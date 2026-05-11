"""Deeper analytics endpoints — payroll trend, leave usage by dept, top earners, audit activity."""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends

from core import db, get_current_user, tenant_filter, require_feature

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_feature("analytics"))])


@router.get("/payroll-trend")
async def payroll_trend(user: dict = Depends(get_current_user)):
    runs = await db.payroll_runs.find(tenant_filter(user), {"_id": 0}).sort("created_at", 1).to_list(120)
    return [
        {
            "period": r["period"],
            "gross": r["totals"]["gross"],
            "net": r["totals"]["net"],
            "paye": r["totals"]["paye"],
            "nassit": r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"],
        }
        for r in runs
    ]


@router.get("/leave-usage")
async def leave_usage(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    leaves = await db.leave_requests.find(tf, {"_id": 0}).to_list(5000)
    employees = {e["id"]: e for e in await db.employees.find(tf, {"_id": 0}).to_list(2000)}
    by_dept = defaultdict(lambda: {"days": 0, "count": 0})
    by_type = defaultdict(int)
    for lv in leaves:
        if lv.get("status") != "approved":
            continue
        emp = employees.get(lv["employee_id"], {})
        dept = emp.get("department", "Unknown")
        by_dept[dept]["days"] += lv.get("days", 0)
        by_dept[dept]["count"] += 1
        by_type[lv["leave_type"]] += lv.get("days", 0)
    return {
        "by_department": [{"name": k, **v} for k, v in by_dept.items()],
        "by_type": [{"type": k, "days": v} for k, v in by_type.items()],
    }


@router.get("/top-earners")
async def top_earners(user: dict = Depends(get_current_user)):
    employees = await db.employees.find(
        {"status": "active", **tenant_filter(user)},
        {"_id": 0},
    ).to_list(2000)
    employees.sort(key=lambda e: (e.get("basic_salary_sle", 0) + e.get("allowances_sle", 0)), reverse=True)
    return [
        {
            "id": e["id"],
            "name": f'{e["first_name"]} {e["last_name"]}',
            "department": e["department"],
            "job_title": e["job_title"],
            "gross": e.get("basic_salary_sle", 0) + e.get("allowances_sle", 0),
        }
        for e in employees[:10]
    ]


@router.get("/audit-activity")
async def audit_activity(user: dict = Depends(get_current_user)):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = await db.audit_logs.find(
        {"ts": {"$gte": cutoff}, **tenant_filter(user)},
        {"_id": 0, "ts": 1, "action": 1},
    ).to_list(5000)
    by_day = defaultdict(int)
    by_action = defaultdict(int)
    for r in rows:
        day = r["ts"][:10]
        by_day[day] += 1
        by_action[r["action"]] += 1
    return {
        "by_day": sorted([{"date": k, "count": v} for k, v in by_day.items()], key=lambda x: x["date"]),
        "by_action": sorted([{"action": k, "count": v} for k, v in by_action.items()], key=lambda x: -x["count"])[:10],
    }
