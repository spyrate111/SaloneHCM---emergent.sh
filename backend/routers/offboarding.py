"""Offboarding workflow — exit checklist with role-gated sign-offs, account deactivation on completion."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core import (db, get_current_user, require_roles, can_role, is_admin, audit,
                  tenant_filter, with_tenant, now_utc, iso)

router = APIRouter(prefix="/offboarding", tags=["offboarding"])

CHECKLIST_TEMPLATE = [
    {"key": "final_settlement", "label": "Final payroll settlement", "responsible_role": "payroll"},
    {"key": "document_handover", "label": "Document handover", "responsible_role": "hr"},
    {"key": "equipment_return", "label": "Equipment return", "responsible_role": "hr"},
    {"key": "access_revocation", "label": "Access revocation", "responsible_role": "admin"},
]


def _may_complete(user: dict, item: dict) -> bool:
    role = item["responsible_role"]
    if role == "admin":
        return is_admin(user)
    return can_role(user, role)


@router.get("")
async def list_offboardings(user: dict = Depends(require_roles("hr", "payroll", "auditor"))):
    return await db.offboardings.find(
        tenant_filter(user), {"_id": 0}).sort("started_at", -1).to_list(500)


@router.get("/employee/{eid}")
async def get_for_employee(eid: str, user: dict = Depends(require_roles("hr", "payroll", "auditor"))):
    row = await db.offboardings.find_one(
        {"employee_id": eid, **tenant_filter(user), "status": {"$ne": "cancelled"}},
        {"_id": 0}, sort=[("started_at", -1)])
    if not row:
        raise HTTPException(404, "No offboarding for this employee")
    return row


@router.post("/{eid}/start")
async def start_offboarding(eid: str, user: dict = Depends(require_roles("hr"))):
    emp = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")
    existing = await db.offboardings.find_one(
        {"employee_id": eid, **tenant_filter(user), "status": "in_progress"}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(409, "Offboarding already in progress for this employee")

    oid = str(uuid.uuid4())
    doc = with_tenant({
        "id": oid,
        "employee_id": eid,
        "employee_name": f'{emp.get("first_name", "")} {emp.get("last_name", "")}'.strip(),
        "status": "in_progress",
        "items": [{**i, "completed": False, "completed_by": None, "completed_at": None}
                  for i in CHECKLIST_TEMPLATE],
        "started_by": user.get("name") or user["email"],
        "started_at": iso(now_utc()),
        "completed_at": None,
    }, user)
    await db.offboardings.insert_one(doc)
    doc.pop("_id", None)
    await db.employees.update_one({"id": eid, **tenant_filter(user)},
                                  {"$set": {"status": "exiting"}})
    await audit("offboarding_started", f"offboardings/{oid}", user,
                {"employee": doc["employee_name"], "employee_id": eid})
    return doc


@router.put("/{oid}/items/{key}/complete")
async def complete_item(oid: str, key: str, user: dict = Depends(get_current_user)):
    ob = await db.offboardings.find_one({"id": oid, **tenant_filter(user)}, {"_id": 0})
    if not ob:
        raise HTTPException(404, "Offboarding not found")
    if ob["status"] != "in_progress":
        raise HTTPException(409, "Offboarding is not in progress")
    item = next((i for i in ob["items"] if i["key"] == key), None)
    if not item:
        raise HTTPException(404, "Checklist item not found")
    if item["completed"]:
        raise HTTPException(409, "Item already completed")
    if not _may_complete(user, item):
        raise HTTPException(403, f"Only {item['responsible_role']} (or an admin) may complete '{item['label']}'")

    now = iso(now_utc())
    who = user.get("name") or user["email"]
    for i in ob["items"]:
        if i["key"] == key:
            i.update({"completed": True, "completed_by": who, "completed_at": now})
    all_done = all(i["completed"] for i in ob["items"])
    update = {"items": ob["items"]}
    await audit("offboarding_item_completed", f"offboardings/{oid}", user,
                {"item": key, "employee": ob["employee_name"]})

    deactivated = False
    if all_done:
        update["status"] = "completed"
        update["completed_at"] = now
        await db.employees.update_one({"id": ob["employee_id"], **tenant_filter(user)},
                                      {"$set": {"status": "exited"}})
        res = await db.users.update_many(
            {"employee_id": ob["employee_id"], **tenant_filter(user)},
            {"$set": {"disabled": True, "deactivated_at": now}})
        deactivated = res.modified_count > 0
        await audit("offboarding_completed", f"offboardings/{oid}", user,
                    {"employee": ob["employee_name"], "account_deactivated": deactivated})

    await db.offboardings.update_one({"id": oid}, {"$set": update})
    return {"ok": True, "all_complete": all_done, "account_deactivated": deactivated}


LEAVING_REASONS = {"resignation", "retirement", "redundancy", "contract_end", "dismissal", "other"}


class ExitInterviewIn(BaseModel):
    leaving_reason: str
    notes: str = ""


@router.put("/{oid}/exit-interview")
async def record_exit_interview(oid: str, body: ExitInterviewIn,
                                user: dict = Depends(require_roles("hr"))):
    if body.leaving_reason not in LEAVING_REASONS:
        raise HTTPException(422, f"leaving_reason must be one of: {', '.join(sorted(LEAVING_REASONS))}")
    ob = await db.offboardings.find_one({"id": oid, **tenant_filter(user)}, {"_id": 0})
    if not ob:
        raise HTTPException(404, "Offboarding not found")
    if ob["status"] == "cancelled":
        raise HTTPException(409, "Cannot record an exit interview on a cancelled offboarding")
    record = {
        "leaving_reason": body.leaving_reason,
        "notes": body.notes.strip()[:5000],
        "recorded_by": user.get("name") or user["email"],
        "recorded_at": iso(now_utc()),
    }
    await db.offboardings.update_one({"id": oid}, {"$set": {"exit_interview": record}})
    await audit("exit_interview_recorded", f"offboardings/{oid}", user,
                {"employee": ob["employee_name"], "leaving_reason": body.leaving_reason})
    return {"ok": True, "exit_interview": record}


@router.delete("/{oid}")
async def cancel_offboarding(oid: str, user: dict = Depends(require_roles("hr"))):
    ob = await db.offboardings.find_one({"id": oid, **tenant_filter(user)}, {"_id": 0})
    if not ob:
        raise HTTPException(404, "Offboarding not found")
    if ob["status"] != "in_progress":
        raise HTTPException(409, "Only in-progress offboardings can be cancelled")
    await db.offboardings.update_one({"id": oid}, {"$set": {
        "status": "cancelled",
        "cancelled_by": user.get("name") or user["email"],
        "cancelled_at": iso(now_utc()),
    }})
    await db.employees.update_one({"id": ob["employee_id"], **tenant_filter(user)},
                                  {"$set": {"status": "active"}})
    await audit("offboarding_cancelled", f"offboardings/{oid}", user,
                {"employee": ob["employee_name"]})
    return {"ok": True}
