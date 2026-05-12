"""Compliance & Tax endpoints — incl. NRA PAYE return + NASSIT schedule exports."""
import io
import csv
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from core import db, get_current_user, require_admin, audit, tenant_filter, require_feature
from payroll_engine import PAYE_BANDS, NASSIT_EMPLOYEE, NASSIT_EMPLOYER

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/summary")
async def compliance_summary(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    runs = await db.payroll_runs.find(tf, {"_id": 0}).sort("created_at", -1).to_list(50)
    total_paye = sum(r["totals"]["paye"] for r in runs)
    total_nassit = sum(r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"] for r in runs)
    # NRA / NASSIT filing status — by period
    filings = await db.nra_filings.find(tf, {"_id": 0}).sort("filed_at", -1).to_list(50)
    filed_periods = {f["period"]: f for f in filings}
    history = [
        {
            "run_id": r["id"],
            "period": r["period"],
            "paye": r["totals"]["paye"],
            "nassit_total": r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"],
            "employees": r["totals"]["employee_count"],
            "nra_filed": r["period"] in filed_periods,
            "nra_filed_at": filed_periods.get(r["period"], {}).get("filed_at"),
            "nra_reference": filed_periods.get(r["period"], {}).get("nra_reference"),
        }
        for r in runs
    ]
    return {
        "runs_count": len(runs),
        "ytd_paye_sle": round(total_paye, 2),
        "ytd_nassit_sle": round(total_nassit, 2),
        "filed_count": len(filings),
        "outstanding": [h for h in history if not h["nra_filed"]],
        "history": history,
        "next_filing": "NRA PAYE — 15th of next month",
        "regs": {
            "paye_bands": PAYE_BANDS[:-1],
            "nassit_employee": NASSIT_EMPLOYEE,
            "nassit_employer": NASSIT_EMPLOYER,
        },
    }


@router.get("/nra-export/{rid}")
async def nra_export(rid: str, user: dict = Depends(require_admin)):
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
    """NRA PAYE Return CSV — the layout the Sierra Leone NRA accepts at their portal.
    Each row = one employee; final row is the period total per NRA convention."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin only")
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
    """NASSIT contribution schedule CSV — per-employee employee + employer NASSIT for the period."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin only")
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


@router.post("/file-nra/{rid}")
async def mark_nra_filed(rid: str, user: dict = Depends(require_feature("nra_export"))):
    """Record that the NRA return has been filed for this run."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin only")
    tf = tenant_filter(user)
    r = await db.payroll_runs.find_one({"id": rid, **tf}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    existing = await db.nra_filings.find_one({"run_id": rid, **tf})
    if existing:
        raise HTTPException(409, "Already filed")
    # Auto-generate a deterministic NRA reference (in production this would come from NRA portal).
    nra_ref = f"NRA-{r['period']}-{r['id'][:8].upper()}"
    doc = {
        **tf,
        "id": rid,  # piggyback on run id for uniqueness within tenant
        "run_id": rid,
        "period": r["period"],
        "nra_reference": nra_ref,
        "filed_at": datetime.now(timezone.utc).isoformat(),
        "filed_by": user["email"],
        "paye_total": r["totals"]["paye"],
        "nassit_total": r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"],
    }
    await db.nra_filings.insert_one(doc)
    await audit("nra_filed", f"payroll_runs/{rid}", user,
                {"period": r["period"], "nra_reference": nra_ref})
    doc.pop("_id", None)
    return doc


@router.get("/filings")
async def list_filings(user: dict = Depends(require_admin)):
    return await db.nra_filings.find(tenant_filter(user), {"_id": 0}).sort("filed_at", -1).to_list(500)
