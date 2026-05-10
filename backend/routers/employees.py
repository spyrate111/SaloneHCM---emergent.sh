"""Employee CRUD endpoints."""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, require_admin, audit, now_utc, iso
from models import EmployeeIn

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("")
async def list_employees(_: dict = Depends(get_current_user)):
    return await db.employees.find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)


@router.post("")
async def create_employee(body: EmployeeIn, user: dict = Depends(require_admin)):
    eid = str(uuid.uuid4())
    doc = {**body.model_dump(), "id": eid, "created_at": iso(now_utc())}
    await db.employees.insert_one(doc)
    doc.pop("_id", None)
    await audit("create", f"employees/{eid}", user, {"name": f'{body.first_name} {body.last_name}'})
    return doc


@router.get("/{eid}")
async def get_employee(eid: str, _: dict = Depends(get_current_user)):
    e = await db.employees.find_one({"id": eid}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Not found")
    return e


@router.put("/{eid}")
async def update_employee(eid: str, body: EmployeeIn, user: dict = Depends(require_admin)):
    res = await db.employees.update_one({"id": eid}, {"$set": body.model_dump()})
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    e = await db.employees.find_one({"id": eid}, {"_id": 0})
    await audit("update", f"employees/{eid}", user, {"name": f'{body.first_name} {body.last_name}'})
    return e


@router.delete("/{eid}")
async def delete_employee(eid: str, user: dict = Depends(require_admin)):
    await db.employees.delete_one({"id": eid})
    await audit("delete", f"employees/{eid}", user)
    return {"ok": True}
