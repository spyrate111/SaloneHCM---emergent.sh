"""Manager Self-Service: team view, direct reports, team payroll/leave/attendance summary."""
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, require_admin
from payroll_engine import calc_payslip

router = APIRouter(prefix="/team", tags=["team"])


async def _team_summary(manager_eid: str) -> dict:
    """Compute team metrics for a given manager's employee_id."""
    reports = await db.employees.find({"manager_id": manager_eid}, {"_id": 0}).to_list(500)
    report_ids = [r["id"] for r in reports]

    # Team payroll cost
    slips = [calc_payslip(r) for r in reports if r.get("status") == "active"]
    payroll = {
        "gross": round(sum(s["gross"] for s in slips), 2),
        "net": round(sum(s["net"] for s in slips), 2),
        "headcount_active": len(slips),
    }

    # Pending leave for team
    pending_leaves = 0
    if report_ids:
        pending_leaves = await db.leave_requests.count_documents(
            {"employee_id": {"$in": report_ids}, "status": "pending"}
        )

    # Recent leave (last 5 across team)
    recent_leaves = []
    if report_ids:
        recent_leaves = await db.leave_requests.find(
            {"employee_id": {"$in": report_ids}}, {"_id": 0}
        ).sort("created_at", -1).to_list(5)

    # Recent attendance
    recent_attendance = []
    if report_ids:
        recent_attendance = await db.attendance.find(
            {"employee_id": {"$in": report_ids}}, {"_id": 0}
        ).sort("date", -1).to_list(10)
        emp_map = {r["id"]: r for r in reports}
        for a in recent_attendance:
            e = emp_map.get(a["employee_id"], {})
            a["employee_name"] = f'{e.get("first_name","")} {e.get("last_name","")}'.strip()

    return {
        "reports": reports,
        "payroll": payroll,
        "pending_leaves": pending_leaves,
        "recent_leaves": recent_leaves,
        "recent_attendance": recent_attendance,
        "team_size": len(reports),
    }


@router.get("/me")
async def my_team(user: dict = Depends(get_current_user)):
    eid = user.get("employee_id")
    if not eid:
        # Admin without an employee record — show empty team gracefully
        return {"team_size": 0, "reports": [], "payroll": {"gross": 0, "net": 0, "headcount_active": 0},
                "pending_leaves": 0, "recent_leaves": [], "recent_attendance": []}
    return await _team_summary(eid)


@router.get("/managers")
async def list_managers(_: dict = Depends(require_admin)):
    """All employees flagged is_manager — useful for the Employee form dropdown."""
    return await db.employees.find(
        {"is_manager": True}, {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "department": 1, "job_title": 1}
    ).sort("first_name", 1).to_list(500)


@router.get("/{eid}")
async def team_for(eid: str, _: dict = Depends(require_admin)):
    e = await db.employees.find_one({"id": eid}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Employee not found")
    summary = await _team_summary(eid)
    summary["manager"] = {"id": e["id"], "name": f'{e["first_name"]} {e["last_name"]}',
                         "job_title": e["job_title"], "department": e["department"]}
    return summary
