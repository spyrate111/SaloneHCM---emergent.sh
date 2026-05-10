"""Time & Attendance endpoints."""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, now_utc, iso
from models import TimeEntryIn

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("")
async def list_attendance(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "admin" else {"employee_id": user.get("employee_id")}
    return await db.attendance.find(q, {"_id": 0}).sort("date", -1).to_list(1000)


@router.post("")
async def add_attendance(body: TimeEntryIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] == "admin" else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    doc = {
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "date": body.date,
        "hours": body.hours,
        "overtime_hours": body.overtime_hours,
        "notes": body.notes,
        "created_at": iso(now_utc()),
    }
    await db.attendance.insert_one(doc)
    doc.pop("_id", None)
    return doc
