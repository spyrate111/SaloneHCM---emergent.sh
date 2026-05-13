"""Integration status endpoints — admins can check which 3rd-party services are wired."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional

from core import require_admin, audit
from sms import is_configured as sms_is_configured
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
