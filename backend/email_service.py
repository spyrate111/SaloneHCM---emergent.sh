"""Resend email service — async-safe wrappers for transactional sends (approver notices, invites)."""
import asyncio
import logging
import os
from typing import Optional

import resend

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.email")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def is_configured() -> bool:
    return bool(RESEND_API_KEY)


async def _send(to: str, subject: str, html: str) -> dict:
    """Single send via Resend, returned as {ok, id?, error?}."""
    if not is_configured():
        return {"ok": False, "error": "resend_not_configured", "dry_run": True}
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"ok": True, "id": result.get("id") if isinstance(result, dict) else getattr(result, "id", None)}
    except Exception as e:
        logger.warning("Resend send failed for %s: %s", to, e)
        return {"ok": False, "error": str(e)[:300]}


async def _log(kind: str, to: str, subject: str, result: dict, meta: Optional[dict] = None):
    try:
        await db.email_logs.insert_one({
            "kind": kind,
            "to": to,
            "subject": subject,
            "status": "sent" if result.get("ok") else ("dry_run" if result.get("dry_run") else "failed"),
            "provider_id": result.get("id"),
            "error": result.get("error"),
            "company_id": (meta or {}).get("company_id"),
            "sent_at": iso(now_utc()),
            "meta": meta or {},
        })
    except Exception as e:
        logger.warning("email log persist failed: %s", e)


def _wrap_html(title: str, body_html: str, cta_label: Optional[str] = None, cta_url: Optional[str] = None) -> str:
    cta = ""
    if cta_label and cta_url:
        cta = f"""
        <tr><td style="padding:24px 0 8px 0;">
          <a href="{cta_url}" style="background:#133326;color:#ffffff;text-decoration:none;font-family:Inter,Arial,sans-serif;font-size:14px;font-weight:600;padding:12px 22px;border-radius:6px;display:inline-block;">{cta_label}</a>
        </td></tr>"""
    return f"""<!doctype html><html><body style="margin:0;background:#F7F6F2;font-family:Inter,Arial,sans-serif;color:#1A1C1E;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F7F6F2;padding:32px 12px;">
  <tr><td align="center">
    <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #E2DFD6;border-radius:12px;overflow:hidden;">
      <tr><td style="background:linear-gradient(135deg,#133326,#26547C);color:#ffffff;padding:24px 28px;">
        <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;opacity:.7;">SaloneHCM</div>
        <div style="font-size:22px;font-weight:700;margin-top:4px;">{title}</div>
      </td></tr>
      <tr><td style="padding:28px;font-size:14px;line-height:1.65;color:#1A1C1E;">
        {body_html}
        {cta}
      </td></tr>
      <tr><td style="padding:18px 28px;background:#F7F6F2;border-top:1px solid #E2DFD6;font-size:11px;color:#686D76;">
        SaloneHCM · Sierra Leone Human Capital Management
      </td></tr>
    </table>
  </td></tr></table></body></html>"""


# ============ Public API ============

async def send_scenario_approval_request(
    approver_email: str,
    approver_name: str,
    requester_name: str,
    scenario_name: str,
    scenario_id: str,
    summary: str,
    company_id: Optional[str] = None,
) -> dict:
    """Notify an approver that a payroll scenario needs their decision."""
    cta_url = f"{FRONTEND_URL}/simulator?scenario={scenario_id}" if FRONTEND_URL else None
    html = _wrap_html(
        title="Payroll scenario awaiting your approval",
        body_html=f"""
          <p>Hi {approver_name or 'there'},</p>
          <p><strong>{requester_name}</strong> has submitted a payroll scenario titled <strong>"{scenario_name}"</strong> and is requesting your approval.</p>
          <div style="background:#F7F6F2;border:1px solid #E2DFD6;border-radius:8px;padding:14px 16px;margin:14px 0;font-size:13px;color:#525860;white-space:pre-line;">{summary}</div>
          <p style="color:#525860;font-size:12px;">Open the scenario in SaloneHCM to review, compare, approve, or apply.</p>
        """,
        cta_label="Open scenario",
        cta_url=cta_url,
    )
    res = await _send(approver_email, f"[SaloneHCM] Approval needed — {scenario_name}", html)
    await _log("scenario_approval", approver_email, scenario_name, res, {
        "scenario_id": scenario_id,
        "requester_name": requester_name,
        "company_id": company_id,
    })
    return res


async def send_scenario_decision(
    requester_email: str,
    requester_name: str,
    scenario_name: str,
    scenario_id: str,
    approver_name: str,
    decision: str,
    note: Optional[str] = None,
    company_id: Optional[str] = None,
) -> dict:
    """Notify the requester of an approver's decision."""
    cta_url = f"{FRONTEND_URL}/simulator?scenario={scenario_id}" if FRONTEND_URL else None
    pretty = decision.capitalize()
    accent = "#2D7A5D" if decision == "approved" else "#B83A3A"
    html = _wrap_html(
        title=f"Scenario {pretty.lower()}",
        body_html=f"""
          <p>Hi {requester_name or 'there'},</p>
          <p>Your scenario <strong>"{scenario_name}"</strong> was <strong style="color:{accent};">{pretty}</strong> by {approver_name}.</p>
          {('<div style="background:#F7F6F2;border:1px solid #E2DFD6;border-radius:8px;padding:12px 14px;margin:10px 0;font-size:13px;color:#525860;"><b>Note:</b> ' + note + '</div>') if note else ''}
        """,
        cta_label="View scenario",
        cta_url=cta_url,
    )
    res = await _send(requester_email, f"[SaloneHCM] Scenario {pretty.lower()} — {scenario_name}", html)
    await _log("scenario_decision", requester_email, scenario_name, res, {
        "scenario_id": scenario_id,
        "decision": decision,
        "company_id": company_id,
    })
    return res


async def send_user_invite(
    invite_email: str,
    invite_name: str,
    inviter_name: str,
    company_name: str,
    invite_token: str,
    role: str = "employee",
    company_id: Optional[str] = None,
) -> dict:
    """Send a magic-link invite to a newly provisioned user."""
    link = f"{FRONTEND_URL}/login?invite={invite_token}" if FRONTEND_URL else f"/login?invite={invite_token}"
    html = _wrap_html(
        title=f"You've been invited to {company_name}",
        body_html=f"""
          <p>Hi {invite_name or 'there'},</p>
          <p><strong>{inviter_name}</strong> has invited you to join <strong>{company_name}</strong> on SaloneHCM as a <strong>{role}</strong>.</p>
          <p>Click the button below to accept your invitation. The link is single-use.</p>
        """,
        cta_label="Accept invitation",
        cta_url=link,
    )
    res = await _send(invite_email, f"[SaloneHCM] You're invited to {company_name}", html)
    await _log("user_invite", invite_email, company_name, res, {
        "role": role,
        "inviter_name": inviter_name,
        "company_id": company_id,
    })
    return res
