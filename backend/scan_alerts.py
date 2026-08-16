"""Fraud alert push — when a payslip QR crosses the unusual-scan threshold
(5+ scans within any 24h window), immediately push every tenant admin.
De-duplicated: at most one alert per payslip per 24h (`payslip_scan_alerts`)."""
import logging
import uuid
from datetime import datetime, timedelta

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.scan_alerts")


def flag_scans(times: list[str]) -> bool:
    """True when 5+ scans fall within ANY sliding 24-hour window."""
    for i in range(len(times) - 4):
        if (datetime.fromisoformat(times[i + 4])
                - datetime.fromisoformat(times[i])) <= timedelta(hours=24):
            return True
    return False


async def check_and_alert(ver: dict):
    """Fire-and-forget after each public scan; must never raise."""
    try:
        vid = ver["id"]
        scans = await db.payslip_scans.find(
            {"verification_id": vid},
            {"_id": 0, "scanned_at": 1}).sort("scanned_at", 1).to_list(5000)
        times = [s["scanned_at"] for s in scans]
        if not flag_scans(times):
            return None
        cutoff = iso(now_utc() - timedelta(hours=24))
        if await db.payslip_scan_alerts.find_one(
                {"verification_id": vid, "created_at": {"$gte": cutoff}}):
            return None  # admins already pinged for this payslip in the last 24h

        from push_service import fanout_to_user
        payload = {
            "title": "Unusual payslip scans",
            "body": (f"{ver.get('employee_name')}'s {ver.get('period')} payslip QR "
                     f"was scanned {len(times)} times — 5+ within 24 hours."),
            "url": f"/payroll?flag={vid}",
            "kind": "payslip_scan_alert",
            "tag": f"scan-alert-{vid}",
        }
        admins = await db.users.find(
            {"company_id": ver.get("company_id"), "role": "admin"},
            {"_id": 0, "id": 1, "email": 1}).to_list(50)
        notified = []
        for a in admins:
            try:
                r = await fanout_to_user(a["id"], payload)
                notified.append({"user_id": a["id"], "ok": True, "sent": r.get("sent", 0)})
            except Exception as e:
                notified.append({"user_id": a["id"], "ok": False, "error": str(e)[:200]})

        alert = {
            "id": str(uuid.uuid4()), "verification_id": vid,
            "company_id": ver.get("company_id"),
            "employee_name": ver.get("employee_name"), "period": ver.get("period"),
            "scan_count": len(times), "notified": notified,
            "created_at": iso(now_utc()),
        }
        await db.payslip_scan_alerts.insert_one(alert)
        alert.pop("_id", None)
        logger.info("Payslip scan fraud alert: %s %s (%s scans, %s admins pinged)",
                    ver.get("employee_name"), ver.get("period"), len(times), len(admins))
        return alert
    except Exception:
        logger.exception("Payslip scan alert failed")
        return None
