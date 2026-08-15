"""Out-of-zone punch alerts.

When a GPS punch lands outside its branch geofence:
  - branch supervisor  → web push + SMS (they must act now)
  - tenant admins      → web push only (no SMS)
An active snooze rule (approved field assignment) suppresses ALL channels;
the alert is still logged with snoozed=True + the reason, for audit.
Every alert is logged to `ooz_alerts`; a daily 18:00 UTC email digest
summarises the day's NON-SNOOZED out-of-zone punches for tenant admins
(idempotent per company per day via `ooz_digests`).
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.ooz")


def _fmt_time(iso_ts: str) -> str:
    try:
        return datetime.fromisoformat(iso_ts).strftime("%H:%M UTC")
    except Exception:
        return iso_ts


def _sms_body(punch: dict) -> str:
    return (f"SaloneHCM ALERT: {punch['employee_name']} clocked "
            f"{punch['kind'].upper()} {int(punch['distance_from_branch_m'])}m outside the "
            f"{punch.get('branch_name') or 'branch'} geofence at {_fmt_time(punch['clocked_at'])}. "
            f"Review the team map in the app.")


def _push_payload(punch: dict) -> dict:
    return {
        "title": "Out-of-zone punch",
        "body": (f"{punch['employee_name']} clocked {punch['kind'].upper()} "
                 f"{int(punch['distance_from_branch_m'])}m outside {punch.get('branch_name') or 'the branch'} "
                 f"at {_fmt_time(punch['clocked_at'])}"),
        "url": "/m/clock",
        "kind": "ooz_alert",
        "tag": f"ooz-{punch['id']}",
    }


def _base_alert(punch: dict, branch: Optional[dict], company_id: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "punch_id": punch["id"],
        "employee_id": punch.get("employee_id"),
        "employee_name": punch.get("employee_name"),
        "branch_id": punch.get("branch_id"),
        "branch_name": punch.get("branch_name"),
        "kind": punch.get("kind"),
        "clocked_at": punch.get("clocked_at"),
        "date": punch.get("date"),
        "distance_from_branch_m": punch.get("distance_from_branch_m"),
        "geofence_radius_m": (branch or {}).get("geofence_radius_m") or 250.0,
        "created_at": iso(now_utc()),
    }


async def fire_out_of_zone_alert(punch: dict, branch: Optional[dict], company_id: str,
                                 snooze: Optional[dict] = None) -> dict:
    """Fire-and-forget: must NEVER raise into the punch endpoint."""
    try:
        if snooze:
            alert = {**_base_alert(punch, branch, company_id),
                     "snoozed": True,
                     "snooze_id": snooze.get("id"),
                     "snooze_reason": snooze.get("reason"),
                     "channels": {"suppressed": "active snooze rule"}}
            await db.ooz_alerts.insert_one(alert)
            alert.pop("_id", None)
            logger.info("OOZ alert SNOOZED: %s (%s)", punch.get("employee_name"),
                        snooze.get("reason"))
            return alert

        channels = {"supervisor_push": None, "supervisor_sms": None, "admin_push": []}
        from push_service import fanout_to_user

        # --- branch supervisor: push + SMS -------------------------------
        sup = None
        sup_id = (branch or {}).get("supervisor_user_id")
        if sup_id:
            sup = await db.users.find_one(
                {"id": sup_id, "company_id": company_id},
                {"_id": 0, "id": 1, "email": 1, "name": 1, "phone": 1})
        if sup:
            try:
                r = await fanout_to_user(sup["id"], _push_payload(punch))
                channels["supervisor_push"] = {"ok": True, **{k: r.get(k) for k in ("sent", "failed") if k in r}}
            except Exception as e:
                channels["supervisor_push"] = {"ok": False, "error": str(e)[:200]}
            from sms import is_configured as sms_ok, normalize_phone, send_one
            phone = normalize_phone(sup.get("phone"))
            if sms_ok() and phone:
                r = await send_one(phone, _sms_body(punch))
                channels["supervisor_sms"] = {"ok": r.get("ok"), "sid": r.get("sid"),
                                              "phone": phone, "error": r.get("error")}
            else:
                channels["supervisor_sms"] = {
                    "ok": False, "phone": phone,
                    "error": "sms not configured" if not sms_ok() else "no valid phone"}
        else:
            channels["supervisor_push"] = {"ok": False, "error": "no supervisor assigned"}
            channels["supervisor_sms"] = {"ok": False, "error": "no supervisor assigned"}

        # --- tenant admins: push only (no SMS) ----------------------------
        admins = await db.users.find(
            {"company_id": company_id, "role": "admin"},
            {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(50)
        for a in admins:
            if sup and a["id"] == sup["id"]:
                continue  # already pushed as supervisor
            try:
                await fanout_to_user(a["id"], _push_payload(punch))
                channels["admin_push"].append({"user_id": a["id"], "ok": True})
            except Exception as e:
                channels["admin_push"].append({"user_id": a["id"], "ok": False, "error": str(e)[:200]})

        alert = {**_base_alert(punch, branch, company_id),
                 "snoozed": False, "channels": channels}
        await db.ooz_alerts.insert_one(alert)
        alert.pop("_id", None)
        logger.info("OOZ alert fired: %s %sm out at %s", alert["employee_name"],
                    int(alert["distance_from_branch_m"] or 0), alert["branch_name"])
        return alert
    except Exception:
        logger.exception("OOZ alert failed (punch still recorded)")
        return {"ok": False}


# ---------------------------------------------------------------------------
# Daily 18:00 UTC end-of-day email digest for tenant admins
# ---------------------------------------------------------------------------
def _digest_html(admin_name: str, company_name: str, day: str, rows: list[dict]) -> str:
    trs = "".join(
        f"<tr>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2DFD6'>{r['employee_name']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2DFD6;text-transform:uppercase'>{r['kind']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2DFD6'>{_fmt_time(r['clocked_at'])}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2DFD6'>{r.get('branch_name') or '—'}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2DFD6;color:#B03A2E;font-weight:bold'>"
        f"{int(r.get('distance_from_branch_m') or 0)}m out</td>"
        f"</tr>"
        for r in rows
    )
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#1A1C1E">
      <div style="background:#0A4A1E;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0">
        <h2 style="margin:0;font-size:18px">Out-of-zone punch digest — {day}</h2>
        <p style="margin:6px 0 0;font-size:12px;opacity:.85">{company_name} · SaloneHCM</p>
      </div>
      <div style="border:1px solid #E2DFD6;border-top:none;padding:20px 24px;border-radius:0 0 8px 8px">
        <p style="font-size:13px">Hello {admin_name or 'Admin'},</p>
        <p style="font-size:13px">{len(rows)} punch{'es were' if len(rows) != 1 else ' was'} recorded
        outside a branch geofence today (snoozed field assignments excluded):</p>
        <table style="border-collapse:collapse;width:100%;font-size:12px">
          <tr style="background:#F7F6F2;text-align:left">
            <th style="padding:8px 12px">Employee</th><th style="padding:8px 12px">Kind</th>
            <th style="padding:8px 12px">Time</th><th style="padding:8px 12px">Branch</th>
            <th style="padding:8px 12px">Distance</th>
          </tr>
          {trs}
        </table>
        <p style="font-size:12px;color:#525860;margin-top:16px">
          Open the GPS punch map in SaloneHCM (Attendance page, or the mobile Clock screen)
          for the full picture. Branch geofence radii can be adjusted in Branch settings.
        </p>
      </div>
    </div>
    """


async def _digest_for_company(company: dict, day: str) -> dict:
    already = await db.ooz_digests.find_one({"company_id": company["id"], "date": day})
    if already:
        return {"company_id": company["id"], "skipped": "already sent"}
    rows = await db.ooz_alerts.find(
        {"company_id": company["id"], "date": day, "snoozed": {"$ne": True}},
        {"_id": 0}).sort("clocked_at", 1).to_list(500)
    if not rows:
        return {"company_id": company["id"], "skipped": "no out-of-zone punches"}

    from email_service import is_configured as email_ok, _send as _email_send
    sent = []
    admins = await db.users.find(
        {"company_id": company["id"], "role": "admin"},
        {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(50)
    for a in admins:
        if not (email_ok() and a.get("email")):
            sent.append({"to": a.get("email"), "ok": False, "error": "email not configured"})
            continue
        subject = f"[SaloneHCM] {len(rows)} out-of-zone punch{'es' if len(rows) != 1 else ''} today — {company.get('name')}"
        r = await _email_send(a["email"], subject, _digest_html(a.get("name"), company.get("name", ""), day, rows))
        sent.append({"to": a["email"], "ok": r.get("ok"), "id": r.get("id"), "error": r.get("error")})

    await db.ooz_digests.insert_one({
        "id": str(uuid.uuid4()), "company_id": company["id"], "date": day,
        "alert_count": len(rows), "recipients": sent, "created_at": iso(now_utc()),
    })
    return {"company_id": company["id"], "alerts": len(rows), "recipients": sent}


async def send_daily_digest() -> list[dict]:
    day = now_utc().strftime("%Y-%m-%d")
    out = []
    company_ids = await db.ooz_alerts.distinct(
        "company_id", {"date": day, "snoozed": {"$ne": True}})
    for cid in company_ids:
        company = await db.companies.find_one({"id": cid}, {"_id": 0})
        if company:
            try:
                out.append(await _digest_for_company(company, day))
            except Exception:
                logger.exception("OOZ digest failed for company %s", cid)
    return out


async def run_digest_now(company_id: str) -> dict:
    """Manual trigger (admin endpoint / tests) — respects per-day idempotency."""
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        return {"ok": False, "error": "company not found"}
    return await _digest_for_company(company, now_utc().strftime("%Y-%m-%d"))


def attach(scheduler) -> None:
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(send_daily_digest, CronTrigger(hour=18, minute=0, second=0),
                      id="ooz_daily_digest", replace_existing=True,
                      max_instances=1, coalesce=True)
    logger.info("Out-of-zone digest scheduler attached (18:00 UTC daily)")
