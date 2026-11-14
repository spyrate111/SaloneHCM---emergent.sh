"""Annual step-increment job — auto-bumps each active civil servant by +1 step on their hire-date anniversary.

Designed to be:
  - Idempotent: writes a `step_increments` audit row keyed by (company_id, employee_id, year) so
    re-running on the same day is a no-op.
  - Safe: only bumps employees who are below the max step on their current grade.
  - Re-targetable: admin can call `POST /civil-service/step-increments/run` to dry-run or apply now.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.triggers.cron import CronTrigger

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.step_increments")

# 02:00 UTC daily — picks up everyone with anniversary today
INCREMENT_CRON = CronTrigger(hour=2, minute=0, second=0)


async def _eligible_today_for_tenant(company_id: str, target_date: Optional[datetime] = None) -> list[dict]:
    """Find employees whose hire-date anniversary is today AND who haven't been auto-bumped this year."""
    today = (target_date or now_utc()).date()
    year = today.year

    # Fetch all active employees with a grade
    emps = await db.employees.find({
        "company_id": company_id,
        "status": "active",
        "grade_code": {"$exists": True, "$ne": None},
        "step_number": {"$exists": True, "$ne": None},
        "hire_date": {"$exists": True, "$ne": None},
    }, {"_id": 0}).to_list(5000)

    eligible = []
    for e in emps:
        hire = e.get("hire_date")
        if not hire:
            continue
        try:
            hd = datetime.fromisoformat(hire.replace("Z", "+00:00")).date() if "T" in str(hire) else datetime.strptime(hire, "%Y-%m-%d").date()
        except Exception:
            continue
        if hd.month != today.month or hd.day != today.day:
            continue
        # Don't bump if the employee was hired this year (no anniversary yet)
        if hd.year >= year:
            continue
        # Idempotency: skip if we already recorded an increment for (employee, year)
        existing = await db.step_increments.find_one(
            {"company_id": company_id, "employee_id": e["id"], "year": year}, {"_id": 0, "id": 1}
        )
        if existing:
            continue
        # Skip if already on max step
        max_step = await db.civil_service_steps.find_one(
            {"company_id": company_id, "grade_code": e["grade_code"]},
            sort=[("step_number", -1)],
        )
        max_n = (max_step or {}).get("step_number", 6)
        if e["step_number"] >= max_n:
            continue
        # Compute next step amount
        next_step = await db.civil_service_steps.find_one({
            "company_id": company_id, "grade_code": e["grade_code"], "step_number": e["step_number"] + 1,
        }, {"_id": 0})
        if not next_step:
            continue
        eligible.append({
            "employee": e,
            "next_step_number": e["step_number"] + 1,
            "old_step_number": e["step_number"],
            "old_basic": e.get("basic_salary_sle", 0),
            "new_basic": float(next_step["monthly_amount_sle"]),
            "year": year,
        })
    return eligible


async def _notify_company_admins(company_id: str, applied: list[dict]) -> None:
    """Send one privacy-conscious summary to admins in the affected company."""
    try:
        admins = await db.users.find(
            {"company_id": company_id, "role": {"$in": ["admin", "superadmin"]}},
            {"_id": 0, "id": 1},
        ).to_list(500)
        if not admins:
            logger.info("No HR admins found for step-increment notification (company=%s)", company_id)
            return

        import push_service

        count = len(applied)
        payload = {
            "title": "Annual step increments applied",
            "body": (
                f"{count} employee{'s' if count != 1 else ''} received an annual grade-step adjustment. "
                "Review the step-increment history."
            ),
            "url": "/civil-service",
            "kind": "step_increment_admin",
        }
        results = await asyncio.gather(
            *(push_service.fanout_to_user(admin["id"], payload) for admin in admins),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.error("HR step-increment push failed: %s", result)
            elif result.get("failed"):
                logger.warning(
                    "HR step-increment push had %d failed device deliveries",
                    result["failed"],
                )
    except Exception:
        logger.exception("Failed to notify HR admins about annual step increments")


async def apply_increments(company_id: str, eligible: list[dict], user_email: str, dry_run: bool = False) -> dict:
    applied = []
    for it in eligible:
        e = it["employee"]
        if not dry_run:
            year = int(it.get("year") or now_utc().year)
            result = await db.employees.update_one(
                {
                    "id": e["id"],
                    "company_id": company_id,
                    "status": "active",
                    "grade_code": e["grade_code"],
                    "step_number": it["old_step_number"],
                    "last_step_bump_year": {"$ne": year},
                },
                {"$set": {
                    "step_number": it["next_step_number"],
                    "basic_salary_sle": it["new_basic"],
                    "last_step_bump_at": iso(now_utc()),
                    "last_step_bump_year": year,
                }},
            )
            if result.matched_count != 1:
                logger.info(
                    "Skipping stale or duplicate step increment (company=%s employee=%s year=%s)",
                    company_id, e["id"], year,
                )
                continue

            await db.step_increments.insert_one({
                "company_id": company_id,
                "employee_id": e["id"],
                "employee_name": f'{e.get("first_name","")} {e.get("last_name","")}'.strip(),
                "grade_code": e["grade_code"],
                "year": year,
                "from_step": it["old_step_number"],
                "to_step": it["next_step_number"],
                "from_basic_sle": it["old_basic"],
                "to_basic_sle": it["new_basic"],
                "delta_sle": round(it["new_basic"] - it["old_basic"], 2),
                "applied_at": iso(now_utc()),
                "applied_by": user_email,
            })
            try:
                import push_service
                await push_service.fanout_to_employee(e["id"], {
                    "title": "Step increment applied",
                    "body": f"You moved to {e['grade_code']} step {it['next_step_number']} on your work anniversary. New basic: SLE {it['new_basic']:,.0f}.",
                    "url": "/self-service",
                    "kind": "step_increment",
                })
            except Exception:
                logger.exception("Failed to notify employee about step increment (employee=%s)", e["id"])
        applied.append({
            "employee_id": e["id"],
            "employee_name": f'{e.get("first_name","")} {e.get("last_name","")}'.strip(),
            "grade_code": e["grade_code"],
            "from_step": it["old_step_number"],
            "to_step": it["next_step_number"],
            "delta_sle": round(it["new_basic"] - it["old_basic"], 2),
        })
    if not dry_run and applied:
        await _notify_company_admins(company_id, applied)
    return {"dry_run": dry_run, "count": len(applied), "applied": applied}


async def _run_for_all_tenants(target_date: Optional[datetime] = None) -> dict:
    companies = await db.companies.find({"features": "civil_service"}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    summary = []
    for c in companies:
        eligible = await _eligible_today_for_tenant(c["id"], target_date=target_date)
        res = await apply_increments(c["id"], eligible, user_email="system_cron")
        summary.append({"company_id": c["id"], "name": c["name"], "applied": res["count"]})
    logger.info("Step-increment cron: processed %d tenants → %s", len(summary), summary)
    return {"tenants": summary}


async def _scheduled_run() -> None:
    """APScheduler entrypoint."""
    try:
        await _run_for_all_tenants()
    except Exception as e:
        logger.exception("step-increment cron failed: %s", e)


def attach(scheduler) -> None:
    scheduler.add_job(
        _scheduled_run, INCREMENT_CRON,
        id="step_increments", replace_existing=True, max_instances=1, coalesce=True,
    )
    logger.info("Step-increment cron scheduled: 02:00 UTC daily")
