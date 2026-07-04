"""Subscription billing for SaloneHCM SaaS.

Sierra Leone reality:
  * Most B2B payments still go via direct bank transfer (SLCB, Rokel, Ecobank, GTBank, UBA).
  * Card payments are growing but limited — Stripe Checkout is the international fallback.
  * Mobile money (Orange Money, Africell Money) dominates retail but is rarely used B2B.

This module exposes both rails:
  * `bank_transfer` invoice (default) — reference code, due_date, SL bank details.
    Super-admin manually marks paid after reconciling with the bank statement.
  * `stripe` — Stripe Checkout for international tenants. Server-defined plan prices.

Plan catalog is SERVER-DEFINED only (anti-fraud — frontend cannot pass prices).
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import db, tenant_filter, require_admin, require_superadmin, audit, now_utc, iso, get_current_user
from tiers import features_for, tier_label, TIERS


# ---- Plan catalog — Sierra Leone Leone pricing ----
# Prices are MONTHLY in SLE (Sierra Leonean Leone, the country's official currency).
# These are server-controlled — frontend can NEVER override these.
PLAN_CATALOG = {
    "lite": {
        "id": "lite", "label": "Lite", "monthly_sle": 200.0, "monthly_usd": 9.0,
        "included_employees": 25, "extra_employee_sle": 8.0,
        "description": "Solo founders and micro-businesses (<25 staff).",
    },
    "professional": {
        "id": "professional", "label": "Professional", "monthly_sle": 800.0, "monthly_usd": 35.0,
        "included_employees": 100, "extra_employee_sle": 6.0,
        "description": "Growing SMEs — adds loans, analytics, AI assistant.",
    },
    "enterprise": {
        "id": "enterprise", "label": "Enterprise", "monthly_sle": 2500.0, "monthly_usd": 109.0,
        "included_employees": 500, "extra_employee_sle": 4.0,
        "description": "Mid-cap companies — adds IFMIS, Establishment, full audit.",
    },
    "gov": {
        "id": "gov", "label": "Government", "monthly_sle": 8000.0, "monthly_usd": 349.0,
        "included_employees": 5000, "extra_employee_sle": 2.5,
        "description": "Ministries, Departments & Agencies — civil service, NRA, ministry rollups.",
    },
}

# Sierra Leone bank details used on every bank-transfer invoice.
# In production, an admin would set these via /api/billing/bank-details.
SALONEHCM_BANK_DETAILS = {
    "bank_name": "Sierra Leone Commercial Bank",
    "account_name": "SaloneHCM Limited",
    "account_number": "001-2200-4488761",
    "branch_code": "001",
    "swift": "SLCBSLFRXXX",
    "currency": "SLE",
}

GRACE_PERIOD_DAYS = 7  # past_due → suspended


router = APIRouter(prefix="/billing", tags=["billing"])


# ---------- Models ----------

class CreateBankInvoiceIn(BaseModel):
    plan_id: Literal["lite", "professional", "enterprise", "gov"]


class CreateCheckoutIn(BaseModel):
    plan_id: Literal["lite", "professional", "enterprise", "gov"]
    origin_url: str = Field(..., min_length=10)


class MarkPaidIn(BaseModel):
    bank_reference: str = Field(..., min_length=3, max_length=120)


# ---------- Helpers ----------

def _public_plan(p: dict) -> dict:
    return {**p, "features": features_for(p["id"])}


def _compute_amount_for_company(plan_id: str, employee_count: int) -> tuple[float, dict]:
    """Server-side amount calculation — frontend never sends a price."""
    plan = PLAN_CATALOG[plan_id]
    base = plan["monthly_sle"]
    extra = max(0, employee_count - plan["included_employees"]) * plan["extra_employee_sle"]
    total = round(base + extra, 2)
    return total, {
        "base_sle": base,
        "extra_sle": round(extra, 2),
        "extra_employees": max(0, employee_count - plan["included_employees"]),
        "total_sle": total,
        "currency": "SLE",
    }


def _next_period_dates() -> tuple[str, str]:
    now = now_utc()
    end = now + timedelta(days=30)
    return iso(now), iso(end)


async def _ensure_subscription(company_id: str) -> dict:
    """Get or create a subscription doc for the company."""
    sub = await db.subscriptions.find_one({"company_id": company_id}, {"_id": 0})
    if sub:
        return sub
    company = await db.companies.find_one({"id": company_id}, {"_id": 0, "tier": 1})
    tier = (company or {}).get("tier") or "lite"
    start, end = _next_period_dates()
    new_sub = {
        "id": str(uuid.uuid4()),
        "company_id": company_id,
        "plan_id": tier,
        "status": "trialing",  # 30-day free trial for every new tenant
        "trial_ends_at": end,
        "current_period_start": start,
        "current_period_end": end,
        "created_at": start,
    }
    await db.subscriptions.insert_one(new_sub)
    return new_sub


async def _create_invoice(company_id: str, plan_id: str, payment_method: str,
                          stripe_session_id: Optional[str] = None) -> dict:
    employees = await db.employees.count_documents({"company_id": company_id, "status": {"$ne": "terminated"}})
    amount, breakdown = _compute_amount_for_company(plan_id, employees)
    iid = str(uuid.uuid4())
    now = now_utc()
    period_start = iso(now)
    period_end = iso(now + timedelta(days=30))
    due_date = iso(now + timedelta(days=GRACE_PERIOD_DAYS))
    company = await db.companies.find_one({"id": company_id}, {"_id": 0, "name": 1})
    invoice = {
        "id": iid,
        "company_id": company_id,
        "company_name": (company or {}).get("name", ""),
        "plan_id": plan_id,
        "plan_label": PLAN_CATALOG[plan_id]["label"],
        "employee_count": employees,
        **breakdown,
        "payment_method": payment_method,  # "bank_transfer" or "stripe"
        "status": "open",  # open → paid | cancelled
        "reference": f"SHCM-{company_id[:6].upper()}-{datetime.now(timezone.utc).strftime('%Y%m')}-{iid[:4].upper()}",
        "due_date": due_date,
        "period_start": period_start,
        "period_end": period_end,
        "created_at": iso(now),
        "stripe_session_id": stripe_session_id,
        "bank_details": SALONEHCM_BANK_DETAILS if payment_method == "bank_transfer" else None,
    }
    await db.subscription_invoices.insert_one(invoice)
    return invoice


def _strip_id(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "_id"}


# ---------- Public catalog ----------

@router.get("/plans")
async def list_plans():
    """Public — show pricing on the upgrade page."""
    return {
        "plans": [_public_plan(p) for p in PLAN_CATALOG.values()],
        "currency": "SLE",
        "grace_period_days": GRACE_PERIOD_DAYS,
    }


@router.get("/me")
async def my_subscription(user: dict = Depends(get_current_user)):
    """Current tenant's subscription + plan info + outstanding invoice (if any)."""
    sub = await _ensure_subscription(user["company_id"])
    plan = _public_plan(PLAN_CATALOG[sub["plan_id"]])
    employees = await db.employees.count_documents({"company_id": user["company_id"], "status": {"$ne": "terminated"}})
    amount, breakdown = _compute_amount_for_company(sub["plan_id"], employees)
    open_invoice = await db.subscription_invoices.find_one(
        {"company_id": user["company_id"], "status": "open"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    return {
        "subscription": _strip_id(sub),
        "plan": plan,
        "employees": employees,
        "current_charge": breakdown,
        "open_invoice": open_invoice,
        "feature_locked": sub["status"] in ("past_due", "suspended"),
    }


@router.get("/invoices")
async def list_invoices(user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    return await db.subscription_invoices.find(tf, {"_id": 0}).sort("created_at", -1).to_list(200)


# ---------- Bank-transfer flow (SL primary) ----------

@router.post("/bank-transfer/invoice")
async def create_bank_invoice(body: CreateBankInvoiceIn, user: dict = Depends(require_admin)):
    """Issue a bank-transfer invoice. The tenant pays into the bank account on the invoice
    using the unique reference code, then a super-admin marks it paid via /admin/mark-paid."""
    # Refuse double-open invoice
    existing = await db.subscription_invoices.find_one(
        {"company_id": user["company_id"], "status": "open"}, {"_id": 0, "id": 1},
    )
    if existing:
        raise HTTPException(409, f"Invoice {existing['id']} is already open — pay or cancel it first.")
    invoice = await _create_invoice(user["company_id"], body.plan_id, "bank_transfer")
    await audit("billing_bank_invoice", f"subscription_invoices/{invoice['id']}", user, {
        "plan": body.plan_id, "amount_sle": invoice["total_sle"],
    })
    return _strip_id(invoice)


@router.post("/invoices/{iid}/mark-paid")
async def mark_invoice_paid(iid: str, body: MarkPaidIn, user: dict = Depends(require_superadmin)):
    """Super-admin only: confirm bank transfer received & activate the subscription."""
    inv = await db.subscription_invoices.find_one({"id": iid}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv["status"] != "open":
        raise HTTPException(409, f"Invoice already {inv['status']}")
    start, end = _next_period_dates()
    await db.subscription_invoices.update_one(
        {"id": iid},
        {"$set": {
            "status": "paid",
            "paid_at": start,
            "paid_by": user["email"],
            "bank_reference": body.bank_reference,
        }},
    )
    # Update tenant subscription
    await db.subscriptions.update_one(
        {"company_id": inv["company_id"]},
        {"$set": {
            "plan_id": inv["plan_id"],
            "status": "active",
            "current_period_start": start,
            "current_period_end": end,
            "last_payment_at": start,
            "last_payment_method": "bank_transfer",
        }},
        upsert=True,
    )
    # Update company tier so feature flags follow
    await db.companies.update_one(
        {"id": inv["company_id"]},
        {"$set": {
            "tier": inv["plan_id"],
            "label": tier_label(inv["plan_id"]),
            "features": features_for(inv["plan_id"]),
        }},
    )
    await audit("billing_mark_paid", f"subscription_invoices/{iid}", user, {
        "company": inv["company_id"], "plan": inv["plan_id"],
        "amount_sle": inv["total_sle"], "bank_reference": body.bank_reference,
    })
    return {"ok": True, "subscription_status": "active"}


# ---------- Stripe Checkout flow (international fallback) ----------

def _compute_stripe_usd_amount(plan_id: str, employees: int) -> float:
    """Server-side USD price for Stripe (SLE not natively supported). Frontend cannot manipulate."""
    plan = PLAN_CATALOG[plan_id]
    base_usd = plan["monthly_usd"]
    extra_usd = max(0, employees - plan["included_employees"]) * (plan["extra_employee_sle"] / 22)
    return round(base_usd + extra_usd, 2)


async def _persist_pending_stripe_txn(session, company_id: str, plan_id: str,
                                       amount_usd: float, amount_sle: float,
                                       metadata: dict, user: dict) -> str:
    """Persist a pending payment_transaction (mandated by playbook) + audit log."""
    txn_id = str(uuid.uuid4())
    await db.payment_transactions.insert_one({
        "id": txn_id,
        "session_id": session.session_id,
        "company_id": company_id,
        "plan_id": plan_id,
        "amount_usd": amount_usd,
        "amount_sle": amount_sle,
        "currency": "USD",
        "payment_status": "initiated",
        "status": "open",
        "metadata": metadata,
        "created_at": iso(now_utc()),
    })
    await audit("billing_stripe_session", f"payment_transactions/{txn_id}", user, {
        "plan": plan_id, "amount_usd": amount_usd,
    })
    return txn_id


@router.post("/stripe/checkout")
async def create_stripe_checkout(body: CreateCheckoutIn, http_request: Request, user: dict = Depends(require_admin)):
    """Create a Stripe Checkout session in USD (Stripe doesn't support SLE).

    The amount is computed server-side per the catalog — frontend cannot manipulate price.
    """
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(503, "Stripe is not configured — use bank-transfer flow instead")

    employees = await db.employees.count_documents({"company_id": user["company_id"], "status": {"$ne": "terminated"}})
    amount_sle, _ = _compute_amount_for_company(body.plan_id, employees)
    amount_usd = _compute_stripe_usd_amount(body.plan_id, employees)

    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
    host_url = str(http_request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    sc = StripeCheckout(api_key=api_key, webhook_url=webhook_url)

    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/billing?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/billing?cancelled=1"
    metadata = {
        "company_id": user["company_id"],
        "plan_id": body.plan_id,
        "user_email": user["email"],
        "amount_sle": str(amount_sle),
    }
    req = CheckoutSessionRequest(
        amount=amount_usd, currency="usd",
        success_url=success_url, cancel_url=cancel_url, metadata=metadata,
    )
    session = await sc.create_checkout_session(req)

    await _persist_pending_stripe_txn(
        session, user["company_id"], body.plan_id, amount_usd, amount_sle, metadata, user,
    )
    return {"checkout_url": session.url, "session_id": session.session_id, "amount_usd": amount_usd}


@router.get("/stripe/status/{session_id}")
async def stripe_status(session_id: str, http_request: Request, user: dict = Depends(get_current_user)):
    """Polled by the frontend after Stripe redirects back. Idempotent."""
    txn = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn["company_id"] != user["company_id"]:
        raise HTTPException(403, "Not allowed")
    if txn["payment_status"] == "paid":
        return _strip_id(txn)

    api_key = os.environ.get("STRIPE_API_KEY")
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    host_url = str(http_request.base_url).rstrip("/")
    sc = StripeCheckout(api_key=api_key, webhook_url=f"{host_url}/api/webhook/stripe")
    status_resp = await sc.get_checkout_status(session_id)

    new_status = txn["payment_status"]
    if status_resp.payment_status == "paid":
        new_status = "paid"
    elif status_resp.status == "expired":
        new_status = "expired"

    if new_status != txn["payment_status"]:
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": new_status, "status": status_resp.status}},
        )
        if new_status == "paid":
            await _apply_paid_subscription(txn["company_id"], txn["plan_id"], txn["amount_sle"], "stripe")

    fresh = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    return _strip_id(fresh)


async def _apply_paid_subscription(company_id: str, plan_id: str, amount_sle: float, method: str) -> None:
    """Activate or extend a paid subscription. Idempotent — guard by checking
    last_payment_at to avoid double application if both webhook and polling fire."""
    start, end = _next_period_dates()
    await db.subscriptions.update_one(
        {"company_id": company_id},
        {"$set": {
            "plan_id": plan_id,
            "status": "active",
            "current_period_start": start,
            "current_period_end": end,
            "last_payment_at": start,
            "last_payment_method": method,
            "last_payment_amount_sle": amount_sle,
        }},
        upsert=True,
    )
    await db.companies.update_one(
        {"id": company_id},
        {"$set": {
            "tier": plan_id, "label": tier_label(plan_id),
            "features": features_for(plan_id),
        }},
    )


# ---------- Subscription enforcement ----------

async def is_tenant_blocked(company_id: str) -> tuple[bool, str]:
    """Returns (blocked, reason). Used by a middleware-ish dependency to soft-block
    routes when the subscription lapses past the grace period."""
    sub = await db.subscriptions.find_one(
        {"company_id": company_id}, {"_id": 0, "status": 1, "current_period_end": 1, "trial_ends_at": 1},
    )
    if not sub:
        return False, ""  # No sub yet → permitted (will be created on first /billing/me call)
    if sub.get("status") == "suspended":
        return True, "subscription_suspended"
    end_iso = sub.get("current_period_end") or sub.get("trial_ends_at")
    if end_iso:
        end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        if end_dt < now_utc() - timedelta(days=GRACE_PERIOD_DAYS):
            await db.subscriptions.update_one({"company_id": company_id}, {"$set": {"status": "suspended"}})
            return True, "subscription_expired"
    return False, ""
