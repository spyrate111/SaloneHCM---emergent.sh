"""Time & Attendance endpoints."""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, now_utc, iso, tenant_filter, with_tenant
from models import TimeEntryIn

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("")
async def list_attendance(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    if user["role"] == "admin":
        return await db.attendance.find(tf, {"_id": 0}).sort("date", -1).to_list(1000)
    return await db.attendance.find(
        {"employee_id": user.get("employee_id"), **tf},
        {"_id": 0},
    ).sort("date", -1).to_list(1000)


@router.post("")
async def add_attendance(body: TimeEntryIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] == "admin" else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    # Validate employee belongs to user's company
    emp = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0, "id": 1})
    if not emp:
        raise HTTPException(404, "Employee not found in your organization")
    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "date": body.date,
        "hours": body.hours,
        "overtime_hours": body.overtime_hours,
        "notes": body.notes,
        "created_at": iso(now_utc()),
    }, user)
    await db.attendance.insert_one(doc)
    doc.pop("_id", None)
    return doc
