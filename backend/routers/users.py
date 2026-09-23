"""User management within a tenant — invite, list, reset password, delete."""
import uuid
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import (
    db, get_current_user, require_admin, require_superadmin, hash_password,
    audit, now_utc, iso, tenant_filter, with_tenant,
)

router = APIRouter(prefix="/users", tags=["users"])

Role = Literal["admin", "hr", "payroll", "manager", "employee", "auditor"]

ROLE_DESCRIPTIONS = {
    "admin": "Full control of everything in the company",
    "hr": "Employees, leave, training, performance & benefits — no payroll money or user management",
    "payroll": "Payroll runs, vouchers, payslips & compliance filings — read-only employees",
    "manager": "Self-service plus their own team: approve reports' leave, see team attendance",
    "employee": "Self-service only — own payslips, leave, attendance and training",
    "auditor": "Read-only oversight — audit logs, compliance reports, scan logs, punch maps and leave records. Cannot change anything",
}


class RoleChangeIn(BaseModel):
    role: Role


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


def _stale_invite_query(user: dict) -> dict:
    from datetime import timedelta
    cutoff = iso(now_utc() - timedelta(days=7))
    return {**tenant_filter(user), "consumed_at": None, "superseded_at": None,
            "created_at": {"$lt": cutoff}}


@router.get("/invites/stale-count")
async def stale_invite_count(user: dict = Depends(require_superadmin)):
    """Pending invitations older than 7 days (super-admin only)."""
    return {"count": await db.user_invites.count_documents(_stale_invite_query(user))}


@router.delete("/invites/stale")
async def clear_stale_invites(user: dict = Depends(require_superadmin)):
    """Hard-delete all pending invitations older than 7 days (super-admin only)."""
    r = await db.user_invites.delete_many(_stale_invite_query(user))
    await audit("invites_stale_cleared", "user_invites", user, {"deleted": r.deleted_count})
    return {"ok": True, "deleted": r.deleted_count}


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


@router.get("/roles")
async def list_roles(user: dict = Depends(require_admin)):
    """Assignable roles with plain-language permission summaries."""
    return [{"role": r, "description": d} for r, d in ROLE_DESCRIPTIONS.items()]


@router.post("/test-accounts/seed")
async def seed_test_accounts_endpoint(user: dict = Depends(require_superadmin)):
    """Create/refresh the 70 standard test accounts (10 per role) in THIS
    environment's database. Superadmin only, idempotent, audited."""
    from seed_test_accounts import seed_accounts
    res = await seed_accounts()
    if not res.get("ok"):
        raise HTTPException(409, res.get("error", "Seeding failed"))
    await audit("test_accounts_seeded", "users/test-accounts", user,
                {"created": res["created"], "updated": res["updated"]})
    return res


@router.delete("/test-accounts")
async def wipe_test_accounts(user: dict = Depends(require_superadmin)):
    """Permanently delete all seeded test accounts (flagged test_account=true
    on a salonehcm domain). Superadmin only, audited."""
    q = {"test_account": True, "email": {"$regex": r"@salonehcm\.(com|sl)$"}}
    count = await db.users.count_documents(q)
    if count:
        await db.users.delete_many(q)
    await audit("test_accounts_wiped", "users/test-accounts", user, {"deleted": count})
    return {"ok": True, "deleted": count}


@router.patch("/{uid}/role")
async def change_user_role(uid: str, body: RoleChangeIn, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"id": uid, **tenant_filter(user)}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if target.get("role") == "superadmin":
        raise HTTPException(403, "Cannot change a super-admin's role")
    if target["id"] == user["id"]:
        raise HTTPException(400, "You cannot change your own role")
    old = target.get("role")
    await db.users.update_one({"id": uid, **tenant_filter(user)},
                              {"$set": {"role": body.role}})
    await audit("user_role_changed", f"users/{uid}", user,
                {"email": target["email"], "from": old, "to": body.role})
    return {"ok": True, "role": body.role}


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


@router.post("/me/role-tour-seen")
async def dismiss_role_tour(user: dict = Depends(get_current_user)):
    """One-time role welcome card dismissed — never show again for this user."""
    await db.users.update_one({"id": user["id"]}, {"$set": {"role_tour_seen": True}})
    return {"ok": True}


@router.get("/me/digest-preview")
async def digest_preview(user: dict = Depends(get_current_user)):
    """Snapshot of what today's digest would contain (admin only)."""
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(403, "Digest is admin-only")
    from digest import _aggregate_for_tenant
    return await _aggregate_for_tenant(user["company_id"])


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
