"""Weekly training reminders — Monday 09:00 UTC web push to every staff member
with unfinished walkthrough videos, worded in the language they last used in
the Training Center. Push only (no SMS/email). Idempotent per user per ISO week
via `training_reminders`."""
import logging
import uuid

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.training_reminders")

MESSAGES = {
    "en": ("Training reminder",
           "You have {n} training video(s) left — just a few minutes each. Open the Training Center to finish up."),
    "krio": ("Trenin rimanda",
             "Yu gɛt {n} trenin vidio lɛf — na smɔl tɛm nɔmɔ fɔ wach dɛn. Opin di Trenin Sɛnta fɔ dɔn dɛn."),
    "mende": ("Gaa hugɔɔ",
              "Bi gaa video {n} lɔ naa — wati kulo mia. Gbɔu Gaa Wumbu bu kɔ bi kpele gbi."),
    "temne": ("Karan kəpon",
              "Ka video ŋa karan {n} po ŋa yi — ka wath tɛmpɛt nomu. Kanthɛ ka Training Center kama pon aŋa."),
}


def _week_key() -> str:
    return now_utc().strftime("%G-W%V")


async def _catalog_total() -> int:
    slugs = await db.marketing_videos.distinct(
        "base_slug", {"category": "training", "lang": "en"})
    return len(slugs)


async def run_for_company(company_id: str, force_lang: str | None = None) -> dict:
    total = await _catalog_total()
    week = _week_key()
    if total == 0:
        return {"week": week, "skipped": "no training catalog"}
    from push_service import fanout_to_user
    users = await db.users.find(
        {"company_id": company_id},
        {"_id": 0, "id": 1, "name": 1, "training_lang": 1}).to_list(2000)
    reminded = skipped_complete = skipped_already = delivered = 0
    for u in users:
        done = len(await db.training_progress.distinct("base_slug", {"user_id": u["id"]}))
        if done >= total:
            skipped_complete += 1
            continue
        if await db.training_reminders.find_one({"user_id": u["id"], "week": week}):
            skipped_already += 1
            continue
        if force_lang in MESSAGES:
            lang = force_lang
        else:
            lang = u.get("training_lang") if u.get("training_lang") in MESSAGES else "en"
        title, body = MESSAGES[lang]
        r = await fanout_to_user(u["id"], {
            "title": title, "body": body.format(n=total - done),
            "url": "/m/training", "kind": "training_reminder",
            "tag": f"training-{week}",
        })
        sent = r.get("sent", 0)
        await db.training_reminders.insert_one({
            "id": str(uuid.uuid4()), "user_id": u["id"], "company_id": company_id,
            "week": week, "lang": lang, "remaining": total - done,
            "push_sent": sent, "created_at": iso(now_utc()),
        })
        reminded += 1
        delivered += 1 if sent else 0
    return {"week": week, "total_videos": total, "reminded": reminded,
            "delivered_to_devices": delivered,
            "lang": force_lang if force_lang in MESSAGES else "per-user",
            "skipped_complete": skipped_complete, "skipped_already": skipped_already}


async def send_weekly_reminders() -> list[dict]:
    out = []
    for cid in await db.users.distinct("company_id"):
        if not cid:
            continue
        try:
            out.append({"company_id": cid, **(await run_for_company(cid))})
        except Exception:
            logger.exception("Training reminder failed for company %s", cid)
    return out


def attach(scheduler) -> None:
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(send_weekly_reminders,
                      CronTrigger(day_of_week="mon", hour=9, minute=0, second=0),
                      id="training_weekly_reminder", replace_existing=True,
                      max_instances=1, coalesce=True)
    logger.info("Training reminder scheduler attached (Mon 09:00 UTC)")
