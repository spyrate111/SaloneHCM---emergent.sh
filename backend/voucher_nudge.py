"""Voucher deadline nudges — cron-fired reminders (SMS + email) to branch
supervisors when their monthly payroll voucher is still missing and the
payroll cut-off deadline is imminent.

Trigger windows (hours before the cut-off day at midnight UTC):
    - 72h out  (early nudge)
    - 24h out  (final nudge)

Each nudge is idempotent per (company, branch, period, window) so a
supervisor never receives duplicates in one window.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.triggers.interval import IntervalTrigger

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.voucher_nudge")

# Windows: (hours_before_deadline, tolerance_hours, tag)
WINDOWS = [
    (72, 3, "T-72h"),
    (24, 3, "T-24h"),
]

FRONTEND_URL = os.environ.get("FRONTEND_URL", "")


def _current_period(dt: datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"


def _deadline_for(company: dict, dt: datetime) -> Optional[datetime]:
    """Deadline = midnight UTC on the tenant's payroll cutoff day of the
    current month. Returns None if cutoff not enabled."""
    if not company.get("payroll_cutoff_enabled"):
        return None
    day = int(company.get("payroll_cutoff_day", 25))
    try:
        return dt.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        return None  # e.g. Feb 30 — skip


def _hours_between(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 3600.0


def _sms_body(branch_name: str, period: str, hours: int) -> str:
    return (
        f"SaloneHCM: Reminder — the {branch_name} payroll voucher for {period} "
        f"is still missing and the MoF cut-off is in ~{hours}h. "
        f"Please submit today: {FRONTEND_URL}/vouchers"
    ).strip()


def _email_html(admin_name: str, branch_name: str, branch_code: str, period: str, hours: int) -> str:
    from email_service import _wrap_html
    link = f"{FRONTEND_URL}/vouchers" if FRONTEND_URL else "/vouchers"
    body = f"""
      <p>Hi {admin_name or 'there'},</p>
      <p>This is a friendly reminder that the payroll voucher for
         <strong>{branch_name}</strong> ({branch_code}) for period
         <strong>{period}</strong> has <strong>not been submitted yet</strong>.</p>
      <p>The Ministry of Finance cut-off is in <strong>~{hours} hours</strong>.
         Miss it and the branch's voucher will not make the current MoF pack.</p>
      <p style="color:#525860;font-size:12px;">You are receiving this because you are
         listed as the branch supervisor for {branch_name} in SaloneHCM.</p>
    """
    return _wrap_html(
        title=f"Voucher due in ~{hours}h — {branch_name} · {period}",
        body_html=body,
        cta_label="Submit voucher now",
        cta_url=link,
    )


async def _fire_nudge(company: dict, branch: dict, period: str, hours: int, tag: str) -> dict:
    """Send SMS + Email to the branch supervisor. Returns a status dict."""
    sup_id = branch.get("supervisor_user_id")
    if not sup_id:
        return {"skipped": "no supervisor assigned"}
    sup = await db.users.find_one(
        {"id": sup_id, "company_id": company["id"]},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "phone": 1},
    )
    if not sup:
        return {"skipped": "supervisor user not found"}

    branch_name = branch.get("name", "")
    branch_code = branch.get("code", "")
    channels = {"sms": None, "email": None}

    # SMS
    from sms import is_configured as sms_ok, normalize_phone, send_one
    phone = normalize_phone(sup.get("phone"))
    if sms_ok() and phone:
        r = await send_one(phone, _sms_body(branch_name, period, hours))
        channels["sms"] = {"ok": r.get("ok"), "sid": r.get("sid"), "phone": phone,
                           "error": r.get("error")}
    else:
        channels["sms"] = {"ok": False, "phone": phone,
                           "error": "sms not configured" if not sms_ok() else "no valid phone"}

    # Email
    from email_service import is_configured as email_ok, _send as _email_send
    if email_ok() and sup.get("email"):
        subject = f"[SaloneHCM] Voucher due in ~{hours}h — {branch_name} · {period}"
        html = _email_html(sup.get("name"), branch_name, branch_code, period, hours)
        r = await _email_send(sup["email"], subject, html)
        channels["email"] = {"ok": r.get("ok"), "id": r.get("id"),
                             "to": sup["email"], "error": r.get("error")}
    else:
        channels["email"] = {"ok": False, "to": sup.get("email"),
                             "error": "email not configured" if not email_ok() else "no email address"}

    return {"channels": channels, "supervisor_email": sup.get("email"),
            "supervisor_name": sup.get("name")}


async def _process_tenant(company: dict, now: datetime) -> int:
    """Evaluate every branch of one tenant for nudges. Returns count sent."""
    deadline = _deadline_for(company, now)
    if not deadline:
        return 0
    period = _current_period(now)
    hours_left = _hours_between(now, deadline)

    # Which window are we in? (must be within tolerance of the target)
    matches = []
    for hrs_target, tolerance, tag in WINDOWS:
        # Fire only when we're approaching the deadline (positive hours_left).
        if abs(hours_left - hrs_target) <= tolerance and hours_left > 0:
            matches.append((hrs_target, tag))
    if not matches:
        return 0

    branches = await db.branches.find(
        {"company_id": company["id"]}, {"_id": 0}).to_list(500)
    if not branches:
        return 0

    # Which branches have already submitted (non-draft) for this period?
    submitted = await db.payroll_vouchers.find(
        {"company_id": company["id"], "period": period,
         "status": {"$ne": "draft"}},
        {"_id": 0, "branch_id": 1}).to_list(1000)
    submitted_bids = {v["branch_id"] for v in submitted}

    sent = 0
    for hrs_target, tag in matches:
        for br in branches:
            if br["id"] in submitted_bids:
                continue
            # Idempotency guard — one nudge per (company, branch, period, window)
            existing = await db.voucher_nudges.find_one({
                "company_id": company["id"], "branch_id": br["id"],
                "period": period, "window": tag,
            }, {"_id": 1})
            if existing:
                continue
            res = await _fire_nudge(company, br, period, hrs_target, tag)
            await db.voucher_nudges.insert_one({
                "company_id": company["id"], "branch_id": br["id"],
                "branch_name": br.get("name"), "branch_code": br.get("code"),
                "period": period, "window": tag, "hours_before": hrs_target,
                "supervisor_user_id": br.get("supervisor_user_id"),
                "supervisor_email": res.get("supervisor_email"),
                "supervisor_name": res.get("supervisor_name"),
                "channels": res.get("channels", {}),
                "skipped": res.get("skipped"),
                "sent_at": iso(now),
            })
            if not res.get("skipped"):
                sent += 1
    return sent


async def _tick() -> None:
    """Called by the scheduler every 30 minutes."""
    now = now_utc()
    companies = await db.companies.find(
        {"payroll_cutoff_enabled": True},
        {"_id": 0, "id": 1, "name": 1, "payroll_cutoff_day": 1,
         "payroll_cutoff_enabled": 1}).to_list(500)
    total = 0
    for c in companies:
        try:
            total += await _process_tenant(c, now)
        except Exception:
            logger.exception("voucher_nudge tick failed for company %s", c.get("id"))
    if total:
        logger.info("voucher_nudge: fired %d reminder(s)", total)


async def run_for_tenant(company_id: str, period: Optional[str] = None,
                        window: str = "manual") -> dict:
    """Manual nudge — admin button on the Vouchers page. Fires to every
    missing branch immediately, ignoring the deadline window checks but
    still respecting the idempotency guard for the given period+window tag."""
    now = now_utc()
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        return {"ok": False, "error": "company not found", "sent": 0}
    period = period or _current_period(now)
    branches = await db.branches.find({"company_id": company_id}, {"_id": 0}).to_list(500)
    submitted = await db.payroll_vouchers.find(
        {"company_id": company_id, "period": period, "status": {"$ne": "draft"}},
        {"_id": 0, "branch_id": 1}).to_list(1000)
    submitted_bids = {v["branch_id"] for v in submitted}
    results = []
    deadline = _deadline_for(company, now)
    hours = int(_hours_between(now, deadline)) if deadline else 0
    for br in branches:
        if br["id"] in submitted_bids:
            continue
        existing = await db.voucher_nudges.find_one({
            "company_id": company_id, "branch_id": br["id"],
            "period": period, "window": window,
        }, {"_id": 1})
        if existing:
            results.append({"branch": br["name"], "status": "already_sent"})
            continue
        res = await _fire_nudge(company, br, period, max(hours, 0), window)
        await db.voucher_nudges.insert_one({
            "company_id": company_id, "branch_id": br["id"],
            "branch_name": br.get("name"), "branch_code": br.get("code"),
            "period": period, "window": window, "hours_before": max(hours, 0),
            "supervisor_user_id": br.get("supervisor_user_id"),
            "supervisor_email": res.get("supervisor_email"),
            "supervisor_name": res.get("supervisor_name"),
            "channels": res.get("channels", {}),
            "skipped": res.get("skipped"),
            "sent_at": iso(now),
        })
        results.append({
            "branch": br["name"],
            "status": "skipped" if res.get("skipped") else "sent",
            "reason": res.get("skipped"),
            "channels": res.get("channels", {}),
        })
    return {"ok": True, "period": period, "window": window, "results": results,
            "sent": sum(1 for r in results if r["status"] == "sent")}


def attach(scheduler) -> None:
    """Register the tick job on the shared APScheduler. Fires every 30 minutes."""
    scheduler.add_job(_tick, IntervalTrigger(minutes=30),
                      id="voucher_nudge", replace_existing=True,
                      max_instances=1, coalesce=True)
    logger.info("Voucher nudge scheduler attached (every 30 min)")
