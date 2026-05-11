"""Leave endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, audit, now_utc, iso, tenant_filter, with_tenant
from models import LeaveIn, LeaveDecision

router = APIRouter(prefix="/leave", tags=["leave"])


@router.get("")
async def list_leaves(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    if user["role"] == "admin":
        return await db.leave_requests.find(tf, {"_id": 0}).sort("created_at", -1).to_list(1000)
    # Employee: their own + their direct reports' (if they're a manager)
    my_eid = user.get("employee_id")
    if not my_eid:
        return []
    reports = await db.employees.find(
        {"manager_id": my_eid, **tf},
        {"_id": 0, "id": 1},
    ).to_list(500)
    eids = [my_eid] + [r["id"] for r in reports]
    return await db.leave_requests.find(
        {"employee_id": {"$in": eids}, **tf},
        {"_id": 0},
    ).sort("created_at", -1).to_list(1000)


@router.post("")
async def create_leave(body: LeaveIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] == "admin" else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    emp = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found in your organization")
    days = (datetime.fromisoformat(body.end_date) - datetime.fromisoformat(body.start_date)).days + 1
    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "employee_name": f'{emp["first_name"]} {emp["last_name"]}',
        "leave_type": body.leave_type,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "days": max(1, days),
        "reason": body.reason,
        "status": "pending",
        "created_at": iso(now_utc()),
    }, user)
    await db.leave_requests.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{lid}/decision")
async def decide_leave(lid: str, body: LeaveDecision, user: dict = Depends(get_current_user)):
    lv = await db.leave_requests.find_one({"id": lid, **tenant_filter(user)}, {"_id": 0})
    if not lv:
        raise HTTPException(404, "Not found")
    # Authorization: admin, or the requesting employee's direct manager
    if user.get("role") != "admin":
        if not user.get("employee_id"):
            raise HTTPException(403, "Admin or manager only")
        emp = await db.employees.find_one({"id": lv["employee_id"]}, {"_id": 0})
        if not emp or emp.get("manager_id") != user["employee_id"]:
            raise HTTPException(403, "You can only decide leave for your direct reports")
    res = await db.leave_requests.update_one(
        {"id": lid, **tenant_filter(user)},
        {"$set": {"status": body.status}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    action = f"leave_{body.status}" if user.get("role") == "admin" else f"manager_leave_{body.status}"
    await audit(action, f"leave_requests/{lid}", user, {"employee": lv.get("employee_name")})
    return {"ok": True, "status": body.status}
