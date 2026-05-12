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
    employees = await db.employees.find(tf, {"_id": 0}).to_list(2000)
    active = [e for e in employees if e.get("status") == "active"]
    payroll_cost = sum(
        float(e.get("basic_salary_sle", 0)) + float(e.get("allowances_sle", 0))
        for e in active
    )
    runs = await db.payroll_runs.find(tf, {"_id": 0}).sort("created_at", -1).to_list(12)
    pending_leaves = await db.leave_requests.count_documents({"status": "pending", **tf})
    dept_counts = {}
    for e in active:
        dept_counts[e["department"]] = dept_counts.get(e["department"], 0) + 1
    return {
        "headcount": len(active),
        "total_employees": len(employees),
        "monthly_payroll_sle": round(payroll_cost, 2),
        "pending_leaves": pending_leaves,
        "last_run": runs[0] if runs else None,
        "runs_history": [
            {"period": r["period"], "net": r["totals"]["net"], "gross": r["totals"]["gross"]}
            for r in reversed(runs)
        ],
        "departments": [{"name": k, "count": v} for k, v in dept_counts.items()],
    }
