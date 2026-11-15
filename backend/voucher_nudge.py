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


async def _fire_nudge(company: dict, branch: dict, period: str, hours: int,
                      tag: str, sms: bool = True, email: bool = True) -> dict:
    """Send a nudge to the branch supervisor. Any channel set to False is skipped.
    Returns a status dict recording every attempted channel."""
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

    # SMS — point-in-time (72h + 24h). Skipped when sms=False.
    if sms:
        from sms import is_configured as sms_ok, normalize_phone, send_one
        phone = normalize_phone(sup.get("phone"))
        if sms_ok() and phone:
            r = await send_one(phone, _sms_body(branch_name, period, hours))
            channels["sms"] = {"ok": r.get("ok"), "sid": r.get("sid"), "phone": phone,
                               "error": r.get("error")}
        else:
            channels["sms"] = {"ok": False, "phone": phone,
                               "error": "sms not configured" if not sms_ok() else "no valid phone"}
    else:
        channels["sms"] = {"ok": False, "error": "sms suppressed (digest mode)"}

    # Email — either send now (manual button) or defer to the 06:00 UTC digest
    if email:
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
    else:
        channels["email"] = {"ok": False, "to": sup.get("email"),
                             "error": "deferred to daily digest"}

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
            res = await _fire_nudge(company, br, period, hrs_target, tag,
                                     sms=True, email=False)  # SMS-only tick
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
    """Called by the scheduler every 30 minutes. SMS-only — email nudges are
    rolled into the daily 06:00 UTC digest so supervisors get one summary,
    not one email per branch per window."""
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
        logger.info("voucher_nudge: fired %d SMS reminder(s)", total)


def _digest_email_html(supervisor_name: str, rows: list[dict], deadline_hours: int) -> str:
    """Build the daily digest body — one summary email listing every branch
    the supervisor still needs to submit a voucher for."""
    from email_service import _wrap_html
    link = f"{FRONTEND_URL}/vouchers" if FRONTEND_URL else "/vouchers"
    row_html = "".join(
        f'<tr>'
        f'<td style="padding:8px 10px;border-bottom:1px solid #E2DFD6;"><b>{r["branch_name"]}</b>'
        f'<div style="font-size:11px;color:#686D76;">{r.get("branch_code","")}</div></td>'
        f'<td style="padding:8px 10px;border-bottom:1px solid #E2DFD6;font-family:monospace;">{r["period"]}</td>'
        f'<td style="padding:8px 10px;border-bottom:1px solid #E2DFD6;text-align:right;color:#8B6A14;font-weight:600;">~{r.get("hours_left", deadline_hours)}h</td>'
        f'</tr>'
        for r in rows
    )
    urgency = ("&lt;24h" if deadline_hours <= 24 else
               "&lt;72h" if deadline_hours <= 72 else
               f"~{deadline_hours}h")
    body = f"""
      <p>Good morning {supervisor_name or 'there'},</p>
      <p>You are the branch supervisor for <b>{len(rows)}</b> office{'s' if len(rows) != 1 else ''}
         that still <b>have not submitted a payroll voucher</b> and the Ministry of Finance cut-off is
         approaching ({urgency} away). Please submit today.</p>
      <table role="presentation" style="width:100%;border-collapse:collapse;margin:14px 0;font-size:13px;">
        <thead>
          <tr style="background:#F7F6F2;text-align:left;">
            <th style="padding:8px 10px;border-bottom:2px solid #E2DFD6;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#525860;">Branch</th>
            <th style="padding:8px 10px;border-bottom:2px solid #E2DFD6;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#525860;">Period</th>
            <th style="padding:8px 10px;border-bottom:2px solid #E2DFD6;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#525860;text-align:right;">Time left</th>
          </tr>
        </thead>
        <tbody>{row_html}</tbody>
      </table>
      <p style="color:#525860;font-size:12px;">This is your single daily summary — SaloneHCM will not
         send another email today. Urgent SMS reminders still fire at 72h and 24h before the cut-off.</p>
    """
    return _wrap_html(
        title=f"{len(rows)} voucher{'s' if len(rows) != 1 else ''} still due — {urgency} left",
        body_html=body,
        cta_label="Open vouchers",
        cta_url=link,
    )


async def _send_daily_digest() -> None:
    """06:00 UTC job — for every gov tenant with cutoff enabled, group missing
    branches by supervisor and send one consolidated email each. Skipped
    entirely when the deadline is more than 7 days out (too early to matter)
    or already past (post-cutoff nudges never help)."""
    from email_service import is_configured as email_ok, _send as _email_send
    if not email_ok():
        logger.info("voucher_nudge digest: email not configured — skip")
        return

    now = now_utc()
    companies = await db.companies.find(
        {"payroll_cutoff_enabled": True},
        {"_id": 0, "id": 1, "name": 1, "payroll_cutoff_day": 1,
         "payroll_cutoff_enabled": 1}).to_list(500)

    sent_total = 0
    for company in companies:
        deadline = _deadline_for(company, now)
        if not deadline:
            continue
        hours_left = _hours_between(now, deadline)
        if hours_left <= 0 or hours_left > 24 * 7:
            continue  # too late or too early

        period = _current_period(now)
        branches = await db.branches.find(
            {"company_id": company["id"]}, {"_id": 0}).to_list(500)
        if not branches:
            continue
        submitted = await db.payroll_vouchers.find(
            {"company_id": company["id"], "period": period,
             "status": {"$ne": "draft"}},
            {"_id": 0, "branch_id": 1}).to_list(1000)
        submitted_bids = {v["branch_id"] for v in submitted}

        # Group missing branches by supervisor
        by_sup: dict[str, dict] = {}
        for br in branches:
            if br["id"] in submitted_bids:
                continue
            sup_id = br.get("supervisor_user_id")
            if not sup_id:
                continue
            by_sup.setdefault(sup_id, {"branches": []})["branches"].append(br)

        for sup_id, bundle in by_sup.items():
            sup = await db.users.find_one(
                {"id": sup_id, "company_id": company["id"]},
                {"_id": 0, "id": 1, "email": 1, "name": 1})
            if not sup or not sup.get("email"):
                continue

            # Idempotency — one digest per (supervisor, period, day)
            day_key = now.strftime("%Y-%m-%d")
            existing = await db.voucher_nudge_digests.find_one({
                "company_id": company["id"], "supervisor_user_id": sup_id,
                "period": period, "day": day_key}, {"_id": 1})
            if existing:
                continue

            rows = [{
                "branch_id": br["id"],
                "branch_name": br.get("name"),
                "branch_code": br.get("code"),
                "period": period,
                "hours_left": max(0, int(hours_left)),
            } for br in bundle["branches"]]

            subject = (f"[SaloneHCM] {len(rows)} voucher"
                       f"{'s' if len(rows) != 1 else ''} still due — MoF cut-off in "
                       f"~{int(hours_left)}h")
            html = _digest_email_html(sup.get("name"), rows, int(hours_left))
            res = await _email_send(sup["email"], subject, html)
            await db.voucher_nudge_digests.insert_one({
                "company_id": company["id"],
                "supervisor_user_id": sup_id,
                "supervisor_email": sup.get("email"),
                "supervisor_name": sup.get("name"),
                "period": period, "day": day_key,
                "branch_count": len(rows),
                "branches": [{"name": b["branch_name"], "code": b["branch_code"]} for b in rows],
                "hours_left": int(hours_left),
                "email_ok": bool(res.get("ok")),
                "email_id": res.get("id"),
                "email_error": res.get("error"),
                "sent_at": iso(now),
            })
            if res.get("ok"):
                sent_total += 1

    if sent_total:
        logger.info("voucher_nudge daily digest: sent %d supervisor summar(y|ies)", sent_total)


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


async def run_digest_now(company_id: Optional[str] = None) -> dict:
    """Manual trigger for the daily digest — used by the admin 'Send digest now'
    button and by tests. When `company_id` is provided we only process that
    tenant; otherwise we process every enabled tenant, exactly like the 06:00
    UTC cron does."""
    from apscheduler.util import undefined  # noqa: F401 — sanity
    # Snapshot digest counter before and after
    before = await db.voucher_nudge_digests.count_documents({})
    if company_id:
        # Temporarily narrow to a single tenant by monkey-patching the query
        # in the cron; simplest is to just reuse the cron with a filter, but
        # to keep the cron logic single-source we clone the loop here.
        from apscheduler.util import undefined  # noqa
        # Reimplement scoped to one tenant so tests + admin button work.
        from email_service import is_configured as email_ok, _send as _email_send
        if not email_ok():
            return {"ok": False, "error": "email not configured", "sent": 0}
        now = now_utc()
        company = await db.companies.find_one({"id": company_id}, {"_id": 0})
        if not company or not company.get("payroll_cutoff_enabled"):
            return {"ok": False, "error": "cutoff not enabled for this tenant", "sent": 0}
        deadline = _deadline_for(company, now)
        if not deadline:
            return {"ok": True, "sent": 0, "reason": "no deadline computable"}
        hours_left = _hours_between(now, deadline)
        period = _current_period(now)
        branches = await db.branches.find(
            {"company_id": company["id"]}, {"_id": 0}).to_list(500)
        submitted = await db.payroll_vouchers.find(
            {"company_id": company["id"], "period": period,
             "status": {"$ne": "draft"}}, {"_id": 0, "branch_id": 1}).to_list(1000)
        submitted_bids = {v["branch_id"] for v in submitted}
        by_sup: dict[str, list] = {}
        for br in branches:
            if br["id"] in submitted_bids:
                continue
            sid = br.get("supervisor_user_id")
            if not sid:
                continue
            by_sup.setdefault(sid, []).append(br)
        sent = 0
        for sid, brs in by_sup.items():
            sup = await db.users.find_one({"id": sid, "company_id": company["id"]},
                                          {"_id": 0, "email": 1, "name": 1})
            if not sup or not sup.get("email"):
                continue
            day_key = now.strftime("%Y-%m-%d")
            if await db.voucher_nudge_digests.find_one({
                "company_id": company_id, "supervisor_user_id": sid,
                "period": period, "day": day_key}, {"_id": 1}):
                continue
            rows = [{"branch_id": b["id"], "branch_name": b.get("name"),
                     "branch_code": b.get("code"), "period": period,
                     "hours_left": max(0, int(hours_left))} for b in brs]
            subject = (f"[SaloneHCM] {len(rows)} voucher"
                       f"{'s' if len(rows) != 1 else ''} still due — MoF cut-off in "
                       f"~{int(hours_left)}h")
            html = _digest_email_html(sup.get("name"), rows, int(hours_left))
            res = await _email_send(sup["email"], subject, html)
            await db.voucher_nudge_digests.insert_one({
                "company_id": company_id,
                "supervisor_user_id": sid,
                "supervisor_email": sup.get("email"),
                "supervisor_name": sup.get("name"),
                "period": period, "day": day_key,
                "branch_count": len(rows),
                "branches": [{"name": b["branch_name"], "code": b["branch_code"]} for b in rows],
                "hours_left": int(hours_left),
                "email_ok": bool(res.get("ok")),
                "email_id": res.get("id"),
                "email_error": res.get("error"),
                "sent_at": iso(now),
            })
            if res.get("ok"):
                sent += 1
        after = await db.voucher_nudge_digests.count_documents({})
        return {"ok": True, "sent": sent, "supervisors_targeted": len(by_sup),
                "digests_new": after - before, "hours_left": int(hours_left),
                "period": period}
    else:
        await _send_daily_digest()
        after = await db.voucher_nudge_digests.count_documents({})
        return {"ok": True, "digests_new": after - before}


def attach(scheduler) -> None:
    """Register the tick + daily digest jobs on the shared APScheduler.
    Tick fires every 30 minutes (SMS-only). Daily digest fires 06:00 UTC."""
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(_tick, IntervalTrigger(minutes=30),
                      id="voucher_nudge", replace_existing=True,
                      max_instances=1, coalesce=True)
    scheduler.add_job(_send_daily_digest, CronTrigger(hour=6, minute=0, second=0),
                      id="voucher_nudge_daily_digest", replace_existing=True,
                      max_instances=1, coalesce=True)
    logger.info("Voucher nudge scheduler attached (SMS tick every 30 min · email digest 06:00 UTC)")
