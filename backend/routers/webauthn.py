"""WebAuthn (passkey / biometric) enrolment + assertion for SaloneHCM.

This uses the `webauthn` Python library. The relying-party ID is derived from
the frontend origin; challenges are short-lived (5 min) and stored in
`webauthn_challenges` with a TTL index. Credentials are stored in
`webauthn_credentials` per-user and can be listed / revoked from the mobile
Profile page.

Flow (registration):
    POST /api/auth/webauthn/register/begin  -> options_json (pass to
                                                navigator.credentials.create)
    POST /api/auth/webauthn/register/finish -> verify attestation, persist
                                                credential

Flow (login):
    POST /api/auth/webauthn/login/begin     -> options_json (pass to
                                                navigator.credentials.get)
    POST /api/auth/webauthn/login/finish    -> verify assertion, issue our
                                                usual JWT + CSRF pair
"""
from __future__ import annotations
import os
import base64
import json
import secrets
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from pydantic import BaseModel

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    AuthenticatorAttachment,
)

from core import db, get_current_user, now_utc, iso, make_access
from routers.auth import _set_auth_cookies, _public_company

router = APIRouter(prefix="/auth/webauthn", tags=["webauthn"])

# ---------------------------------------------------------------------------
# Config — RP ID is the eTLD+1 of the frontend origin. Local dev falls back to
# "localhost".
# ---------------------------------------------------------------------------
_FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
_RP_HOST = urlparse(_FRONTEND_URL).hostname or "localhost"
# Strip subdomains for RP ID (WebAuthn accepts a suffix match against origin).
# For preview URLs we keep the full hostname; production it can be trimmed.
RP_ID = _RP_HOST
RP_NAME = "SaloneHCM"
EXPECTED_ORIGIN = _FRONTEND_URL.rstrip("/")


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64url_dec(s: str) -> bytes:
    s = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


async def _issue_session(user: dict, response: Response) -> tuple[str, str]:
    """Mint JWT + set httpOnly cookie + CSRF, matching the classic login path."""
    token = make_access(user["id"], user["email"], user["role"])
    csrf = _set_auth_cookies(response, token)
    return token, csrf


# ---------------------------------------------------------------------------
# Registration ceremony (must be signed-in)
# ---------------------------------------------------------------------------
class RegisterFinishIn(BaseModel):
    credential: dict
    device_label: Optional[str] = None


@router.post("/register/begin")
async def register_begin(user: dict = Depends(get_current_user)):
    # Existing credential IDs — pass as "excludeCredentials" so the same
    # authenticator can't be enrolled twice.
    existing = await db.webauthn_credentials.find(
        {"user_id": user["id"]}, {"_id": 0, "credential_id": 1}).to_list(20)
    exclude = [
        PublicKeyCredentialDescriptor(id=_b64url_dec(c["credential_id"]))
        for c in existing
    ]
    opts = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user["id"].encode("utf-8"),
        user_name=user["email"],
        user_display_name=user.get("name") or user["email"],
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        timeout=60_000,
    )
    # Store the challenge server-side keyed by (user_id, purpose="register")
    await db.webauthn_challenges.update_one(
        {"user_id": user["id"], "purpose": "register"},
        {"$set": {
            "user_id": user["id"],
            "purpose": "register",
            "challenge": _b64url(opts.challenge),
            "created_at": iso(now_utc()),
        }},
        upsert=True,
    )
    return json.loads(options_to_json(opts))


@router.post("/register/finish")
async def register_finish(body: RegisterFinishIn,
                          user: dict = Depends(get_current_user)):
    saved = await db.webauthn_challenges.find_one(
        {"user_id": user["id"], "purpose": "register"}, {"_id": 0})
    if not saved:
        raise HTTPException(400, "No pending registration — call /begin first")

    try:
        verification = verify_registration_response(
            credential=body.credential,
            expected_challenge=_b64url_dec(saved["challenge"]),
            expected_origin=EXPECTED_ORIGIN,
            expected_rp_id=RP_ID,
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Attestation failed: {exc}") from exc

    await db.webauthn_credentials.insert_one({
        "id": secrets.token_urlsafe(16),
        "user_id": user["id"],
        "company_id": user.get("company_id"),
        "credential_id": _b64url(verification.credential_id),
        "public_key": _b64url(verification.credential_public_key),
        "sign_count": verification.sign_count,
        "device_label": (body.device_label or "This device")[:64],
        "created_at": iso(now_utc()),
        "last_used_at": None,
    })
    await db.webauthn_challenges.delete_one(
        {"user_id": user["id"], "purpose": "register"})
    return {"ok": True, "device_label": body.device_label or "This device"}


@router.get("/credentials")
async def list_credentials(user: dict = Depends(get_current_user)):
    rows = await db.webauthn_credentials.find(
        {"user_id": user["id"]},
        {"_id": 0, "id": 1, "device_label": 1, "created_at": 1, "last_used_at": 1},
    ).sort("created_at", -1).to_list(20)
    return rows


@router.delete("/credentials/{cid}")
async def revoke_credential(cid: str, user: dict = Depends(get_current_user)):
    res = await db.webauthn_credentials.delete_one(
        {"id": cid, "user_id": user["id"]})
    return {"ok": True, "deleted": res.deleted_count}


# ---------------------------------------------------------------------------
# Authentication ceremony (unauthenticated — matches classic login)
# ---------------------------------------------------------------------------
class LoginBeginIn(BaseModel):
    email: Optional[str] = None  # optional — resident keys allow passwordless


class LoginFinishIn(BaseModel):
    credential: dict


@router.post("/login/begin")
async def login_begin(body: LoginBeginIn):
    allow: list[PublicKeyCredentialDescriptor] = []
    user = None
    if body.email:
        user = await db.users.find_one(
            {"email": body.email.lower().strip()},
            {"_id": 0, "id": 1, "email": 1, "name": 1})
        if user:
            existing = await db.webauthn_credentials.find(
                {"user_id": user["id"]},
                {"_id": 0, "credential_id": 1}).to_list(20)
            allow = [
                PublicKeyCredentialDescriptor(id=_b64url_dec(c["credential_id"]))
                for c in existing
            ]
    opts = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=60_000,
    )
    # Store challenge globally (unauthenticated); keyed by challenge hash to
    # prevent reuse. Use short TTL via periodic cleanup — for this scale we
    # just keep the last 100 challenges.
    await db.webauthn_challenges.insert_one({
        "purpose": "login",
        "user_id": (user or {}).get("id"),
        "challenge": _b64url(opts.challenge),
        "created_at": iso(now_utc()),
    })
    return json.loads(options_to_json(opts))


@router.post("/login/finish")
async def login_finish(body: LoginFinishIn, response: Response):
    # Look up the credential by the returned rawId
    raw_id = body.credential.get("rawId") or body.credential.get("id")
    if not raw_id:
        raise HTTPException(400, "Malformed credential")
    cred_id_b64 = _b64url(_b64url_dec(raw_id))
    cred = await db.webauthn_credentials.find_one(
        {"credential_id": cred_id_b64}, {"_id": 0})
    if not cred:
        raise HTTPException(404, "Credential not enrolled")
    user = await db.users.find_one({"id": cred["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    # Find the challenge we most recently issued that isn't yet consumed.
    saved = await db.webauthn_challenges.find_one(
        {"purpose": "login", "$or": [{"user_id": user["id"]},
                                      {"user_id": None}]},
        {"_id": 0}, sort=[("created_at", -1)])
    if not saved:
        raise HTTPException(400, "No pending login challenge")

    try:
        verification = verify_authentication_response(
            credential=body.credential,
            expected_challenge=_b64url_dec(saved["challenge"]),
            expected_origin=EXPECTED_ORIGIN,
            expected_rp_id=RP_ID,
            credential_public_key=_b64url_dec(cred["public_key"]),
            credential_current_sign_count=cred["sign_count"],
            require_user_verification=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Assertion failed: {exc}") from exc

    await db.webauthn_credentials.update_one(
        {"id": cred["id"]},
        {"$set": {"sign_count": verification.new_sign_count,
                  "last_used_at": iso(now_utc())}},
    )
    # burn the challenge
    await db.webauthn_challenges.delete_many(
        {"purpose": "login", "challenge": saved["challenge"]})

    token, csrf = await _issue_session(user, response)
    company = await db.companies.find_one({"id": user.get("company_id")}, {"_id": 0})
    return {
        "ok": True,
        "id": user["id"], "email": user["email"], "name": user.get("name"),
        "role": user.get("role"), "employee_id": user.get("employee_id"),
        "company_id": user.get("company_id"), "company": _public_company(company),
        "twofa_enabled": bool(user.get("twofa_enabled")),
        "mof_approver": bool(user.get("mof_approver")),
        "finance_officer": bool(user.get("finance_officer")),
        "token": token, "csrf_token": csrf,
    }
