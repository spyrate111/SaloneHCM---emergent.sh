"""Daily admin digest — runs once per day, pushes a summary to each tenant admin."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.triggers.cron import CronTrigger

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.digest")

# 7:00 UTC = 7:00 in Sierra Leone (UTC+0)
DIGEST_CRON = CronTrigger(hour=7, minute=0, second=0)


async def _aggregate_for_tenant(company_id: str) -> dict:
    """Pull KPI snapshot for one tenant."""
    now = now_utc()
    pending_leaves = await db.leave_requests.count_documents({"company_id": company_id, "status": "pending"})
    employee_count = await db.employees.count_documents({"company_id": company_id, "status": "active"})

    # Upcoming scheduled payroll runs in the next 72h
    cutoff = iso(now + timedelta(hours=72))
    next_runs = await db.payroll_schedules.find(
        {"company_id": company_id, "active": True, "next_run_at": {"$lte": cutoff}},
        {"_id": 0, "title": 1, "next_run_at": 1, "cadence": 1},
    ).to_list(10)

    # Outstanding NRA filings = payroll runs without filing
    all_runs = await db.payroll_runs.find(
        {"company_id": company_id}, {"_id": 0, "id": 1, "period": 1}
    ).sort("created_at", -1).to_list(50)
    filed_ids = set(await db.nra_filings.distinct("run_id", {"company_id": company_id}))
    outstanding = [r for r in all_runs if r["id"] not in filed_ids][:5]

    # Pending performance reviews (manager-side only)
    pending_perf = await db.performance_reviews_v2.count_documents({
        "company_id": company_id, "status": "pending_manager",
    })
    return {
        "pending_leaves": pending_leaves,
        "employee_count": employee_count,
        "upcoming_runs": next_runs,
        "outstanding_filings": outstanding,
        "pending_manager_reviews": pending_perf,
        "generated_at": iso(now),
    }


def _summarize(snap: dict) -> str:
    """Build a short notification body line."""
    parts = []
    if snap["pending_leaves"]:
        parts.append(f"{snap['pending_leaves']} pending leave{'s' if snap['pending_leaves'] != 1 else ''}")
    if snap["upcoming_runs"]:
        parts.append(f"{len(snap['upcoming_runs'])} payroll run{'s' if len(snap['upcoming_runs']) != 1 else ''} due ≤72h")
    if snap["outstanding_filings"]:
        parts.append(f"{len(snap['outstanding_filings'])} NRA filing{'s' if len(snap['outstanding_filings']) != 1 else ''} outstanding")
    if snap["pending_manager_reviews"]:
        parts.append(f"{snap['pending_manager_reviews']} review{'s' if snap['pending_manager_reviews'] != 1 else ''} awaiting manager")
    return " · ".join(parts) or "All clear — no pending actions."


async def _send_daily_digest() -> None:
    """For each admin user, compute their tenant snapshot and fire a push."""
    import push_service
    admins = await db.users.find(
        {"role": {"$in": ["admin", "superadmin"]}},
        {"_id": 0, "id": 1, "email": 1, "company_id": 1},
    ).to_list(500)

    by_tenant: dict[str, dict] = {}
    for a in admins:
        cid = a.get("company_id")
        if not cid:
            continue
        if cid not in by_tenant:
            by_tenant[cid] = await _aggregate_for_tenant(cid)
        snap = by_tenant[cid]
        body = _summarize(snap)
        try:
            await push_service.fanout_to_user(a["id"], {
                "title": "SaloneHCM · Daily digest",
                "body": body,
                "url": "/dashboard",
                "kind": "daily_digest",
                "tag": "daily-digest",
            })
        except Exception:
            logger.warning("daily digest push failed for %s", a["email"])

    # Persist a log so admins can inspect
    try:
        await db.digest_runs.insert_one({
            "ran_at": iso(now_utc()),
            "admins_notified": len(admins),
            "tenants_summarised": len(by_tenant),
            "snapshots": {tid: {k: (v if not isinstance(v, list) else len(v)) for k, v in s.items()} for tid, s in by_tenant.items()},
        })
    except Exception:
        pass
    logger.info("Daily digest: notified %d admins across %d tenants", len(admins), len(by_tenant))


async def run_now(company_id: Optional[str] = None) -> dict:
    """On-demand digest preview — useful for the 'Send me a digest' admin button."""
    return await _aggregate_for_tenant(company_id) if company_id else {"error": "company_id required"}


def attach(scheduler) -> None:
    """Register the daily digest job on the shared APScheduler instance."""
    scheduler.add_job(_send_daily_digest, DIGEST_CRON,
                      id="daily_digest", replace_existing=True, max_instances=1, coalesce=True)
    logger.info("Daily digest scheduled: 07:00 UTC every day")
