"""IFMIS (Integrated Financial Management Information System) integration layer.

Provides export endpoints used by the Ministry of Finance to:
  1. Download bank-specific disbursement files for each clearing bank in SL.
  2. Reconcile payroll totals against the Treasury Single Account by budget code.
  3. Mark a payroll run as reconciled (records the IFMIS transaction reference
     and timestamp; immutable after that until super-admin override).

All endpoints are tier-gated behind `ifmis_integration` (Gov + Enterprise).
"""
from __future__ import annotations
import io
import csv
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import db, tenant_filter, require_admin, require_feature, audit, now_utc, iso
from bank_formats import render_bank_file, available_formats

router = APIRouter(
    prefix="/ifmis",
    tags=["ifmis"],
    dependencies=[Depends(require_feature("ifmis_integration"))],
)


# ---------- Bank disbursement files ----------

@router.get("/formats")
async def list_formats(_: dict = Depends(require_admin)):
    """List available bank-specific disbursement formats for this tenant."""
    return {"formats": available_formats()}


@router.get("/runs/{rid}/disbursement/{bank_code}")
async def disbursement_file(rid: str, bank_code: str, user: dict = Depends(require_admin)):
    """Download a bank-specific disbursement file."""
    run = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    employees = await db.employees.find(tenant_filter(user), {"_id": 0}).to_list(5000)
    body, media, ext, label = render_bank_file(bank_code, run, employees)
    await audit("ifmis_disbursement_download", f"payroll_runs/{rid}", user,
                {"bank": bank_code, "period": run["period"], "rows": len(run["slips"])})
    fn = f"disbursement-{bank_code.lower()}-{run['period']}.{ext}"
    return StreamingResponse(
        io.BytesIO(body), media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{fn}"',
            "X-Bank-Label": label,
            "X-Record-Count": str(len(run["slips"])),
        },
    )


# ---------- Treasury reconciliation ----------

def _reconciliation_rows(run: dict, emp_map: dict) -> tuple[list[dict], dict]:
    """Group payroll slips by budget_code → MDA vote line. Returns (rows, totals)."""
    by_code: dict = defaultdict(lambda: {
        "budget_code": "", "mda_ministry": "", "headcount": 0,
        "gross": 0.0, "net": 0.0, "paye": 0.0,
        "nassit_employee": 0.0, "nassit_employer": 0.0,
    })
    for s in run["slips"]:
        e = emp_map.get(s["employee_id"], {})
        code = e.get("budget_code") or "UNCODED"
        b = by_code[code]
        b["budget_code"] = code
        b["mda_ministry"] = e.get("mda_ministry") or e.get("department") or "—"
        b["headcount"] += 1
        b["gross"] += s["gross"]
        b["net"] += s["net"]
        b["paye"] += s["paye"]
        b["nassit_employee"] += s.get("nassit_employee", 0)
        b["nassit_employer"] += s.get("nassit_employer", 0)
    rows = [
        {**v, **{k: round(v[k], 2) for k in
                 ("gross", "net", "paye", "nassit_employee", "nassit_employer")}}
        for v in by_code.values()
    ]
    rows.sort(key=lambda r: r["budget_code"])
    totals = {
        "headcount": sum(r["headcount"] for r in rows),
        "gross": round(sum(r["gross"] for r in rows), 2),
        "net": round(sum(r["net"] for r in rows), 2),
        "paye": round(sum(r["paye"] for r in rows), 2),
        "nassit_employee": round(sum(r["nassit_employee"] for r in rows), 2),
        "nassit_employer": round(sum(r["nassit_employer"] for r in rows), 2),
    }
    return rows, totals


@router.get("/runs/{rid}/reconciliation")
async def reconciliation_json(rid: str, user: dict = Depends(require_admin)):
    """Return treasury reconciliation as JSON for the UI."""
    run = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    employees = await db.employees.find(tenant_filter(user), {"_id": 0}).to_list(5000)
    rows, totals = _reconciliation_rows(run, {e["id"]: e for e in employees})
    company = await db.companies.find_one({"id": run["company_id"]},
                                          {"_id": 0, "name": 1, "ifmis_org_code": 1}) or {}
    return {
        "period": run["period"],
        "run_id": rid,
        "org_code": company.get("ifmis_org_code") or "—",
        "org_name": company.get("name"),
        "rows": rows,
        "totals": totals,
        "reconciled": run.get("ifmis_reconciled") or False,
        "ifmis_reference": run.get("ifmis_reference"),
        "ifmis_reconciled_at": run.get("ifmis_reconciled_at"),
    }


@router.get("/runs/{rid}/reconciliation.csv")
async def reconciliation_csv(rid: str, user: dict = Depends(require_admin)):
    run = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    employees = await db.employees.find(tenant_filter(user), {"_id": 0}).to_list(5000)
    rows, totals = _reconciliation_rows(run, {e["id"]: e for e in employees})

    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    w.writerow(["budget_code", "mda_ministry", "headcount", "gross_sle",
                "paye_sle", "nassit_employee_sle", "nassit_employer_sle", "net_sle"])
    for r in rows:
        w.writerow([
            r["budget_code"], r["mda_ministry"], r["headcount"],
            f"{r['gross']:.2f}", f"{r['paye']:.2f}",
            f"{r['nassit_employee']:.2f}", f"{r['nassit_employer']:.2f}", f"{r['net']:.2f}",
        ])
    w.writerow([])
    w.writerow(["TOTAL", "", totals["headcount"],
                f"{totals['gross']:.2f}", f"{totals['paye']:.2f}",
                f"{totals['nassit_employee']:.2f}", f"{totals['nassit_employer']:.2f}",
                f"{totals['net']:.2f}"])
    await audit("ifmis_reconciliation_csv", f"payroll_runs/{rid}", user, {"period": run["period"]})
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="ifmis-recon-{run["period"]}.csv"'},
    )


class ReconcileIn(BaseModel):
    ifmis_reference: str = Field(..., min_length=4, max_length=64)


@router.post("/runs/{rid}/mark-reconciled")
async def mark_reconciled(rid: str, body: ReconcileIn, user: dict = Depends(require_admin)):
    """Lock a payroll run as reconciled against IFMIS with the given transaction reference."""
    run = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("ifmis_reconciled"):
        raise HTTPException(409, "Run already reconciled")
    ts = iso(now_utc())
    await db.payroll_runs.update_one(
        {"id": rid, **tenant_filter(user)},
        {"$set": {
            "ifmis_reconciled": True,
            "ifmis_reference": body.ifmis_reference,
            "ifmis_reconciled_at": ts,
            "ifmis_reconciled_by": user["email"],
        }},
    )
    await audit("ifmis_mark_reconciled", f"payroll_runs/{rid}", user,
                {"period": run["period"], "ifmis_reference": body.ifmis_reference})
    return {"ok": True, "ifmis_reference": body.ifmis_reference, "reconciled_at": ts}
