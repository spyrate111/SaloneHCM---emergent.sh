"""Employee CRUD endpoints."""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, require_admin, audit, now_utc, iso, tenant_filter, with_tenant
from models import EmployeeIn
from routers.payroll_rails import assert_not_cutoff_locked

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("")
async def list_employees(user: dict = Depends(get_current_user)):
    return await db.employees.find(tenant_filter(user), {"_id": 0}).sort("created_at", -1).to_list(2000)


@router.post("")
async def create_employee(body: EmployeeIn, user: dict = Depends(require_admin)):
    await assert_not_cutoff_locked(user, "hiring a new employee")
    eid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": eid, "created_at": iso(now_utc())}, user)
    await db.employees.insert_one(doc)
    doc.pop("_id", None)
    await audit("create", f"employees/{eid}", user, {"name": f'{body.first_name} {body.last_name}'})
    return doc


@router.get("/{eid}")
async def get_employee(eid: str, user: dict = Depends(get_current_user)):
    e = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Not found")
    return e


@router.put("/{eid}")
async def update_employee(eid: str, body: EmployeeIn, user: dict = Depends(require_admin)):
    # Salary changes during cutoff lock are the #1 fraud vector — block them.
    existing = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if existing:
        new_basic = getattr(body, "basic_salary_sle", None)
        new_status = getattr(body, "status", None)
        salary_change = new_basic is not None and existing.get("basic_salary_sle") != new_basic
        status_change = new_status is not None and existing.get("status") != new_status
        if salary_change or status_change:
            await assert_not_cutoff_locked(
                user, "changing an employee's salary" if salary_change else "changing employment status",
            )
    res = await db.employees.update_one(
        {"id": eid, **tenant_filter(user)},
        {"$set": body.model_dump()},
    )
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    e = await db.employees.find_one({"id": eid}, {"_id": 0})
    await audit("update", f"employees/{eid}", user, {"name": f'{body.first_name} {body.last_name}'})
    return e


@router.delete("/{eid}")
async def delete_employee(eid: str, user: dict = Depends(require_admin)):
    await assert_not_cutoff_locked(user, "terminating/deleting an employee")
    await db.employees.delete_one({"id": eid, **tenant_filter(user)})
    await audit("delete", f"employees/{eid}", user)
    return {"ok": True}
