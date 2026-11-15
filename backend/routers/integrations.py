"""Integration status endpoints — admins can check which 3rd-party services are wired."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from core import require_admin, audit
from sms import is_configured as sms_is_configured, send_one as sms_send_one, normalize_phone
from email_service import is_configured as email_is_configured, _send

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status")
async def integrations_status(_: dict = Depends(require_admin)):
    return {
        "twilio": {"configured": sms_is_configured(), "service": "sms"},
        "resend": {"configured": email_is_configured(), "service": "email"},
    }


class EmailTestIn(BaseModel):
    to: EmailStr
    subject: Optional[str] = "SaloneHCM test email"


@router.post("/email/test")
async def send_test_email(body: EmailTestIn, user: dict = Depends(require_admin)):
    html = (
        '<p>Hello! This is a SaloneHCM test email confirming Resend is wired.</p>'
        f'<p style="font-size:12px;color:#686D76;">Sent by {user["email"]}</p>'
    )
    res = await _send(body.to, body.subject or "SaloneHCM test email", html)
    await audit("email_test_send", "integrations/email/test", user, {"to": body.to, "ok": res.get("ok")})
    return res


class SmsTestIn(BaseModel):
    to: str = Field(..., description="E.164 phone number, e.g. +18777804236")
    body: Optional[str] = Field(None, max_length=320)


@router.post("/sms/test")
async def send_test_sms(payload: SmsTestIn, user: dict = Depends(require_admin)):
    """Send a single test SMS to verify Twilio is wired correctly."""
    if not sms_is_configured():
        raise HTTPException(503, "Twilio is not configured. Set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER in .env.")
    to = normalize_phone(payload.to)
    if not to:
        raise HTTPException(422, f"Phone '{payload.to}' is not valid E.164 (e.g. +18777804236)")
    body = payload.body or f"SaloneHCM: Test SMS from {user.get('email', 'admin')} — Twilio integration is working."
    res = await sms_send_one(to, body)
    await audit("sms_test_send", "integrations/sms/test", user, {"to": to, "ok": res.get("ok"), "sid": res.get("sid")})
    if not res.get("ok"):
        raise HTTPException(502, f"Twilio rejected the message: {res.get('error', 'unknown')}")
    return {"ok": True, "to": to, "sid": res.get("sid"), "status": res.get("status")}
