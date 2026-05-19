"""Ministry-level rollups — Gov-tier dashboard that aggregates by department (= ministry)."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from core import db, require_feature, tenant_filter
from payroll_engine import calc_payslip

router = APIRouter(
    prefix="/ministry",
    tags=["ministry"],
    dependencies=[Depends(require_feature("ministry_reports"))],
)


def _blank_ministry() -> dict:
    return {
        "name": "",
        "headcount_total": 0,
        "headcount_active": 0,
        "headcount_managers": 0,
        "monthly_payroll_gross": 0.0,
        "monthly_payroll_net": 0.0,
        "monthly_paye": 0.0,
        "monthly_nassit": 0.0,
        "avg_basic_salary": 0.0,
        "leave_pending": 0,
        "leave_approved_30d": 0,
    }


def _accumulate_employee(bucket: dict, e: dict) -> None:
    bucket["name"] = e["department"]
    bucket["headcount_total"] += 1
    if e.get("status") == "active":
        bucket["headcount_active"] += 1
        slip = calc_payslip(e)
        bucket["monthly_payroll_gross"] += slip["gross"]
        bucket["monthly_payroll_net"] += slip["net"]
        bucket["monthly_paye"] += slip["paye"]
        bucket["monthly_nassit"] += slip["nassit_employee"] + slip["nassit_employer"]
        bucket["avg_basic_salary"] += slip["basic"]
    if e.get("is_manager"):
        bucket["headcount_managers"] += 1


def _accumulate_leave(bucket: dict, lv: dict, cutoff_iso: str) -> None:
    if lv["status"] == "pending":
        bucket["leave_pending"] += 1
    elif lv["status"] == "approved" and (lv.get("created_at") or "") >= cutoff_iso:
        bucket["leave_approved_30d"] += lv.get("days", 0)


def _finalize(bucket: dict) -> None:
    if bucket["headcount_active"]:
        bucket["avg_basic_salary"] = round(bucket["avg_basic_salary"] / bucket["headcount_active"], 2)
    for k in ("monthly_payroll_gross", "monthly_payroll_net", "monthly_paye", "monthly_nassit"):
        bucket[k] = round(bucket[k], 2)


@router.get("/rollup")
async def ministry_rollup(user: dict = Depends(require_feature("ministry_reports"))):
    """Aggregate KPIs grouped by department (treated as ministry)."""
    tf = tenant_filter(user)
    employees = await db.employees.find(tf, {"_id": 0}).to_list(5000)

    by_ministry: dict[str, dict] = defaultdict(_blank_ministry)
    for e in employees:
        _accumulate_employee(by_ministry[e["department"]], e)

    leaves = await db.leave_requests.find(tf, {"_id": 0}).to_list(5000)
    emp_dept = {e["id"]: e["department"] for e in employees}
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    for lv in leaves:
        dept = emp_dept.get(lv["employee_id"])
        if dept:
            _accumulate_leave(by_ministry[dept], lv, cutoff_iso)

    rows = []
    for m in by_ministry.values():
        _finalize(m)
        rows.append(m)
    rows.sort(key=lambda x: x["monthly_payroll_gross"], reverse=True)

    totals = {
        "ministries": len(rows),
        "headcount_total": sum(r["headcount_total"] for r in rows),
        "headcount_active": sum(r["headcount_active"] for r in rows),
        "monthly_payroll_gross": round(sum(r["monthly_payroll_gross"] for r in rows), 2),
        "monthly_payroll_net": round(sum(r["monthly_payroll_net"] for r in rows), 2),
        "monthly_paye": round(sum(r["monthly_paye"] for r in rows), 2),
        "monthly_nassit": round(sum(r["monthly_nassit"] for r in rows), 2),
        "leave_pending": sum(r["leave_pending"] for r in rows),
    }
    return {"ministries": rows, "totals": totals}
