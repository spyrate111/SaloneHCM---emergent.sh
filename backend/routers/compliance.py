"""Compliance & Tax endpoints — incl. NRA PAYE return + NASSIT schedule exports."""
import io
import csv
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import db, get_current_user, require_admin, audit, tenant_filter, require_feature
from payroll_engine import PAYE_BANDS, NASSIT_EMPLOYEE, NASSIT_EMPLOYER

from core import require_roles, can_role

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _build_nra_csv(run: dict, employees: list, company: dict) -> bytes:
    emp_map = {e["id"]: e for e in employees}
    period = run["period"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["NRA PAYE RETURN"])
    w.writerow(["Period", period])
    w.writerow(["Employer TIN", (company or {}).get("tin", "")])
    w.writerow(["Employer Name", (company or {}).get("name", "")])
    w.writerow([])
    w.writerow([
        "tin", "employee_name", "nassit_no", "department",
        "gross_sle", "taxable_sle", "paye_sle",
        "nassit_employee_sle", "nassit_employer_sle", "net_sle",
    ])
    for s in run["slips"]:
        emp = emp_map.get(s["employee_id"], {})
        taxable = round(s["gross"] - s["nassit_employee"], 2)
        w.writerow([
            emp.get("tin", ""), s["employee_name"], emp.get("nassit_no", ""),
            emp.get("department", ""), f'{s["gross"]:.2f}', f'{taxable:.2f}',
            f'{s["paye"]:.2f}', f'{s["nassit_employee"]:.2f}',
            f'{s["nassit_employer"]:.2f}', f'{s["net"]:.2f}',
        ])
    t = run["totals"]
    w.writerow([])
    w.writerow(["TOTAL", "", "", "",
                f'{t["gross"]:.2f}', f'{t["gross"] - t["nassit_employee"]:.2f}',
                f'{t["paye"]:.2f}', f'{t["nassit_employee"]:.2f}',
                f'{t["nassit_employer"]:.2f}', f'{t["net"]:.2f}'])
    return buf.getvalue().encode()


@router.get("/summary")
async def compliance_summary(user: dict = Depends(require_roles("payroll", "auditor"))):
    tf = tenant_filter(user)
    all_runs = await db.payroll_runs.find(tf, {"_id": 0}).sort("created_at", -1).to_list(500)
    # A rerun replaces the earlier run for the same pay period in reporting.
    latest_by_period = {}
    for run in all_runs:
        if run.get("status") == "completed" and run.get("period"):
            latest_by_period.setdefault(run["period"], run)
    latest_runs = list(latest_by_period.values())[:50]

    reporting_year = datetime.now(timezone.utc).year
    year_runs = [
        run for period, run in latest_by_period.items()
        if period.startswith(f"{reporting_year}-")
    ]
    total_paye = sum(float(r.get("totals", {}).get("paye", 0)) for r in year_runs)
    total_nassit = sum(
        float(r.get("totals", {}).get("nassit_employee", 0))
        + float(r.get("totals", {}).get("nassit_employer", 0))
        for r in year_runs
    )

    # NRA filing status is tied to the current payroll run for each period.
    filings = await db.nra_filings.find(tf, {"_id": 0}).sort("filed_at", -1).to_list(500)
    filed_runs = {}
    for filing in filings:
        run_id = filing.get("run_id")
        if run_id and run_id not in filed_runs:
            filed_runs[run_id] = filing
    history = [
        {
            "run_id": r["id"],
            "period": r["period"],
            "paye": r["totals"]["paye"],
            "nassit_total": r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"],
            "employees": r["totals"]["employee_count"],
            "nra_filed": bool(
                filed_runs.get(r["id"])
                and filed_runs[r["id"]].get("reference_source") == "external"
                and filed_runs[r["id"]].get("nra_reference")
            ),
            "nra_legacy_recorded": bool(
                filed_runs.get(r["id"])
                and filed_runs[r["id"]].get("reference_source") != "external"
            ),
            "nra_filed_at": (
                filed_runs[r["id"]].get("filed_at")
                if filed_runs.get(r["id"], {}).get("reference_source") == "external" else None
            ),
            "nra_reference": (
                filed_runs[r["id"]].get("nra_reference")
                if filed_runs.get(r["id"], {}).get("reference_source") == "external" else None
            ),
        }
        for r in latest_runs
    ]
    return {
        "runs_count": len(latest_runs),
        "report_year": reporting_year,
        "ytd_paye_sle": round(total_paye, 2),
        "ytd_nassit_sle": round(total_nassit, 2),
        "filed_count": sum(1 for h in history if h["nra_filed"]),
        "outstanding": [h for h in history if not h["nra_filed"] and not h["nra_legacy_recorded"]],
        "unverified": [h for h in history if h["nra_legacy_recorded"]],
        "history": history,
        "next_filing": "NRA PAYE due by the 15th of the following month",
        "regs": {
            "paye_bands": PAYE_BANDS[:-1],
            "nassit_employee": NASSIT_EMPLOYEE,
            "nassit_employer": NASSIT_EMPLOYER,
        },
    }


@router.get("/nra-export/{rid}")
async def nra_export(rid: str, user: dict = Depends(require_roles("payroll", "auditor"))):
    """Original JSON export — kept for backwards compatibility with the UI table."""
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Not found")
    rows = [
        {
            "employee": s["employee_name"],
            "gross_sle": s["gross"],
            "paye_sle": s["paye"],
            "nassit_employee_sle": s["nassit_employee"],
            "nassit_employer_sle": s["nassit_employer"],
            "net_sle": s["net"],
        }
        for s in r["slips"]
    ]
    return {"period": r["period"], "rows": rows, "totals": r["totals"]}


@router.get("/nra-paye-return.csv/{rid}")
async def nra_paye_return_csv(rid: str, user: dict = Depends(require_feature("nra_export"))):
    """Structured payroll workpaper for NRA PAYE preparation; it does not submit the return."""
    if not can_role(user, "payroll", "auditor"):
        raise HTTPException(403, "Payroll, auditor or admin only")
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    employees = await db.employees.find(tenant_filter(user), {"_id": 0}).to_list(2000)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    emp_map = {e["id"]: e for e in employees}
    period = r["period"]

    buf = io.StringIO()
    w = csv.writer(buf)
    # NRA PAYE Return header block
    w.writerow(["NRA PAYE RETURN"])
    w.writerow(["Period", period])
    w.writerow(["Employer TIN", (company or {}).get("tin", "")])
    w.writerow(["Employer Name", (company or {}).get("name", "")])
    w.writerow([])
    w.writerow([
        "tin", "employee_name", "nassit_no", "department",
        "gross_sle", "taxable_sle", "paye_sle",
        "nassit_employee_sle", "nassit_employer_sle", "net_sle",
    ])
    for s in r["slips"]:
        emp = emp_map.get(s["employee_id"], {})
        # Taxable = gross less NASSIT employee (Sierra Leone convention)
        taxable = round(s["gross"] - s["nassit_employee"], 2)
        w.writerow([
            emp.get("tin", ""),
            s["employee_name"],
            emp.get("nassit_no", ""),
            emp.get("department", ""),
            f'{s["gross"]:.2f}',
            f'{taxable:.2f}',
            f'{s["paye"]:.2f}',
            f'{s["nassit_employee"]:.2f}',
            f'{s["nassit_employer"]:.2f}',
            f'{s["net"]:.2f}',
        ])
    # Period totals
    t = r["totals"]
    w.writerow([])
    w.writerow(["TOTAL", "", "", "",
                f'{t["gross"]:.2f}', f'{t["gross"] - t["nassit_employee"]:.2f}',
                f'{t["paye"]:.2f}', f'{t["nassit_employee"]:.2f}',
                f'{t["nassit_employer"]:.2f}', f'{t["net"]:.2f}'])

    await audit("nra_paye_export", f"payroll_runs/{rid}", user,
                {"period": period, "rows": len(r["slips"])})
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="NRA-PAYE-Return-{period}.csv"'},
    )


@router.get("/nassit-schedule.csv/{rid}")
async def nassit_schedule_csv(rid: str, user: dict = Depends(require_feature("nra_export"))):
    """Per-employee NASSIT contribution workpaper to accompany the payment advice form."""
    if not can_role(user, "payroll", "auditor"):
        raise HTTPException(403, "Payroll, auditor or admin only")
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    employees = await db.employees.find(tenant_filter(user), {"_id": 0}).to_list(2000)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    emp_map = {e["id"]: e for e in employees}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["NASSIT CONTRIBUTION SCHEDULE"])
    w.writerow(["Period", r["period"]])
    w.writerow(["Employer NASSIT No.", (company or {}).get("nassit_employer", "")])
    w.writerow(["Employer Name", (company or {}).get("name", "")])
    w.writerow([])
    w.writerow(["nassit_no", "employee_name", "basic_sle", "employee_5pct", "employer_10pct", "total_15pct"])
    total_emp = 0.0
    total_er = 0.0
    for s in r["slips"]:
        emp = emp_map.get(s["employee_id"], {})
        emp_share = s["nassit_employee"]
        er_share = s["nassit_employer"]
        total_emp += emp_share
        total_er += er_share
        w.writerow([
            emp.get("nassit_no", ""),
            s["employee_name"],
            f'{s.get("basic", 0):.2f}',
            f'{emp_share:.2f}',
            f'{er_share:.2f}',
            f'{emp_share + er_share:.2f}',
        ])
    w.writerow([])
    w.writerow(["TOTAL", "", "",
                f'{total_emp:.2f}', f'{total_er:.2f}', f'{total_emp + total_er:.2f}'])
    await audit("nassit_export", f"payroll_runs/{rid}", user,
                {"period": r["period"], "rows": len(r["slips"])})
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="NASSIT-Schedule-{r["period"]}.csv"'},
    )


class FilingReferenceIn(BaseModel):
    nra_reference: str = Field(..., min_length=1, max_length=120)


@router.post("/file-nra/{rid}")
async def mark_nra_filed(rid: str, body: FilingReferenceIn, user: dict = Depends(require_feature("nra_export"))):
    """Record the reference returned after an employer submits through NRA ITAS."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin only")
    nra_ref = body.nra_reference.strip()
    if not nra_ref:
        raise HTTPException(422, "Enter the reference returned by NRA ITAS")
    tf = tenant_filter(user)
    r = await db.payroll_runs.find_one({"id": rid, **tf}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")

    filing = {
        "period": r["period"],
        "nra_reference": nra_ref,
        "reference_source": "external",
        "filed_at": datetime.now(timezone.utc).isoformat(),
        "filed_by": user["email"],
        "paye_total": r["totals"]["paye"],
        "nassit_total": r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"],
    }
    existing = await db.nra_filings.find_one({"run_id": rid, **tf}, {"_id": 0})
    if existing and existing.get("reference_source") == "external":
        raise HTTPException(409, "An NRA submission reference is already recorded for this run")
    if existing:
        await db.nra_filings.update_one({"run_id": rid, **tf}, {"$set": filing})
        doc = await db.nra_filings.find_one({"run_id": rid, **tf}, {"_id": 0})
        action = "nra_filing_reference_verified"
    else:
        doc = {
            **tf,
            "id": rid,
            "run_id": rid,
            **filing,
        }
        await db.nra_filings.insert_one(doc)
        doc.pop("_id", None)
        action = "nra_filed"

    await audit(action, f"payroll_runs/{rid}", user,
                {"period": r["period"], "nra_reference": nra_ref})
    return doc


@router.get("/filings")
async def list_filings(user: dict = Depends(require_roles("payroll", "auditor"))):
    return await db.nra_filings.find(tenant_filter(user), {"_id": 0}).sort("filed_at", -1).to_list(500)


class EmailFilingIn(BaseModel):
    to: Optional[str] = None


@router.post("/nra-paye-return.csv/{rid}/email")
async def email_nra_paye_csv(rid: str, body: EmailFilingIn, user: dict = Depends(require_feature("nra_export"))):
    """Email the NRA PAYE Return CSV to the requester (or another email)."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin only")
    from email_service import send_csv_attachment, is_configured as _ec
    if not _ec():
        raise HTTPException(503, "Email service not configured")
    tf = tenant_filter(user)
    r = await db.payroll_runs.find_one({"id": rid, **tf}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    employees = await db.employees.find(tf, {"_id": 0}).to_list(2000)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    csv_bytes = _build_nra_csv(r, employees, company or {})
    to = (body.to or user["email"]).strip().lower()
    res = await send_csv_attachment(
        to=to,
        subject=f"[SaloneHCM] NRA PAYE Return — {r['period']}",
        title=f"NRA PAYE Return · {r['period']}",
        body_text=(
            f"Attached is the <strong>NRA PAYE Return</strong> for "
            f"<strong>{(company or {}).get('name','your company')}</strong>, period "
            f"<strong>{r['period']}</strong>. Total PAYE: <strong>SLE {r['totals']['paye']:.2f}</strong>."
        ),
        csv_bytes=csv_bytes,
        filename=f"NRA-PAYE-Return-{r['period']}.csv",
        company_id=user["company_id"],
    )
    await audit("nra_paye_email", f"payroll_runs/{rid}", user, {"to": to, "period": r["period"], "ok": res.get("ok")})
    return {**res, "period": r["period"], "to": to}
