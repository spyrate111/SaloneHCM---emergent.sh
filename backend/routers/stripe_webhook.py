"""Public Stripe webhook (no CSRF, no auth — verified via signature).

Stripe POSTs to /api/webhook/stripe with the event. We:
  1. Verify signature using the SDK (handle_webhook).
  2. If checkout.session.completed → mark the payment_transaction paid + activate the subscription.

Webhook is idempotent — re-applies cause no state change because _apply_paid_subscription
just updates the subscription doc to the same values.
"""
import os
from fastapi import APIRouter, Request, HTTPException

from core import db, now_utc, iso

# This router is registered on the OUTER app (not /api) so it can be exempted from CSRF.
# But Stripe will POST to /api/webhook/stripe by convention. We register under /api.
router = APIRouter(tags=["webhook"])


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(503, "Stripe not configured")
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    host_url = str(request.base_url).rstrip("/")
    sc = StripeCheckout(api_key=api_key, webhook_url=f"{host_url}/api/webhook/stripe")
    try:
        evt = await sc.handle_webhook(body, sig)
    except Exception as e:
        raise HTTPException(400, f"Invalid webhook: {e}")

    # Only process completion events.
    if evt.payment_status == "paid" and evt.session_id:
        txn = await db.payment_transactions.find_one({"session_id": evt.session_id}, {"_id": 0})
        if txn and txn.get("payment_status") != "paid":
            await db.payment_transactions.update_one(
                {"session_id": evt.session_id},
                {"$set": {"payment_status": "paid", "status": "complete", "paid_at": iso(now_utc())}},
            )
            # Import lazily to avoid circular dep
            from routers.billing import _apply_paid_subscription
            await _apply_paid_subscription(
                txn["company_id"], txn["plan_id"], txn["amount_sle"], "stripe"
            )
    return {"received": True}
