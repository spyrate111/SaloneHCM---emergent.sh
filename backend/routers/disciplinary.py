"""Confidential, append-only disciplinary case records for HR."""
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from core import db, require_roles, tenant_filter, with_tenant, now_utc, iso, audit

router = APIRouter(prefix="/disciplinary", tags=["disciplinary"])


class DisciplinaryCaseIn(BaseModel):
    category: Literal["conduct", "attendance", "performance", "policy", "other"] = "other"
    title: str = Field(..., min_length=3, max_length=160)
    incident_date: date
    summary: str = Field(..., min_length=10, max_length=5000)

    @field_validator("title", "summary")
    @classmethod
    def require_non_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank")
        return value


class DisciplinaryEventIn(BaseModel):
    event_type: Literal["warning", "hearing", "outcome", "note"]
    occurred_on: date
    details: str = Field(..., min_length=3, max_length=5000)

    @field_validator("details")
    @classmethod
    def require_non_blank_details(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Details cannot be blank")
        return value


class DisciplinaryStatusIn(BaseModel):
    status: Literal["open", "under_review", "hearing_scheduled", "closed"]
    note: str = Field(..., min_length=3, max_length=1000)

    @field_validator("note")
    @classmethod
    def require_non_blank_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A reason is required for a status change")
        return value


def _actor(user: dict) -> str:
    return user.get("name") or user.get("email") or "HR user"


@router.get("/employees/{eid}/cases")
async def list_employee_cases(eid: str, user: dict = Depends(require_roles("hr"))):
    """List an employee's confidential case records for HR and tenant admins."""
    tf = tenant_filter(user)
    employee = await db.employees.find_one({"id": eid, **tf}, {"_id": 0, "id": 1})
    if not employee:
        raise HTTPException(404, "Employee not found")
    rows = await db.disciplinary_cases.find(
        {"employee_id": eid, **tf}, {"_id": 0},
    ).sort("updated_at", -1).to_list(200)
    await audit(
        "disciplinary_cases_viewed",
        f"employees/{eid}/disciplinary-cases",
        user,
        {"employee_id": eid, "case_count": len(rows)},
    )
    return rows


@router.post("/employees/{eid}/cases")
async def create_employee_case(
    eid: str,
    body: DisciplinaryCaseIn,
    user: dict = Depends(require_roles("hr")),
):
    """Open a case. Case details remain outside general audit metadata."""
    tf = tenant_filter(user)
    employee = await db.employees.find_one({"id": eid, **tf}, {"_id": 0, "id": 1})
    if not employee:
        raise HTTPException(404, "Employee not found")

    now = now_utc()
    cid = str(uuid.uuid4())
    doc = with_tenant({
        "id": cid,
        "employee_id": eid,
        "category": body.category,
        "title": body.title,
        "incident_date": body.incident_date.isoformat(),
        "summary": body.summary,
        "status": "open",
        "opened_by": _actor(user),
        "opened_at": iso(now),
        "updated_by": _actor(user),
        "updated_at": iso(now),
        "closed_at": None,
        "closed_by": None,
        "events": [{
            "id": str(uuid.uuid4()),
            "event_type": "case_opened",
            "occurred_on": date.today().isoformat(),
            "details": "Case opened and initial summary recorded.",
            "created_by": _actor(user),
            "created_at": iso(now),
        }],
    }, user)
    await db.disciplinary_cases.insert_one(doc)
    doc.pop("_id", None)
    await audit(
        "disciplinary_case_opened",
        f"disciplinary_cases/{cid}",
        user,
        {"case_id": cid, "employee_id": eid, "category": body.category},
    )
    return doc


@router.post("/cases/{cid}/events")
async def add_case_event(
    cid: str,
    body: DisciplinaryEventIn,
    user: dict = Depends(require_roles("hr")),
):
    """Append a warning, hearing, outcome, or note to an open case."""
    tf = tenant_filter(user)
    case = await db.disciplinary_cases.find_one({"id": cid, **tf}, {"_id": 0})
    if not case:
        raise HTTPException(404, "Case not found")
    if case.get("status") == "closed":
        raise HTTPException(409, "Reopen the case before adding a timeline entry")

    now = now_utc()
    event = {
        "id": str(uuid.uuid4()),
        "event_type": body.event_type,
        "occurred_on": body.occurred_on.isoformat(),
        "details": body.details,
        "created_by": _actor(user),
        "created_at": iso(now),
    }
    result = await db.disciplinary_cases.update_one(
        {"id": cid, **tf, "status": {"$ne": "closed"}},
        {"$push": {"events": event}, "$set": {
            "updated_by": _actor(user),
            "updated_at": iso(now),
        }},
    )
    if not result.matched_count:
        raise HTTPException(409, "Case was closed before the timeline entry could be saved")

    updated = await db.disciplinary_cases.find_one({"id": cid, **tf}, {"_id": 0})
    await audit(
        "disciplinary_case_event_added",
        f"disciplinary_cases/{cid}",
        user,
        {"case_id": cid, "employee_id": case["employee_id"], "event_type": body.event_type},
    )
    return updated


@router.patch("/cases/{cid}/status")
async def update_case_status(
    cid: str,
    body: DisciplinaryStatusIn,
    user: dict = Depends(require_roles("hr")),
):
    """Change case status with a required reason recorded in its timeline."""
    tf = tenant_filter(user)
    case = await db.disciplinary_cases.find_one({"id": cid, **tf}, {"_id": 0})
    if not case:
        raise HTTPException(404, "Case not found")
    if case.get("status") == body.status:
        raise HTTPException(409, "Case already has that status")

    now = now_utc()
    event = {
        "id": str(uuid.uuid4()),
        "event_type": "status_changed",
        "occurred_on": date.today().isoformat(),
        "details": f"{case.get('status', 'open').replace('_', ' ').title()} → {body.status.replace('_', ' ').title()}. {body.note}",
        "created_by": _actor(user),
        "created_at": iso(now),
    }
    updates = {
        "status": body.status,
        "updated_by": _actor(user),
        "updated_at": iso(now),
        "closed_at": iso(now) if body.status == "closed" else None,
        "closed_by": _actor(user) if body.status == "closed" else None,
    }
    result = await db.disciplinary_cases.update_one(
        {"id": cid, **tf, "status": case.get("status", "open")},
        {"$set": updates, "$push": {"events": event}},
    )
    if not result.matched_count:
        raise HTTPException(409, "Case changed before the status update could be saved")

    updated = await db.disciplinary_cases.find_one({"id": cid, **tf}, {"_id": 0})
    await audit(
        "disciplinary_case_status_changed",
        f"disciplinary_cases/{cid}",
        user,
        {"case_id": cid, "employee_id": case["employee_id"], "from": case.get("status", "open"), "to": body.status},
    )
    return updated
