"""User management within a tenant — invite, list, reset password, delete."""
import uuid
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, get_current_user, require_admin, hash_password,
    audit, now_utc, iso, tenant_filter, with_tenant,
)

router = APIRouter(prefix="/users", tags=["users"])

Role = Literal["admin", "employee"]


class InviteIn(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=120)
    role: Role = "employee"
    password: str = Field(..., min_length=8, max_length=128)
    employee_id: Optional[str] = None  # link to an existing employee record


class ResetPasswordIn(BaseModel):
    password: str = Field(..., min_length=8, max_length=128)


def _public(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u["name"],
        "role": u["role"],
        "company_id": u["company_id"],
        "employee_id": u.get("employee_id"),
        "created_at": u.get("created_at"),
        "created_by": u.get("created_by"),
    }


@router.get("")
async def list_users(user: dict = Depends(require_admin)):
    rows = await db.users.find(
        tenant_filter(user),
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1).to_list(500)
    return rows


@router.post("/invite")
async def invite_user(body: InviteIn, user: dict = Depends(require_admin)):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Email already in use")
    # If linking to an existing employee, ensure it belongs to user's tenant
    if body.employee_id:
        emp = await db.employees.find_one(
            {"id": body.employee_id, **tenant_filter(user)},
            {"_id": 0, "id": 1},
        )
        if not emp:
            raise HTTPException(404, "Employee not found in your organization")

    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "email": email,
        "name": body.name,
        "role": body.role,
        "employee_id": body.employee_id,
        "password_hash": hash_password(body.password),
        "created_at": iso(now_utc()),
        "created_by": user["email"],
    }, user)
    await db.users.insert_one(doc)
    await audit("user_invite", f"users/{doc['id']}", user, {"email": email, "role": body.role})
    return _public(doc)


@router.post("/{uid}/reset-password")
async def reset_password(uid: str, body: ResetPasswordIn, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"id": uid, **tenant_filter(user)}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target.get("role") == "superadmin":
        raise HTTPException(403, "Cannot reset super-admin password")
    await db.users.update_one(
        {"id": uid, **tenant_filter(user)},
        {"$set": {"password_hash": hash_password(body.password)}},
    )
    await audit("user_reset_password", f"users/{uid}", user, {"email": target["email"]})
    return {"ok": True}


@router.delete("/{uid}")
async def delete_user(uid: str, user: dict = Depends(require_admin)):
    if uid == user["id"]:
        raise HTTPException(400, "You cannot delete yourself")
    target = await db.users.find_one({"id": uid, **tenant_filter(user)}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target.get("role") == "superadmin":
        raise HTTPException(403, "Cannot delete super-admin")
    await db.users.delete_one({"id": uid, **tenant_filter(user)})
    await audit("user_delete", f"users/{uid}", user, {"email": target["email"]})
    return {"ok": True}


@router.get("/unlinked-employees")
async def unlinked_employees(user: dict = Depends(require_admin)):
    """Employees in this tenant that don't have a user account yet — for the invite form picker."""
    tf = tenant_filter(user)
    linked = await db.users.distinct("employee_id", {**tf, "employee_id": {"$ne": None}})
    emps = await db.employees.find(
        {**tf, "id": {"$nin": linked}},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "email": 1, "department": 1, "job_title": 1},
    ).to_list(500)
    return emps
