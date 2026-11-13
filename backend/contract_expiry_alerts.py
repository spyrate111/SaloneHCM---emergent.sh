"""Scheduled 90/60/30-day contract expiry reminders for tenant HR teams."""
import logging
import uuid
from datetime import timedelta
from html import escape

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.contract_expiry")
MILESTONES = (90, 60, 30)
HR_ROLES = ("admin", "superadmin", "hr")


async def _stage_due_alerts(today) -> None:
    target_days = {(today + timedelta(days=days)).isoformat(): days for days in MILESTONES}
    employees = await db.employees.find(
        {"status": "active", "contract_end_date": {"$in": list(target_days)}},
        {"_id": 0, "id": 1, "company_id": 1, "first_name": 1, "last_name": 1,
         "contract_end_date": 1},
    ).to_list(5000)
    hr_users_by_company = {}
    for employee in employees:
        company_id = employee.get("company_id")
        end_date = employee.get("contract_end_date")
        days_before = target_days.get(end_date)
        if not company_id or days_before is None:
            continue
        if company_id not in hr_users_by_company:
            hr_users_by_company[company_id] = await db.users.find(
                {"company_id": company_id, "role": {"$in": list(HR_ROLES)},
                 "disabled": {"$ne": True}},
                {"_id": 0, "id": 1, "email": 1, "name": 1},
            ).to_list(100)
        for user in hr_users_by_company[company_id]:
            key = {
                "company_id": company_id,
                "employee_id": employee["id"],
                "contract_end_date": end_date,
                "days_before": days_before,
                "user_id": user["id"],
            }
            if await db.contract_expiry_alerts.find_one(key, {"_id": 1}):
                continue
            await db.contract_expiry_alerts.insert_one({
                **key,
                "id": str(uuid.uuid4()),
                "employee_name": f'{employee.get("first_name", "")} {employee.get("last_name", "")}'.strip(),
                "status": "pending",
                "attempts": 0,
                "created_at": iso(now_utc()),
            })


async def _deliver_pending_alerts() -> dict:
    pending = await db.contract_expiry_alerts.find(
        {"status": "pending"}, {"_id": 0},
    ).to_list(5000)
    if not pending:
        return {"pending": 0, "delivered": 0, "cancelled": 0}

    from email_service import is_configured as email_is_configured, _send as send_email
    from push_service import fanout_to_user

    can_email = email_is_configured()
    delivered = cancelled = 0
    for alert in pending:
        tf = {"company_id": alert["company_id"]}
        employee = await db.employees.find_one(
            {"id": alert["employee_id"], **tf, "status": "active",
             "contract_end_date": alert["contract_end_date"]},
            {"_id": 0, "id": 1},
        )
        user = await db.users.find_one(
            {"id": alert["user_id"], **tf, "role": {"$in": list(HR_ROLES)},
             "disabled": {"$ne": True}},
            {"_id": 0, "id": 1, "email": 1, "name": 1},
        )
        if not employee or not user:
            await db.contract_expiry_alerts.update_one(
                {"id": alert["id"], "company_id": alert["company_id"]},
                {"$set": {"status": "cancelled", "cancelled_at": iso(now_utc())}},
            )
            cancelled += 1
            continue

        name = alert["employee_name"] or "An employee"
        days = alert["days_before"]
        title = f"Contract expiry reminder ({days}-day)"
        body = f"{name}'s contract ends on {alert['contract_end_date']}."
        try:
            push = await fanout_to_user(user["id"], {
                "title": title,
                "body": body,
                "url": f"/employees/{alert['employee_id']}",
                "kind": "contract_expiry",
                "tag": f"contract-{alert['employee_id']}-{days}",
            })
        except Exception:
            logger.exception("Contract expiry push failed for user %s", user["id"])
            push = {"sent": 0}
        sent = bool(push.get("sent"))
        if not sent and can_email and user.get("email"):
            html = (
                f"<p>{escape(name)}'s contract ends on "
                f"<strong>{escape(alert['contract_end_date'])}</strong> "
                f"(the scheduled {days}-day reminder).</p>"
                f"<p>Review the employee record in SaloneHCM and decide whether to renew or start offboarding.</p>"
            )
            try:
                result = await send_email(user["email"], title, html)
                sent = bool(result.get("ok"))
            except Exception:
                logger.exception("Contract expiry email failed for user %s", user["id"])

        update = {
            "last_attempt_at": iso(now_utc()),
            "last_push_sent": push.get("sent", 0),
        }
        if sent:
            update.update({"status": "sent", "sent_at": iso(now_utc())})
            delivered += 1
        await db.contract_expiry_alerts.update_one(
            {"id": alert["id"], "company_id": alert["company_id"]},
            {"$set": update, "$inc": {"attempts": 1}},
        )
    return {"pending": len(pending), "delivered": delivered, "cancelled": cancelled}


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
