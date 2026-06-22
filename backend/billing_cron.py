"""Monthly billing automation.

Cron job that on the 1st of each month:
  1. Issues a fresh bank-transfer invoice for every `active` or `trialing` subscription.
  2. Flips subscriptions to `past_due` after the grace period if the current invoice is unpaid.
  3. Suspends subscriptions whose past_due lapses beyond the grace period.
  4. Emails the invoice + bank details to each tenant admin via Resend (best-effort).

Idempotent — re-running for the same period skips already-issued invoices.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.billing_cron")


async def _email_invoice(invoice: dict, admin_email: str) -> None:
    """Best-effort email — silently skip on failure."""
    try:
        from email_service import _wrap_html, _send as _email_send, is_configured as _email_ok
        if not _email_ok():
            return
        bank = invoice.get("bank_details") or {}
        body_html = f"""
        <p>Your SaloneHCM subscription invoice for {invoice.get('period_start', '')[:10]} is ready.</p>
        <table style="width:100%;border-collapse:collapse;margin-top:16px;">
          <tr><td style="padding:6px 0;border-bottom:1px solid #E2DFD6;"><strong>Reference</strong></td>
              <td style="padding:6px 0;border-bottom:1px solid #E2DFD6;text-align:right;font-family:monospace;">{invoice['reference']}</td></tr>
          <tr><td style="padding:6px 0;border-bottom:1px solid #E2DFD6;">Plan</td>
              <td style="padding:6px 0;border-bottom:1px solid #E2DFD6;text-align:right;">{invoice['plan_label']}</td></tr>
          <tr><td style="padding:6px 0;border-bottom:1px solid #E2DFD6;">Amount due</td>
              <td style="padding:6px 0;border-bottom:1px solid #E2DFD6;text-align:right;font-weight:bold;">SLE {invoice['total_sle']:,.2f}</td></tr>
          <tr><td style="padding:6px 0;">Due date</td>
              <td style="padding:6px 0;text-align:right;">{invoice.get('due_date', '')[:10]}</td></tr>
        </table>
        <p style="margin-top:16px;">Transfer to <strong>{bank.get('bank_name', '')}</strong>, account
        <code>{bank.get('account_number', '')}</code> using the reference above.</p>
        """
        html = _wrap_html(title="SaloneHCM invoice", body_html=body_html,
                          cta_label="Open billing portal", cta_url="/billing")
        await _email_send(admin_email, f"SaloneHCM · Invoice {invoice['reference']}", html)
    except Exception as e:
        logger.warning("Could not email invoice %s to %s: %s", invoice["reference"], admin_email, e)


async def issue_monthly_invoices() -> dict:
    """Issue invoices to every active/trialing subscription. Idempotent per (company_id, period)."""
    from routers.billing import _create_invoice
    now = now_utc()
    period_key = now.strftime("%Y-%m")
    subs = await db.subscriptions.find(
        {"status": {"$in": ["trialing", "active", "past_due"]}}, {"_id": 0},
    ).to_list(2000)
    issued = 0
    skipped = 0
    for sub in subs:
        # Idempotency: skip if an open invoice already exists for this period.
        existing = await db.subscription_invoices.find_one({
            "company_id": sub["company_id"],
            "status": "open",
            "period_start": {"$gte": period_key + "-01"},
        }, {"_id": 0, "id": 1})
        if existing:
            skipped += 1
            continue
        invoice = await _create_invoice(sub["company_id"], sub["plan_id"], "bank_transfer")
        # Email all admins of this company
        admins = await db.users.find(
            {"company_id": sub["company_id"], "role": {"$in": ["admin", "superadmin"]}},
            {"_id": 0, "email": 1},
        ).to_list(50)
        for a in admins:
            await _email_invoice(invoice, a["email"])
        issued += 1
    logger.info("Monthly billing cron: %d invoices issued, %d skipped (idempotent)", issued, skipped)
    return {"issued": issued, "skipped": skipped, "period": period_key}


async def transition_lapsed_subscriptions() -> dict:
    """Move active→past_due when invoice is overdue, past_due→suspended after grace."""
    now = now_utc()
    iso_now = iso(now)
    grace_cutoff = iso(now - timedelta(days=7))

    # active → past_due (invoice overdue)
    pd = await db.subscriptions.update_many(
        {
            "status": {"$in": ["active", "trialing"]},
            "current_period_end": {"$lt": iso_now},
        },
        {"$set": {"status": "past_due", "past_due_at": iso_now}},
    )

    # past_due → suspended (more than 7 days past due)
    susp = await db.subscriptions.update_many(
        {"status": "past_due", "past_due_at": {"$lt": grace_cutoff}},
        {"$set": {"status": "suspended", "suspended_at": iso_now}},
    )
    logger.info("Subscription transitions: %d → past_due, %d → suspended", pd.modified_count, susp.modified_count)
    return {"past_due": pd.modified_count, "suspended": susp.modified_count}


async def run_monthly_billing() -> dict:
    """Top-level cron entry — orchestrates invoice issuance + state transitions."""
    issuance = await issue_monthly_invoices()
    transitions = await transition_lapsed_subscriptions()
    return {**issuance, **transitions}


def register(scheduler) -> None:
    """Register the cron with APScheduler — runs at 02:00 UTC on day 1 of every month."""
    from apscheduler.triggers.cron import CronTrigger
    scheduler.add_job(
        run_monthly_billing,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="monthly_billing",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Monthly billing cron registered (day=1, 02:00 UTC)")
