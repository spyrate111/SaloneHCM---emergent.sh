"""Dashboard overview + per-role summaries."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from core import db, get_current_user, require_admin, tenant_filter, now_utc, iso
from compliance_score import compute as compute_compliance_score

from core import require_roles

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/compliance-score")
async def compliance_score(user: dict = Depends(require_roles("hr", "payroll"))):
    return await compute_compliance_score(user)


@router.get("/overview")
async def dashboard(user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    employees = await db.employees.find(
        tf, {"_id": 0, "status": 1, "basic_salary_sle": 1, "allowances_sle": 1, "department": 1},
    ).to_list(5000)
    active = [e for e in employees if e.get("status") == "active"]
    payroll_cost = sum(
        float(e.get("basic_salary_sle", 0)) + float(e.get("allowances_sle", 0))
        for e in active
    )
    runs = await db.payroll_runs.find(tf, {"_id": 0, "slips": 0}).sort("created_at", -1).to_list(12)
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


@router.get("/role-summary")
async def role_summary(user: dict = Depends(get_current_user)):
    """Role-scoped dashboard data — each role only receives what it may see."""
    tf = tenant_filter(user)
    role = user.get("role")
    now = now_utc()
    today = now.strftime("%Y-%m-%d")

    if role == "superadmin":
        return {
            "role": role,
            "tenants": await db.companies.count_documents({}),
            "platform_users": await db.users.count_documents({}),
        }

    if role == "hr":
        employees = await db.employees.find(
            tf, {"_id": 0, "status": 1, "department": 1}).to_list(5000)
        active = [e for e in employees if e.get("status") == "active"]
        dept: dict = {}
        for e in active:
            d = e.get("department") or "—"
            dept[d] = dept.get(d, 0) + 1
        return {
            "role": role,
            "headcount": len(active),
            "total_employees": len(employees),
            "pending_leaves": await db.leave_requests.count_documents({"status": "pending", **tf}),
            "on_leave_today": await db.leave_requests.count_documents(
                {"status": "approved", "start_date": {"$lte": today},
                 "end_date": {"$gte": today}, **tf}),
            "punches_today": await db.attendance.count_documents({"date": today, **tf}),
            "departments": [{"name": k, "count": v} for k, v in dept.items()],
        }

    if role == "payroll":
        employees = await db.employees.find(
            tf, {"_id": 0, "status": 1, "basic_salary_sle": 1, "allowances_sle": 1}).to_list(5000)
        active = [e for e in employees if e.get("status") == "active"]
        cost = sum(float(e.get("basic_salary_sle", 0)) + float(e.get("allowances_sle", 0))
                   for e in active)
        runs = await db.payroll_runs.find(tf, {"_id": 0, "slips": 0}).sort(
            "created_at", -1).to_list(12)
        filed = set(await db.nra_filings.distinct("run_id", tf))
        return {
            "role": role,
            "monthly_payroll_sle": round(cost, 2),
            "last_run": runs[0] if runs else None,
            "runs_history": [
                {"period": r["period"], "net": r["totals"]["net"], "gross": r["totals"]["gross"]}
                for r in reversed(runs)
            ],
            "outstanding_filings": sum(1 for r in runs if r["id"] not in filed),
            "runs_total": await db.payroll_runs.count_documents(tf),
        }

    if role == "auditor":
        since = iso(now - timedelta(hours=24))
        recent = await db.audit_logs.find(
            tf, {"_id": 0, "action": 1, "user_email": 1, "ts": 1}).sort("ts", -1).to_list(5)
        return {
            "role": role,
            "audit_24h": await db.audit_logs.count_documents({**tf, "ts": {"$gt": since}}),
            "audit_total": await db.audit_logs.count_documents(tf),
            "flagged_scans": await db.payslip_scan_alerts.count_documents(tf),
            "filings": await db.nra_filings.count_documents(tf),
            "recent_audit": recent,
        }

    raise HTTPException(403, "No role summary for this role — use /api/mobile/summary")
