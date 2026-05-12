"""Ministry-level rollups — Gov-tier dashboard that aggregates by department (= ministry)."""
from collections import defaultdict
from fastapi import APIRouter, Depends
from core import db, require_feature, tenant_filter
from payroll_engine import calc_payslip

router = APIRouter(
    prefix="/ministry",
    tags=["ministry"],
    dependencies=[Depends(require_feature("ministry_reports"))],
)


@router.get("/rollup")
async def ministry_rollup(user: dict = Depends(require_feature("ministry_reports"))):
    """Aggregate KPIs grouped by department (treated as ministry)."""
    tf = tenant_filter(user)
    employees = await db.employees.find(tf, {"_id": 0}).to_list(5000)

    by_ministry: dict[str, dict] = defaultdict(lambda: {
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
    })

    for e in employees:
        m = by_ministry[e["department"]]
        m["name"] = e["department"]
        m["headcount_total"] += 1
        if e.get("status") == "active":
            m["headcount_active"] += 1
            slip = calc_payslip(e)
            m["monthly_payroll_gross"] += slip["gross"]
            m["monthly_payroll_net"] += slip["net"]
            m["monthly_paye"] += slip["paye"]
            m["monthly_nassit"] += slip["nassit_employee"] + slip["nassit_employer"]
            m["avg_basic_salary"] += slip["basic"]
        if e.get("is_manager"):
            m["headcount_managers"] += 1

    # Leave aggregations
    leaves = await db.leave_requests.find(tf, {"_id": 0}).to_list(5000)
    emp_dept = {e["id"]: e["department"] for e in employees}
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    for lv in leaves:
        dept = emp_dept.get(lv["employee_id"])
        if not dept:
            continue
        if lv["status"] == "pending":
            by_ministry[dept]["leave_pending"] += 1
        if lv["status"] == "approved" and (lv.get("created_at") or "") >= cutoff:
            by_ministry[dept]["leave_approved_30d"] += lv.get("days", 0)

    rows = []
    for m in by_ministry.values():
        if m["headcount_active"]:
            m["avg_basic_salary"] = round(m["avg_basic_salary"] / m["headcount_active"], 2)
        m["monthly_payroll_gross"] = round(m["monthly_payroll_gross"], 2)
        m["monthly_payroll_net"] = round(m["monthly_payroll_net"], 2)
        m["monthly_paye"] = round(m["monthly_paye"], 2)
        m["monthly_nassit"] = round(m["monthly_nassit"], 2)
        rows.append(m)
    rows.sort(key=lambda x: x["monthly_payroll_gross"], reverse=True)

    # Tenant totals
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
