"""Employee CRUD endpoints."""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, require_admin, audit, now_utc, iso, tenant_filter, with_tenant, can_role
from models import EmployeeIn, EmployeeMobileMoneyDetailsIn
from routers.payroll_rails import assert_not_cutoff_locked

from core import require_roles

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("")
async def list_employees(user: dict = Depends(get_current_user)):
    """HR/payroll/admin/auditor: full register. Manager: self + direct reports.
    Employee: own record only."""
    tf = tenant_filter(user)
    if can_role(user, "hr", "payroll", "auditor"):
        return await db.employees.find(tf, {"_id": 0}).sort("created_at", -1).to_list(2000)
    my_eid = user.get("employee_id")
    if not my_eid:
        return []
    if user.get("role") == "manager":
        return await db.employees.find(
            {**tf, "$or": [{"id": my_eid}, {"manager_id": my_eid}]},
            {"_id": 0}).sort("created_at", -1).to_list(2000)
    return await db.employees.find({**tf, "id": my_eid}, {"_id": 0}).to_list(1)


@router.post("")
async def create_employee(body: EmployeeIn, user: dict = Depends(require_roles("hr"))):
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
    if not can_role(user, "hr", "payroll", "auditor"):
        my_eid = user.get("employee_id")
        is_own = eid == my_eid
        is_report = user.get("role") == "manager" and e.get("manager_id") == my_eid
        if not (is_own or is_report):
            raise HTTPException(403, "You may only view your own record")
    return e


@router.put("/{eid}")
async def update_employee(eid: str, body: EmployeeIn, user: dict = Depends(require_roles("hr"))):
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
    updates = body.model_dump()
    # Preserve payout numbers when older clients omit the new optional fields.
    for field in ("orange_money_number", "afrimoney_number"):
        if field not in body.model_fields_set:
            updates.pop(field, None)
    res = await db.employees.update_one(
        {"id": eid, **tenant_filter(user)},
        {"$set": updates},
    )
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    e = await db.employees.find_one({"id": eid}, {"_id": 0})
    await audit("update", f"employees/{eid}", user, {"name": f'{body.first_name} {body.last_name}'})
    return e


@router.patch("/{eid}/mobile-money-details")
async def update_mobile_money_details(
    eid: str,
    body: EmployeeMobileMoneyDetailsIn,
    user: dict = Depends(require_roles("hr")),
):
    employee = await db.employees.find_one(
        {"id": eid, **tenant_filter(user)}, {"_id": 0, "id": 1},
    )
    if not employee:
        raise HTTPException(404, "Not found")
    details = body.model_dump()
    await db.employees.update_one(
        {"id": eid, **tenant_filter(user)},
        {"$set": details},
    )
    await audit(
        "employee_mobile_money_details_updated",
        f"employees/{eid}",
        user,
        {
            "orange_money_number_updated": bool(details.get("orange_money_number")),
            "afrimoney_number_updated": bool(details.get("afrimoney_number")),
        },
    )
    return await db.employees.find_one(
        {"id": eid, **tenant_filter(user)}, {"_id": 0},
    )


@router.delete("/{eid}")
async def delete_employee(eid: str, user: dict = Depends(require_roles("hr"))):
    await assert_not_cutoff_locked(user, "terminating/deleting an employee")
    await db.employees.delete_one({"id": eid, **tenant_filter(user)})
    await db.offboardings.delete_many({"employee_id": eid, **tenant_filter(user)})
    await audit("delete", f"employees/{eid}", user)
    return {"ok": True}
