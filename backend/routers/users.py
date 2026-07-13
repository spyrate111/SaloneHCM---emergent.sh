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


class FlagsIn(BaseModel):
    finance_officer: Optional[bool] = None
    mof_approver: Optional[bool] = None


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


class MagicInviteIn(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=120)
    role: Role = "employee"
    employee_id: Optional[str] = None  # link to an existing employee record


@router.post("/invite-magic")
async def invite_magic(body: MagicInviteIn, user: dict = Depends(require_admin)):
    """Email a magic-link invite via Resend. The recipient sets their password on first click."""
    import secrets as _s
    from datetime import timedelta
    from email_service import send_user_invite, is_configured as _ec
    if not _ec():
        raise HTTPException(503, "Email service not configured")

    email = body.email.lower().strip()
    # Block if there's an active user already
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "Email already in use")
    if body.employee_id:
        emp = await db.employees.find_one(
            {"id": body.employee_id, **tenant_filter(user)},
            {"_id": 0, "id": 1},
        )
        if not emp:
            raise HTTPException(404, "Employee not found in your organization")

    # Invalidate any existing un-consumed invite for this email
    await db.user_invites.update_many(
        {"email": email, "consumed_at": None},
        {"$set": {"superseded_at": iso(now_utc())}},
    )

    token = _s.token_urlsafe(32)
    expires_at = iso(now_utc() + timedelta(days=7))
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0, "name": 1, "id": 1})
    invite_doc = with_tenant({
        "id": str(uuid.uuid4()),
        "token": token,
        "email": email,
        "name": body.name,
        "role": body.role,
        "employee_id": body.employee_id,
        "invited_by": user["email"],
        "invited_by_id": user["id"],
        "expires_at": expires_at,
        "created_at": iso(now_utc()),
        "consumed_at": None,
    }, user)
    await db.user_invites.insert_one(invite_doc)

    email_res = await send_user_invite(
        invite_email=email,
        invite_name=body.name,
        inviter_name=user["email"].split("@")[0].replace(".", " ").title(),
        company_name=(company or {}).get("name", "your company"),
        invite_token=token,
        role=body.role,
        company_id=user["company_id"],
    )
    await audit("user_invite_magic", f"user_invites/{invite_doc['id']}", user, {
        "email": email, "role": body.role, "email_ok": email_res.get("ok"),
    })
    return {
        "id": invite_doc["id"], "email": email, "role": body.role,
        "expires_at": expires_at, "email_status": email_res,
    }


@router.get("/invites")
async def list_invites(user: dict = Depends(require_admin)):
    """List active (pending) magic-link invites for this tenant."""
    return await db.user_invites.find(
        {**tenant_filter(user), "consumed_at": None, "superseded_at": None},
        {"_id": 0, "token": 0},
    ).sort("created_at", -1).to_list(200)


@router.delete("/invites/{iid}")
async def revoke_invite(iid: str, user: dict = Depends(require_admin)):
    r = await db.user_invites.update_one(
        {"id": iid, **tenant_filter(user), "consumed_at": None, "superseded_at": None},
        {"$set": {"superseded_at": iso(now_utc())}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Invite not found, already consumed, or already revoked")
    await audit("invite_revoke", f"user_invites/{iid}", user, {})
    return {"ok": True}


@router.patch("/{uid}/flags")
async def set_user_flags(uid: str, body: FlagsIn, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"id": uid, **tenant_filter(user)}, {"_id": 0, "id": 1})
    if not target:
        raise HTTPException(404, "User not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(422, "No flags provided")
    await db.users.update_one({"id": uid}, {"$set": updates})
    await audit("user_flags_set", f"users/{uid}", user, updates)
    return {"ok": True, **updates}


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


class DigestPrefsIn(BaseModel):
    push: bool = True
    email: bool = False


@router.get("/me/digest-prefs")
async def get_digest_prefs(user: dict = Depends(get_current_user)):
    u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "digest_prefs": 1})
    prefs = (u or {}).get("digest_prefs") or {"push": True, "email": False}
    return prefs


@router.put("/me/digest-prefs")
async def set_digest_prefs(body: DigestPrefsIn, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(403, "Digest is admin-only")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"digest_prefs": body.model_dump()}},
    )
    await audit("digest_prefs_update", f"users/{user['id']}", user, body.model_dump())
    return {"ok": True, **body.model_dump()}


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
