"""24h reminder sweeps — interview reminder emails + urgent announcement push nudges."""
import logging
from datetime import timedelta

from apscheduler.triggers.interval import IntervalTrigger

from core import db, now_utc, iso
import push_service

logger = logging.getLogger("salonehcm.reminders")


async def run_interview_reminders() -> int:
    """Email applicants whose interview starts within the next 24h (once per interview)."""
    import email_service
    now = now_utc()
    lo, hi = iso(now), iso(now + timedelta(hours=24))
    apps = await db.job_applications.find({
        "interview.starts_at": {"$gt": lo, "$lte": hi},
        "interview.reminder_sent": {"$ne": True},
    }, {"_id": 0}).to_list(500)
    sent = 0
    for a in apps:
        iv = a["interview"]
        company = await db.companies.find_one(
            {"id": a["company_id"]}, {"_id": 0, "name": 1}) or {}
        await email_service.send_interview_reminder(
            a["email"], a["name"], a["vacancy_title"], iv["date"], iv["time"],
            iv.get("location", ""), company.get("name", "SaloneHCM"), a["company_id"])
        await db.job_applications.update_one({"id": a["id"]}, {"$set": {
            "interview.reminder_sent": True,
            "interview.reminder_sent_at": iso(now)}})
        sent += 1
    if sent:
        logger.info("interview reminders: %d sent", sent)
    return sent


async def run_announcement_reminders() -> int:
    """Push-nudge staff who still haven't read an urgent announcement 24h after posting.
    Exactly one reminder per announcement per employee."""
    now = now_utc()
    cutoff = iso(now - timedelta(hours=24))
    today = iso(now)[:10]
    anns = await db.announcements.find(
        {"priority": "urgent", "created_at": {"$lte": cutoff}}, {"_id": 0}).to_list(500)
    total = 0
    for a in anns:
        if a.get("expires_at") and a["expires_at"] < today:
            continue
        seen = {r["user_id"] async for r in db.announcement_reads.find(
            {"announcement_id": a["id"]}, {"_id": 0, "user_id": 1})}
        reminded = {r["user_id"] async for r in db.announcement_reminders.find(
            {"announcement_id": a["id"]}, {"_id": 0, "user_id": 1})}
        users = await db.users.find(
            {"company_id": a["company_id"], "disabled": {"$ne": True}},
            {"_id": 0, "id": 1}).to_list(2000)
        payload = {"title": "Reminder: urgent announcement",
                   "body": a["title"], "url": "/dashboard",
                   "kind": "announcement_reminder"}
        count = 0
        for u in users:
            if u["id"] in seen or u["id"] in reminded:
                continue
            res = await push_service.fanout_to_user(u["id"], payload)
            await db.announcement_reminders.insert_one({
                "announcement_id": a["id"], "user_id": u["id"],
                "company_id": a["company_id"], "push": res, "sent_at": iso(now)})
            count += 1
        if count:
            await db.announcements.update_one({"id": a["id"]}, {
                "$set": {"reminder_last_at": iso(now)},
                "$inc": {"reminder_count": count}})
            total += count
    if total:
        logger.info("announcement reminders: %d push nudge(s)", total)
    return total


async def _tick():
    try:
        await run_interview_reminders()
    except Exception:
        logger.exception("interview reminder sweep failed")
    try:
        await run_announcement_reminders()
    except Exception:
        logger.exception("announcement reminder sweep failed")


def attach(scheduler) -> None:
    scheduler.add_job(_tick, IntervalTrigger(minutes=15), id="reminder_sweeps",
                      replace_existing=True, max_instances=1, coalesce=True)
    logger.info("Reminder sweeps attached (interview + announcement, every 15 min)")
