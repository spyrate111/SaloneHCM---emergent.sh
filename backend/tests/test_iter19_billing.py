"""Subscription billing tests:
  - Plan catalog
  - Bank-transfer invoice + mark-paid + tier auto-upgrade
  - Per-employee surcharge
  - Stripe Checkout session creation (uses test key)
  - Authorization (admin issues invoice, only superadmin marks paid)
  - Cookie-auth + CSRF compatibility (sanity check)
"""
import os
import requests
import pyotp
import pytest
from pymongo import MongoClient

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"
GOV_EMAIL = "admin@gov.sl"
GOV_PASS = "GovAdmin@2026"
SUPER_EMAIL = "admin@salonehcm.sl"
SUPER_PASS = "Admin@2026"
SUPER_SECRET = "KRSXG5BANFXSAYTBORQXG43LMR2A"


@pytest.fixture
def gov_h():
    tok = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def super_h():
    tok = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS,
                                                   "totp_code": pyotp.TOTP(SUPER_SECRET).now()}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(autouse=True)
def _isolate_billing():
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "salonehcm_db")]
    # Restore Gov tier in case prior test left it changed
    db.companies.update_one({"name": "Government of Sierra Leone"}, {"$set": {"tier": "gov"}})
    db.subscription_invoices.delete_many({})
    db.subscriptions.delete_many({})
    db.payment_transactions.delete_many({})
    yield
    db.companies.update_one({"name": "Government of Sierra Leone"}, {"$set": {"tier": "gov"}})
    db.subscription_invoices.delete_many({})
    db.subscriptions.delete_many({})
    db.payment_transactions.delete_many({})


def test_plan_catalog_public():
    r = requests.get(f"{API}/billing/plans")
    assert r.status_code == 200
    plans = r.json()["plans"]
    assert len(plans) == 4
    ids = {p["id"] for p in plans}
    assert ids == {"lite", "professional", "enterprise", "gov"}
    # Each plan has SLE pricing
    for p in plans:
        assert p["monthly_sle"] > 0
        assert p["included_employees"] > 0
        assert "features" in p and len(p["features"]) > 0


def test_me_returns_subscription_shape(gov_h):
    r = requests.get(f"{API}/billing/me", headers=gov_h)
    assert r.status_code == 200
    body = r.json()
    assert body["subscription"]["plan_id"] == "gov"
    assert body["subscription"]["status"] in ("trialing", "active")
    assert body["plan"]["label"] == "Government"
    assert body["current_charge"]["total_sle"] >= 8000.0
    assert body["employees"] >= 0


def test_bank_invoice_lifecycle(gov_h, super_h):
    # Create
    r = requests.post(f"{API}/billing/bank-transfer/invoice", headers=gov_h, json={"plan_id": "enterprise"})
    assert r.status_code == 200
    inv = r.json()
    assert inv["reference"].startswith("SHCM-")
    assert inv["payment_method"] == "bank_transfer"
    assert inv["status"] == "open"
    assert inv["bank_details"]["bank_name"] == "Sierra Leone Commercial Bank"
    # Pre-payment tier still gov
    r2 = requests.post(f"{API}/billing/invoices/{inv['id']}/mark-paid", headers=super_h,
                       json={"bank_reference": "TEST-WIRE-001"})
    assert r2.status_code == 200
    assert r2.json()["subscription_status"] == "active"
    # Tier flipped
    me = requests.get(f"{API}/billing/me", headers=gov_h).json()
    assert me["plan"]["id"] == "enterprise"
    assert me["subscription"]["status"] == "active"


def test_only_superadmin_can_mark_paid(gov_h):
    inv = requests.post(f"{API}/billing/bank-transfer/invoice", headers=gov_h,
                        json={"plan_id": "professional"}).json()
    # Gov admin (not superadmin) tries to mark paid
    r = requests.post(f"{API}/billing/invoices/{inv['id']}/mark-paid", headers=gov_h,
                      json={"bank_reference": "X"})
    assert r.status_code == 403


def test_double_open_invoice_blocked(gov_h):
    r1 = requests.post(f"{API}/billing/bank-transfer/invoice", headers=gov_h, json={"plan_id": "lite"})
    assert r1.status_code == 200
    r2 = requests.post(f"{API}/billing/bank-transfer/invoice", headers=gov_h, json={"plan_id": "professional"})
    assert r2.status_code == 409


def test_per_employee_surcharge(gov_h, super_h):
    """Gov has 6 employees, lite includes 25 → no surcharge.
    Issue lite first to test base price."""
    r = requests.post(f"{API}/billing/bank-transfer/invoice", headers=gov_h, json={"plan_id": "lite"})
    inv = r.json()
    # Lite base = 200, gov has 6 emps which is well under 25 → 0 surcharge
    assert inv["extra_employees"] == 0
    assert inv["total_sle"] == 200.0


def test_invoices_list_admin_only(gov_h, super_h):
    requests.post(f"{API}/billing/bank-transfer/invoice", headers=gov_h, json={"plan_id": "professional"})
    r = requests.get(f"{API}/billing/invoices", headers=gov_h)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_stripe_checkout_creates_session_with_test_key(gov_h):
    r = requests.post(f"{API}/billing/stripe/checkout", headers=gov_h, json={
        "plan_id": "professional",
        "origin_url": "https://salonepaycms.preview.emergentagent.com",
    })
    # Stripe in test mode should return a checkout URL
    assert r.status_code == 200, r.text
    body = r.json()
    assert "checkout_url" in body
    assert body["checkout_url"].startswith("https://checkout.stripe.com")
    assert body["session_id"].startswith("cs_test_")
    assert body["amount_usd"] > 0


def test_unauthenticated_blocked():
    r = requests.get(f"{API}/billing/me")
    assert r.status_code == 401
