"""Leave endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, require_admin, audit, now_utc, iso
from models import LeaveIn, LeaveDecision

router = APIRouter(prefix="/leave", tags=["leave"])


@router.get("")
async def list_leaves(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "admin" else {"employee_id": user.get("employee_id")}
    return await db.leave_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)


@router.post("")
async def create_leave(body: LeaveIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] == "admin" else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    emp = await db.employees.find_one({"id": eid}, {"_id": 0})
    days = (datetime.fromisoformat(body.end_date) - datetime.fromisoformat(body.start_date)).days + 1
    doc = {
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "employee_name": f'{emp["first_name"]} {emp["last_name"]}' if emp else "Unknown",
        "leave_type": body.leave_type,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "days": max(1, days),
        "reason": body.reason,
        "status": "pending",
        "created_at": iso(now_utc()),
    }
    await db.leave_requests.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{lid}/decision")
async def decide_leave(lid: str, body: LeaveDecision, user: dict = Depends(require_admin)):
    res = await db.leave_requests.update_one({"id": lid}, {"$set": {"status": body.status}})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    await audit(f"leave_{body.status}", f"leave_requests/{lid}", user)
    return {"ok": True, "status": body.status}
