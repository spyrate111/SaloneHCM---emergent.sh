"""Scheduled 90/60/30-day contract expiry reminders for tenant HR teams."""
import logging
import uuid
from datetime import date, timedelta
from html import escape

from pymongo.errors import DuplicateKeyError

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.contract_expiry")
MILESTONES = (90, 60, 30)
MILESTONE_GRACE_DAYS = 7
CLAIM_MINUTES = 30
HR_ROLES = ("admin", "superadmin", "hr")
ACTIVE_EMPLOYMENT_STATUSES = ("active", "on_leave")


async def _stage_due_alerts(today) -> None:
    # A short grace window prevents a missed scheduler day from losing a reminder.
    target_days = {}
    for milestone in MILESTONES:
        for grace_days in range(MILESTONE_GRACE_DAYS + 1):
            due_date = (today + timedelta(days=milestone + grace_days)).isoformat()
            target_days[due_date] = milestone

    employee_cursor = db.employees.find(
        {
            "status": {"$in": list(ACTIVE_EMPLOYMENT_STATUSES)},
            "contract_end_date": {"$in": list(target_days)},
        },
        {
            "_id": 0, "id": 1, "company_id": 1, "first_name": 1,
            "last_name": 1, "contract_end_date": 1,
        },
    )
    hr_users_by_company = {}
    async for employee in employee_cursor:
        company_id = employee.get("company_id")
        end_date = employee.get("contract_end_date")
        days_before = target_days.get(end_date)
        if not company_id or days_before is None:
            continue
        if company_id not in hr_users_by_company:
            users = []
            user_cursor = db.users.find(
                {
                    "company_id": company_id,
                    "role": {"$in": list(HR_ROLES)},
                    "disabled": {"$ne": True},
                },
                {"_id": 0, "id": 1, "email": 1, "name": 1},
            )
            async for user in user_cursor:
                users.append(user)
            hr_users_by_company[company_id] = users

        for user in hr_users_by_company[company_id]:
            key = {
                "company_id": company_id,
                "employee_id": employee["id"],
                "contract_end_date": end_date,
                "days_before": days_before,
                "user_id": user["id"],
            }
            existing = await db.contract_expiry_alerts.find_one(key, {"_id": 0})
            if existing:
                # A contract/user that becomes active again can resume an unsent alert.
                if existing.get("status") == "cancelled":
                    await db.contract_expiry_alerts.update_one(
                        {"id": existing["id"], "status": "cancelled"},
                        {
                            "$set": {
                                "status": "pending",
                                "attempts": 0,
                                "created_at": iso(now_utc()),
                            },
                            "$unset": {
                                "cancelled_at": "",
                                "next_attempt_at": "",
                                "last_attempt_at": "",
                                "last_failure": "",
                                "claim_token": "",
                                "claim_expires_at": "",
                            },
                        },
                    )
                continue

            try:
                await db.contract_expiry_alerts.insert_one({
                    **key,
                    "id": str(uuid.uuid4()),
                    "status": "pending",
                    "attempts": 0,
                    "created_at": iso(now_utc()),
                })
            except DuplicateKeyError:
                # Another scheduler process staged this same milestone first.
                continue


def _pending_alert_query(now_iso: str) -> dict:
    return {
        "$or": [
            {
                "status": "pending",
                "$or": [
                    {"next_attempt_at": {"$exists": False}},
                    {"next_attempt_at": {"$lte": now_iso}},
                ],
            },
            {
                "status": "processing",
                "claim_expires_at": {"$lte": now_iso},
            },
        ],
    }


def _claim_filter(alert: dict, now_iso: str) -> dict:
    base = {"id": alert["id"], "company_id": alert["company_id"]}
    if alert.get("status") == "processing":
        return {
            **base,
            "status": "processing",
            "claim_expires_at": {"$lte": now_iso},
        }
    return {
        **base,
        "status": "pending",
        "$or": [
            {"next_attempt_at": {"$exists": False}},
            {"next_attempt_at": {"$lte": now_iso}},
        ],
    }


async def _deliver_pending_alerts() -> dict:
    now_iso = iso(now_utc())
    pending_cursor = db.contract_expiry_alerts.find(
        _pending_alert_query(now_iso), {"_id": 0},
    )

    from email_service import is_configured as email_is_configured, _send as send_email
    from push_service import fanout_to_user

    can_email = email_is_configured()
    pending_count = delivered = cancelled = 0
    async for alert in pending_cursor:
        pending_count += 1
        claim_token = uuid.uuid4().hex
        claimed = await db.contract_expiry_alerts.update_one(
            _claim_filter(alert, iso(now_utc())),
            {
                "$set": {
                    "status": "processing",
                    "claim_token": claim_token,
                    "claim_expires_at": iso(now_utc() + timedelta(minutes=CLAIM_MINUTES)),
                },
            },
        )
        if claimed.modified_count != 1:
            continue

        end_date = alert.get("contract_end_date", "")
        try:
            contract_expired = date.fromisoformat(end_date) <= now_utc().date()
        except (TypeError, ValueError):
            contract_expired = True
            logger.warning("Cancelling contract alert %s with an invalid end date", alert["id"])

        tf = {"company_id": alert["company_id"]}
        employee = None if contract_expired else await db.employees.find_one(
            {
                "id": alert["employee_id"],
                **tf,
                "status": {"$in": list(ACTIVE_EMPLOYMENT_STATUSES)},
                "contract_end_date": end_date,
            },
            {"_id": 0, "id": 1, "first_name": 1, "last_name": 1},
        )
        user = await db.users.find_one(
            {
                "id": alert["user_id"],
                **tf,
                "role": {"$in": list(HR_ROLES)},
                "disabled": {"$ne": True},
            },
            {"_id": 0, "id": 1, "email": 1, "name": 1},
        )
        if not employee or not user:
            result = await db.contract_expiry_alerts.update_one(
                {
                    "id": alert["id"],
                    "company_id": alert["company_id"],
                    "status": "processing",
                    "claim_token": claim_token,
                },
                {
                    "$set": {"status": "cancelled", "cancelled_at": iso(now_utc())},
                    "$unset": {"claim_token": "", "claim_expires_at": ""},
                },
            )
            if result.matched_count:
                cancelled += 1
            continue

        name = (
            f'{employee.get("first_name", "")} {employee.get("last_name", "")}'.strip()
            or "An employee"
        )
        days = alert["days_before"]
        title = f"Contract expiry reminder ({days}-day)"
        body = f"{name}'s contract ends on {end_date}."
        push = {"sent": 0}
        try:
            push = await fanout_to_user(user["id"], {
                "title": title,
                "body": body,
                "url": f"/employees/{alert['employee_id']}",
                "kind": "contract_expiry",
                "tag": f"contract-{alert['employee_id']}-{days}",
            }) or {"sent": 0}
        except Exception:
            logger.exception("Contract expiry push failed for user %s", user["id"])

        sent = bool(push.get("sent"))
        if not sent and can_email and user.get("email"):
            html = (
                f"<p>{escape(name)}'s contract ends on "
                f"<strong>{escape(end_date)}</strong> "
                f"(the scheduled {days}-day reminder).</p>"
                f"<p>Review the employee record in SaloneHCM and decide whether to renew or start offboarding.</p>"
            )
            try:
                result = await send_email(user["email"], title, html)
                sent = bool(result and result.get("ok"))
            except Exception:
                logger.exception("Contract expiry email failed for user %s", user["id"])

        attempt = int(alert.get("attempts", 0)) + 1
        update = {
            "last_attempt_at": iso(now_utc()),
            "last_push_sent": push.get("sent", 0),
        }
        update_ops = {
            "$set": update,
            "$inc": {"attempts": 1},
            "$unset": {"claim_token": "", "claim_expires_at": ""},
        }
        if sent:
            update.update({"status": "sent", "sent_at": iso(now_utc())})
            update_ops["$unset"].update({
                "next_attempt_at": "",
                "last_failure": "",
            })
        else:
            # Scheduler retries are capped at once every three days after repeated failures.
            retry_hours = min(24 * (2 ** (attempt - 1)), 72)
            update.update({
                "status": "pending",
                "next_attempt_at": iso(now_utc() + timedelta(hours=retry_hours)),
                "last_failure": "No push or email delivery accepted the reminder",
            })
        result = await db.contract_expiry_alerts.update_one(
            {
                "id": alert["id"],
                "company_id": alert["company_id"],
                "status": "processing",
                "claim_token": claim_token,
            },
            update_ops,
        )
        if result.matched_count and sent:
            delivered += 1

    return {
        "pending": pending_count,
        "delivered": delivered,
        "cancelled": cancelled,
    }


async def run_contract_expiry_alerts() -> dict:
    """Create and deliver each 90/60/30-day reminder once per employee and HR user."""
    today = now_utc().date()
    try:
        await _stage_due_alerts(today)
        return await _deliver_pending_alerts()
    except Exception:
        logger.exception("Contract expiry reminder run failed")
        raise


def attach(scheduler) -> None:
    from apscheduler.triggers.cron import CronTrigger

    scheduler.add_job(
        run_contract_expiry_alerts,
        CronTrigger(hour=8, minute=0, second=0),
        id="contract_expiry_alerts",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Contract expiry alerts attached (08:00 UTC daily)")
