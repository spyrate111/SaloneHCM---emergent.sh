"""Recurring payroll schedules — APScheduler-driven monthly/biweekly/weekly auto-runs."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core import db, now_utc, iso, audit
from payroll_engine import run_payroll

logger = logging.getLogger("salonehcm.scheduler")

# Module-level scheduler — started/stopped via FastAPI lifespan
scheduler = AsyncIOScheduler(timezone="UTC")

# How often we wake up to evaluate schedules. 5 minutes is plenty.
TICK_SECONDS = 300


def _add_months(d: datetime, months: int) -> datetime:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # Clamp day to last day of target month
    day = min(d.day, _last_day_of_month(year, month))
    return d.replace(year=year, month=month, day=day)


def _last_day_of_month(year: int, month: int) -> int:
    next_month = datetime(year + (1 if month == 12 else 0),
                          1 if month == 12 else month + 1, 1, tzinfo=timezone.utc)
    return (next_month - timedelta(days=1)).day


def compute_next_run(cadence: str, day_of_month: int, last_run_at: Optional[str], from_dt: Optional[datetime] = None) -> str:
    """Return ISO string of next scheduled run-time in UTC."""
    base = from_dt or now_utc()
    if cadence == "monthly":
        target = base.replace(day=min(day_of_month, _last_day_of_month(base.year, base.month)),
                              hour=6, minute=0, second=0, microsecond=0)
        if target <= base:
            target = _add_months(target, 1)
        return iso(target)
    if cadence == "biweekly":
        anchor = datetime.fromisoformat(last_run_at.replace("Z", "+00:00")) if last_run_at else base
        nxt = anchor + timedelta(days=14)
        if nxt <= base:
            nxt = base + timedelta(days=14)
        return iso(nxt.replace(hour=6, minute=0, second=0, microsecond=0))
    # weekly default
    anchor = datetime.fromisoformat(last_run_at.replace("Z", "+00:00")) if last_run_at else base
    nxt = anchor + timedelta(days=7)
    if nxt <= base:
        nxt = base + timedelta(days=7)
    return iso(nxt.replace(hour=6, minute=0, second=0, microsecond=0))


async def _evaluate_due() -> None:
    """Tick callback — find schedules whose next_run_at is in the past and execute them."""
    now_iso = iso(now_utc())
    due = await db.payroll_schedules.find(
        {"active": True, "next_run_at": {"$lte": now_iso}},
        {"_id": 0},
    ).to_list(50)
    if not due:
        return
    for sched in due:
        try:
            company = await db.companies.find_one({"id": sched["company_id"]}, {"_id": 0})
            if not company:
                continue
            actor = {
                "id": sched.get("created_by_id", "scheduler"),
                "email": sched.get("created_by", "scheduler@salonehcm"),
                "role": "system",
                "company_id": sched["company_id"],
            }
            today = now_utc()
            doc = await run_payroll(
                year=today.year,
                month=today.month,
                user=actor,
                audit_action="scheduled_payroll_run",
            )
            next_at = compute_next_run(sched["cadence"], sched.get("day_of_month", 28), iso(today), today)
            await db.payroll_schedules.update_one(
                {"id": sched["id"]},
                {"$set": {
                    "last_run_at": iso(today),
                    "last_run_id": doc["id"],
                    "last_run_status": "success",
                    "next_run_at": next_at,
                }, "$inc": {"runs_completed": 1}},
            )
            await audit("payroll_schedule_fire", f"payroll_schedules/{sched['id']}", actor,
                        {"period": doc["period"], "run_id": doc["id"]})
            logger.info("scheduled payroll run completed: %s · %s", sched["title"], doc["period"])
        except Exception as e:
            logger.exception("scheduled payroll failed: %s", sched["id"])
            await db.payroll_schedules.update_one(
                {"id": sched["id"]},
                {"$set": {"last_run_status": f"error: {str(e)[:200]}"}},
            )


def start():
    if scheduler.running:
        return
    scheduler.add_job(_evaluate_due, IntervalTrigger(seconds=TICK_SECONDS),
                      id="payroll_scheduler", replace_existing=True, max_instances=1, coalesce=True)
    # Attach daily admin digest (07:00 UTC)
    try:
        from digest import attach as attach_digest
        attach_digest(scheduler)
    except Exception:
        logger.exception("Failed to attach daily digest job")
    # Attach annual step-increment job
    try:
        from step_increments import attach as attach_step_inc
        attach_step_inc(scheduler)
    except Exception:
        logger.exception("Failed to attach step-increment job")
    scheduler.start()
    logger.info("Payroll scheduler started (tick every %ss)", TICK_SECONDS)


def stop():
    if scheduler.running:
        scheduler.shutdown(wait=False)
