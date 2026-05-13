"""Auth endpoints: login, logout, me, 2FA management."""
from fastapi import APIRouter, HTTPException, Depends, Request, Response

from core import db, get_current_user, verify_password, hash_password, make_access, limiter, audit, now_utc, iso
from models import LoginIn, TotpVerifyIn, TotpDisableIn
import twofa

router = APIRouter(prefix="/auth", tags=["auth"])

# Roles that MUST use 2FA once it's been enabled on their account.
TWOFA_REQUIRED_ROLES = {"superadmin"}


def _set_cookie(resp: Response, token: str):
    resp.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )


def _public_company(c: dict | None) -> dict | None:
    if not c:
        return None
    return {
        "id": c["id"], "name": c["name"], "tier": c["tier"],
        "label": c.get("label"), "features": c.get("features", []),
    }


@router.post("/login")
@limiter.limit("30/minute")
async def login(request: Request, body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("company_id"):
        raise HTTPException(401, "User has no company assigned — contact your admin")

    # Enforce 2FA if enabled on this account
    if user.get("twofa_enabled"):
        if not body.totp_code:
            # Tell the frontend to prompt for a 6-digit code
            raise HTTPException(401, detail={"code": "totp_required", "message": "2FA code required"})
        if not twofa.verify(user.get("twofa_secret"), body.totp_code):
            raise HTTPException(401, detail={"code": "totp_invalid", "message": "Invalid 2FA code"})

    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    token = make_access(user["id"], user["email"], user["role"])
    _set_cookie(response, token)
    return {
        "id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"],
        "employee_id": user.get("employee_id"),
        "company_id": user["company_id"], "company": _public_company(company),
        "twofa_enabled": bool(user.get("twofa_enabled")),
        "token": token,
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    user["company"] = _public_company(company)
    user["twofa_enabled"] = bool(user.get("twofa_enabled"))
    user.pop("twofa_secret", None)
    return user


@router.post("/2fa/setup")
async def twofa_setup(user: dict = Depends(get_current_user)):
    """Generate a fresh secret + QR. The secret is stored as pending until verified."""
    secret = twofa.new_secret()
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"twofa_pending_secret": secret}},
    )
    uri = twofa.provisioning_uri(secret, user["email"])
    return {
        "secret": secret,
        "uri": uri,
        "qr_png_data_url": twofa.qr_png_b64(uri),
        "required_for_role": user["role"] in TWOFA_REQUIRED_ROLES,
    }


@router.post("/2fa/enable")
async def twofa_enable(body: TotpVerifyIn, user: dict = Depends(get_current_user)):
    if user.get("twofa_enabled"):
        raise HTTPException(409, "2FA already enabled")
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "twofa_pending_secret": 1})
    pending = (fresh or {}).get("twofa_pending_secret")
    if not pending:
        raise HTTPException(400, "Call /auth/2fa/setup first")
    if not twofa.verify(pending, body.code):
        raise HTTPException(400, "Invalid code — try again")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "twofa_enabled": True,
            "twofa_secret": pending,
            "twofa_enabled_at": iso(now_utc()),
        },
         "$unset": {"twofa_pending_secret": ""}},
    )
    await audit("2fa_enable", f"users/{user['id']}", user, {})
    return {"ok": True, "twofa_enabled": True}


@router.post("/2fa/disable")
async def twofa_disable(body: TotpDisableIn, user: dict = Depends(get_current_user)):
    fresh = await db.users.find_one({"id": user["id"]})
    if not fresh or not fresh.get("twofa_enabled"):
        raise HTTPException(409, "2FA is not enabled on this account")
    if not verify_password(body.password, fresh["password_hash"]):
        raise HTTPException(401, "Invalid password")
    if not twofa.verify(fresh.get("twofa_secret"), body.code):
        raise HTTPException(401, "Invalid 2FA code")
    if user["role"] in TWOFA_REQUIRED_ROLES:
        raise HTTPException(403, "Cannot disable 2FA — required for your role")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"twofa_enabled": False}, "$unset": {"twofa_secret": "", "twofa_enabled_at": ""}},
    )
    await audit("2fa_disable", f"users/{user['id']}", user, {})
    return {"ok": True, "twofa_enabled": False}


@router.get("/2fa/policy")
async def twofa_policy(user: dict = Depends(get_current_user)):
    """Tells the frontend whether the current user MUST enable 2FA."""
    return {
        "role": user["role"],
        "required": user["role"] in TWOFA_REQUIRED_ROLES,
        "enabled": bool(user.get("twofa_enabled")),
    }
