"""Recurring payroll schedules — CRUD + manual trigger."""
import uuid
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core import db, require_admin, audit, now_utc, iso, tenant_filter, with_tenant
from scheduler import compute_next_run
from payroll_engine import run_payroll

router = APIRouter(prefix="/payroll/schedules", tags=["payroll-schedules"])

Cadence = Literal["monthly", "biweekly", "weekly"]


class ScheduleIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=120)
    cadence: Cadence = "monthly"
    day_of_month: int = Field(28, ge=1, le=31)
    active: bool = True
    description: Optional[str] = ""


class ScheduleUpdate(BaseModel):
    active: Optional[bool] = None
    cadence: Optional[Cadence] = None
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    title: Optional[str] = None
    description: Optional[str] = None


@router.get("")
async def list_schedules(user: dict = Depends(require_admin)):
    return await db.payroll_schedules.find(tenant_filter(user), {"_id": 0}).sort("created_at", -1).to_list(200)


@router.post("")
async def create_schedule(body: ScheduleIn, user: dict = Depends(require_admin)):
    sid = str(uuid.uuid4())
    next_run_at = compute_next_run(body.cadence, body.day_of_month, last_run_at=None)
    doc = with_tenant({
        "id": sid,
        "title": body.title,
        "description": body.description or "",
        "cadence": body.cadence,
        "day_of_month": body.day_of_month,
        "active": body.active,
        "next_run_at": next_run_at,
        "last_run_at": None,
        "last_run_id": None,
        "last_run_status": None,
        "runs_completed": 0,
        "created_at": iso(now_utc()),
        "created_by": user["email"],
        "created_by_id": user["id"],
    }, user)
    await db.payroll_schedules.insert_one(doc)
    doc.pop("_id", None)
    await audit("payroll_schedule_create", f"payroll_schedules/{sid}", user,
                {"title": body.title, "cadence": body.cadence})
    return doc


@router.patch("/{sid}")
async def update_schedule(sid: str, body: ScheduleUpdate, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    schedule = await db.payroll_schedules.find_one({"id": sid, **tf}, {"_id": 0})
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    # Recompute next_run_at if cadence/day changed
    if "cadence" in updates or "day_of_month" in updates:
        updates["next_run_at"] = compute_next_run(
            updates.get("cadence", schedule["cadence"]),
            updates.get("day_of_month", schedule["day_of_month"]),
            schedule.get("last_run_at"),
        )
    if updates:
        await db.payroll_schedules.update_one({"id": sid, **tf}, {"$set": updates})
    await audit("payroll_schedule_update", f"payroll_schedules/{sid}", user, updates)
    return await db.payroll_schedules.find_one({"id": sid, **tf}, {"_id": 0})


@router.delete("/{sid}")
async def delete_schedule(sid: str, user: dict = Depends(require_admin)):
    res = await db.payroll_schedules.delete_one({"id": sid, **tenant_filter(user)})
    if not res.deleted_count:
        raise HTTPException(404, "Not found")
    await audit("payroll_schedule_delete", f"payroll_schedules/{sid}", user)
    return {"ok": True}


@router.post("/{sid}/run-now")
async def run_now(sid: str, user: dict = Depends(require_admin)):
    """Manually fire the schedule for the current month."""
    tf = tenant_filter(user)
    schedule = await db.payroll_schedules.find_one({"id": sid, **tf}, {"_id": 0})
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    today = now_utc()
    doc = await run_payroll(today.year, today.month, user, audit_action="manual_scheduled_run")
    next_at = compute_next_run(schedule["cadence"], schedule.get("day_of_month", 28),
                                iso(today), today)
    await db.payroll_schedules.update_one(
        {"id": sid, **tf},
        {"$set": {
            "last_run_at": iso(today),
            "last_run_id": doc["id"],
            "last_run_status": "manual",
            "next_run_at": next_at,
        }, "$inc": {"runs_completed": 1}},
    )
    return {"ok": True, "run": doc, "next_run_at": next_at}
