"""iter24 — Verification of POST /api/integrations/sms/test (live Twilio).

WARNING: this test file invokes the live Twilio API. To preserve trial balance
we cap actual SMS sends at 2 (one happy path with explicit body, one with
default body). All other tests rely on validation/auth short-circuits and do
NOT cross the wire.
"""
import os
import re
import time
import requests
import pytest
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
TEST_RECIPIENT = "+18777804236"  # Twilio Virtual Phone test number
SID_PATTERN = re.compile(r"^SM[0-9a-f]{32}$")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "salonehcm_db")


def _login(email, password):
    r = requests.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def gov_token():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def employee_token():
    # Non-admin employee in demo tenant
    return _login("aminata.kamara@salonehcm.sl", "Employee@2026")


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)[DB_NAME]


# ---- AUTH MATRIX ----

class TestAuth:
    def test_unauthenticated_returns_401(self):
        r = requests.post(
            f"{API}/integrations/sms/test",
            json={"to": TEST_RECIPIENT, "body": "noauth"},
            timeout=15,
        )
        assert r.status_code in (401, 403), r.text

    def test_employee_returns_403(self, employee_token):
        r = requests.post(
            f"{API}/integrations/sms/test",
            headers=_h(employee_token),
            json={"to": TEST_RECIPIENT, "body": "no-admin"},
            timeout=15,
        )
        assert r.status_code == 403, r.text


# ---- INPUT VALIDATION ----

class TestValidation:
    def test_missing_to_returns_422(self, gov_token):
        r = requests.post(
            f"{API}/integrations/sms/test",
            headers=_h(gov_token),
            json={"body": "hi"},
            timeout=15,
        )
        assert r.status_code == 422, r.text

    def test_malformed_phone_returns_422(self, gov_token):
        r = requests.post(
            f"{API}/integrations/sms/test",
            headers=_h(gov_token),
            json={"to": "12345", "body": "bad-phone"},
            timeout=15,
        )
        assert r.status_code == 422, r.text
        # Helpful error message should mention E.164
        assert "E.164" in r.text or "e.164" in r.text.lower(), (
            f"Error response should mention E.164: {r.text}"
        )

    def test_body_too_long_returns_422(self, gov_token):
        long_body = "x" * 321  # >320 char cap on Pydantic model
        r = requests.post(
            f"{API}/integrations/sms/test",
            headers=_h(gov_token),
            json={"to": TEST_RECIPIENT, "body": long_body},
            timeout=15,
        )
        assert r.status_code == 422, r.text


# ---- HAPPY PATH (LIVE TWILIO SENDS) ----
# Capped: 2 actual sends total across this whole module.

class TestHappyPath:
    def test_status_reports_twilio_configured(self, gov_token):
        r = requests.get(f"{API}/integrations/status", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["twilio"]["configured"] is True

    def test_send_test_sms_with_explicit_body(self, gov_token, mongo_db):
        # LIVE SEND #1
        r = requests.post(
            f"{API}/integrations/sms/test",
            headers=_h(gov_token),
            json={"to": TEST_RECIPIENT, "body": "iter24 smoke — explicit body"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["to"] == TEST_RECIPIENT
        assert SID_PATTERN.match(data["sid"]), f"SID does not match SM+32hex: {data['sid']}"
        assert data["status"] in ("queued", "sent", "accepted"), data["status"]

        # Audit log row was written
        time.sleep(0.4)  # async fire-and-forget
        log = mongo_db.audit_logs.find_one(
            {"action": "sms_test_send", "meta.sid": data["sid"]}
        )
        assert log is not None, "expected audit_logs row with this SID"
        assert log["meta"]["to"] == TEST_RECIPIENT
        assert log["user_email"] == "admin@gov.sl"

    def test_send_test_sms_with_default_body(self, gov_token, mongo_db):
        # LIVE SEND #2 — omitting body should default to a templated message
        r = requests.post(
            f"{API}/integrations/sms/test",
            headers=_h(gov_token),
            json={"to": TEST_RECIPIENT},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert SID_PATTERN.match(data["sid"]), f"SID does not match SM+32hex: {data['sid']}"

        # The audit log doesn't store body; we just confirm the row exists for this SID
        time.sleep(0.4)
        log = mongo_db.audit_logs.find_one(
            {"action": "sms_test_send", "meta.sid": data["sid"]}
        )
        assert log is not None
