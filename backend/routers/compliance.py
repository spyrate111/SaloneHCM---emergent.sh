"""Compliance & Tax endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, require_admin
from payroll_engine import PAYE_BANDS, NASSIT_EMPLOYEE, NASSIT_EMPLOYER

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/summary")
async def compliance_summary(_: dict = Depends(get_current_user)):
    runs = await db.payroll_runs.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    total_paye = sum(r["totals"]["paye"] for r in runs)
    total_nassit = sum(r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"] for r in runs)
    return {
        "runs_count": len(runs),
        "ytd_paye_sle": round(total_paye, 2),
        "ytd_nassit_sle": round(total_nassit, 2),
        "next_filing": "NRA PAYE — 15th of next month",
        "regs": {
            "paye_bands": PAYE_BANDS[:-1],
            "nassit_employee": NASSIT_EMPLOYEE,
            "nassit_employer": NASSIT_EMPLOYER,
        },
    }


@router.get("/nra-export/{rid}")
async def nra_export(rid: str, _: dict = Depends(require_admin)):
    r = await db.payroll_runs.find_one({"id": rid}, {"_id": 0})
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
