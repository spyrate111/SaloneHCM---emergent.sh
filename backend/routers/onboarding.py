"""Employee-onboarding QR: a short-lived signed token that lets a new hire
tap once on their phone camera to open the SaloneHCM mobile app already
signed-in as themselves.

Flow:
    1. Admin opens the employee's detail page, clicks "Print onboarding QR".
       → POST /api/employees/{eid}/onboarding-qr returns a one-time token
         (14-day TTL) + a URL + PNG QR bytes.
    2. Admin prints the sheet, hands it to the new hire.
    3. New hire scans the QR → opens
       `{FRONTEND_URL}/onboard/{token}` on their phone.
    4. The React app POSTs `/api/auth/onboarding-consume` with the token.
       Backend verifies + one-time consumes + issues our usual JWT + CSRF
       cookies + returns the mobile-app landing URL.

Security notes
    - Token is a short 32-char urlsafe secret stored server-side (not JWT),
      so revocation is trivially a delete.
    - Single-use: once consumed the DB row is deleted.
    - Bound to (company_id, user_id) — no way to reuse for another user.
    - 14-day TTL by default; admin can pass `ttl_days=1..30`.
"""
from __future__ import annotations
import base64
import io
import os
import secrets
from datetime import timedelta
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import (
    db, get_current_user, require_admin, audit, now_utc, iso,
    tenant_filter,
)
from routers.auth import _set_auth_cookies
from core import make_access

router = APIRouter(tags=["onboarding"])

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


class OnboardIssueIn(BaseModel):
    ttl_days: int = Field(default=14, ge=1, le=30)


@router.post("/employees/{eid}/onboarding-qr")
async def issue_onboarding_qr(eid: str, body: Optional[OnboardIssueIn] = None,
                              user: dict = Depends(require_admin)):
    """Return `{url, token, qr_png_b64, expires_at}` — admin can print any of
    the three. QR encodes the URL, opaque to the scanner."""
    tf = tenant_filter(user)
    emp = await db.employees.find_one({"id": eid, **tf}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")
    # Employees must be linked to a user account for auto-sign-in. Find or
    # bail with a clear message.
    u = await db.users.find_one(
        {"employee_id": eid, **tf}, {"_id": 0, "id": 1, "email": 1, "name": 1, "role": 1})
    if not u:
        raise HTTPException(409, "Create a user login for this employee first, then re-issue the QR")

    ttl_days = (body.ttl_days if body else 14)
    token = secrets.token_urlsafe(32)
    expires = now_utc() + timedelta(days=ttl_days)
    # Invalidate any prior token for the same employee — one active QR at a time
    await db.onboarding_tokens.delete_many({"employee_id": eid, **tf})
    await db.onboarding_tokens.insert_one({
        "token": token,
        "employee_id": eid,
        "user_id": u["id"],
        "company_id": user["company_id"],
        "issued_by": user["email"],
        "issued_at": iso(now_utc()),
        "expires_at": iso(expires),
        "consumed_at": None,
    })
    url = f"{FRONTEND_URL.rstrip('/')}/onboard/{token}"

    # Render QR — high error correction so it survives crumpled prints
    img = qrcode.make(url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    await audit("onboarding_qr_issued", f"employees/{eid}", user,
                {"employee_email": u["email"], "ttl_days": ttl_days})
    return {
        "token": token,
        "url": url,
        "qr_png_b64": b64,
        "expires_at": iso(expires),
        "employee": {"id": eid, "name": u.get("name") or u["email"], "email": u["email"], "role": u.get("role")},
    }


@router.get("/employees/{eid}/onboarding-qr.png")
async def onboarding_qr_png(eid: str, user: dict = Depends(require_admin)):
    """Convenience: return the QR PNG for the current active token as an
    image directly, so it can be embedded in <img src=…> in a printable
    HTML sheet without a data-URL round trip."""
    tf = tenant_filter(user)
    row = await db.onboarding_tokens.find_one(
        {"employee_id": eid, "consumed_at": None, **tf}, {"_id": 0})
    if not row:
        raise HTTPException(404, "No active onboarding token — issue one first")
    url = f"{FRONTEND_URL.rstrip('/')}/onboard/{row['token']}"
    img = qrcode.make(url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png",
                             headers={"Cache-Control": "no-store"})


class OnboardConsumeIn(BaseModel):
    token: str


@router.post("/auth/onboarding-consume")
async def consume_onboarding(body: OnboardConsumeIn, response: Response):
    """Public endpoint — no auth required. Verifies, consumes, signs in."""
    row = await db.onboarding_tokens.find_one({"token": body.token}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Invalid or already-used onboarding link")
    if row.get("consumed_at"):
        raise HTTPException(410, "This onboarding link has already been used — ask your HR team for a new one")
    if row["expires_at"] < iso(now_utc()):
        raise HTTPException(410, "This onboarding link has expired — ask your HR team for a new one")

    u = await db.users.find_one({"id": row["user_id"]}, {"_id": 0})
    if not u:
        raise HTTPException(404, "Associated user account was removed")

    # Consume — one-time
    await db.onboarding_tokens.update_one(
        {"token": body.token},
        {"$set": {"consumed_at": iso(now_utc())}},
    )
    await audit("onboarding_qr_consumed", f"users/{u['id']}", u,
                {"employee_id": row["employee_id"]})

    token = make_access(u)
    _set_auth_cookies(response, token)
    return {
        "ok": True,
        "token": token,
        "user": {"id": u["id"], "email": u["email"], "name": u.get("name"),
                 "role": u.get("role"), "employee_id": u.get("employee_id")},
        "landing": "/m",
    }
