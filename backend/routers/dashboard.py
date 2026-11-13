"""Dashboard overview."""
from fastapi import APIRouter, Depends
from core import db, get_current_user, require_admin, tenant_filter
from compliance_score import compute as compute_compliance_score

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/compliance-score")
async def compliance_score(user: dict = Depends(require_admin)):
    return await compute_compliance_score(user)


@router.get("/overview")
async def dashboard(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    is_admin = user.get("role") in ("admin", "superadmin")
    employees = await db.employees.find(
        tf,
        {"_id": 0, "id": 1, "status": 1, "basic_salary_sle": 1, "allowances_sle": 1,
         "department": 1, "manager_id": 1},
    ).to_list(None)
    active = [e for e in employees if e.get("status") == "active"]
    payroll_cost = sum(
        float(e.get("basic_salary_sle", 0)) + float(e.get("allowances_sle", 0))
        for e in active
    ) if is_admin else None
    runs = []
    if is_admin:
        runs = await db.payroll_runs.find(
            tf,
            {"_id": 0, "period": 1, "totals": 1, "status": 1, "mof_status": 1, "created_at": 1},
        ).sort("created_at", -1).to_list(12)
        pending_leaves = await db.leave_requests.count_documents({"status": "pending", **tf})
    else:
        employee_id = user.get("employee_id")
        employee_ids = [employee_id] if employee_id else []
        if employee_id:
            reports = await db.employees.find(
                {"manager_id": employee_id, **tf}, {"_id": 0, "id": 1}
            ).to_list(500)
            employee_ids.extend(report["id"] for report in reports)
        pending_leaves = await db.leave_requests.count_documents(
            {"status": "pending", "employee_id": {"$in": employee_ids}, **tf}
        ) if employee_ids else 0
    dept_counts = {}
    for e in active:
        department = e.get("department", "Unknown")
        dept_counts[department] = dept_counts.get(department, 0) + 1
    last_run = None
    if runs:
        last = runs[0]
        last_run = {
            "period": last["period"],
            "totals": {"net": last["totals"]["net"]},
            "status": last.get("status"),
            "mof_status": last.get("mof_status"),
            "created_at": last.get("created_at"),
        }
    return {
        "headcount": len(active),
        "total_employees": len(employees),
        "monthly_payroll_sle": round(payroll_cost, 2) if payroll_cost is not None else None,
        "pending_leaves": pending_leaves,
        "last_run": last_run,
        "runs_history": [
            {"period": r["period"], "net": r["totals"]["net"], "gross": r["totals"]["gross"]}
            for r in reversed(runs)
        ],
        "departments": [{"name": k, "count": v} for k, v in dept_counts.items()],
    }
