"""Daily admin digest — runs once per day, pushes a summary to each tenant admin."""
import logging
import os
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


def _email_items(snap: dict) -> list[dict]:
    """Build deep-linked items for the HTML email."""
    frontend = os.environ.get("FRONTEND_URL", "")
    items = []
    if snap["pending_leaves"]:
        items.append({
            "label": f"<strong>{snap['pending_leaves']}</strong> pending leave request{'s' if snap['pending_leaves'] != 1 else ''}",
            "url": f"{frontend}/leave?status=pending",
            "cta": "Review leaves",
        })
    if snap["upcoming_runs"]:
        items.append({
            "label": f"<strong>{len(snap['upcoming_runs'])}</strong> scheduled payroll run{'s' if len(snap['upcoming_runs']) != 1 else ''} due in the next 72h",
            "url": f"{frontend}/payroll?due=soon",
            "cta": "View schedules",
        })
    if snap["outstanding_filings"]:
        items.append({
            "label": f"<strong>{len(snap['outstanding_filings'])}</strong> NRA PAYE filing{'s' if len(snap['outstanding_filings']) != 1 else ''} outstanding",
            "url": f"{frontend}/compliance?outstanding=true",
            "cta": "File now",
        })
    if snap["pending_manager_reviews"]:
        items.append({
            "label": f"<strong>{snap['pending_manager_reviews']}</strong> performance review{'s' if snap['pending_manager_reviews'] != 1 else ''} awaiting manager",
            "url": f"{frontend}/performance",
            "cta": "Score reviews",
        })
    return items


def _build_email_body_html(admin_name: str, items: list[dict]) -> str:
    """Compose the inner HTML body for a digest email."""
    greeting = f"<p>Good morning {admin_name},</p>"
    if not items:
        return greeting + '<p style="color:#2D7A5D;font-weight:600;">All clear — no pending actions today. 🎉</p>'
    rows = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #E2DFD6;">'
        f'<div style="font-size:13px;">{it["label"]}</div>'
        f'<a href="{it["url"]}" style="color:#26547C;font-size:12px;text-decoration:none;">{it["cta"]} →</a>'
        f'</td></tr>'
        for it in items
    )
    return (
        greeting
        + "<p>Here's your SaloneHCM digest for today:</p>"
        + f'<table style="width:100%;border-collapse:collapse;">{rows}</table>'
    )


async def _push_digest(admin: dict, body: str) -> None:
    import push_service
    try:
        await push_service.fanout_to_user(admin["id"], {
            "title": "SaloneHCM · Daily digest",
            "body": body,
            "url": "/dashboard",
            "kind": "daily_digest",
            "tag": "daily-digest",
        })
    except Exception:
        logger.warning("daily digest push failed for %s", admin["email"])


async def _email_digest(admin: dict, snap: dict) -> None:
    from email_service import _wrap_html, _send as _email_send
    try:
        body_html = _build_email_body_html(admin.get("name", ""), _email_items(snap))
        html = _wrap_html(
            title="Daily digest",
            body_html=body_html,
            cta_label="Open dashboard",
            cta_url=(os.environ.get("FRONTEND_URL", "") + "/dashboard"),
        )
        await _email_send(admin["email"], "SaloneHCM · Daily digest", html)
    except Exception:
        logger.warning("daily digest email failed for %s", admin["email"])


async def _send_daily_digest() -> None:
    """For each admin user, compute their tenant snapshot and fire their preferred channels."""
    from email_service import is_configured as _email_ok
    admins = await db.users.find(
        {"role": {"$in": ["admin", "superadmin"]}},
        {"_id": 0, "id": 1, "email": 1, "company_id": 1, "name": 1, "digest_prefs": 1},
    ).to_list(500)

    by_tenant: dict[str, dict] = {}
    for a in admins:
        cid = a.get("company_id")
        if not cid:
            continue
        if cid not in by_tenant:
            by_tenant[cid] = await _aggregate_for_tenant(cid)
        snap = by_tenant[cid]
        prefs = a.get("digest_prefs") or {"push": True, "email": False}
        if prefs.get("push"):
            await _push_digest(a, _summarize(snap))
        if prefs.get("email") and _email_ok():
            await _email_digest(a, snap)

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
