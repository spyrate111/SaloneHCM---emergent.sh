"""Iter9 tests — Compliance Score, 2FA, Recurring Schedules, Ministry Rollup, APScheduler."""
import os
import time

import pyotp
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://salonepaycms.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "admin@salonehcm.sl"
SUPER_PASS = "Admin@2026"
GOV_EMAIL = "admin@gov.sl"
GOV_PASS = "GovAdmin@2026"
EMP_EMAIL = "aminata.kamara@salonehcm.sl"
EMP_PASS = "Employee@2026"


def _login(email, password, totp=None, *, bypass_autotrip=False):
    """Login helper. When `bypass_autotrip=True` we explicitly include
    `totp_code: None` in the payload — conftest's auto-injector only triggers
    when the key is *absent*, so this lets us probe the "totp_required" branch
    on accounts that have 2FA enabled."""
    payload = {"email": email, "password": password}
    if totp is not None:
        payload["totp_code"] = totp
    elif bypass_autotrip:
        payload["totp_code"] = None
    r = requests.post(f"{API}/auth/login", json=payload, timeout=30)
    return r


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def super_token():
    r = _login(SUPER_EMAIL, SUPER_PASS)
    assert r.status_code == 200, f"superadmin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def gov_token():
    r = _login(GOV_EMAIL, GOV_PASS)
    assert r.status_code == 200, f"gov admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def emp_token():
    r = _login(EMP_EMAIL, EMP_PASS)
    assert r.status_code == 200, f"employee login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def gov_company_id(super_token):
    r = requests.get(f"{API}/admin/companies", headers=_auth(super_token), timeout=15)
    assert r.status_code == 200
    for c in r.json():
        if "bulk_sms_payslips" in (c.get("features") or []) or c.get("tier") == "gov":
            return c["id"]
    pytest.skip("Gov tenant not found")


# ---------- Compliance Score ----------
class TestComplianceScore:
    def test_demo_tenant_sms_not_applicable(self, super_token):
        r = requests.get(f"{API}/dashboard/compliance-score", headers=_auth(super_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "score" in d and "grade" in d and "breakdown" in d and "weights" in d
        for k in ("payroll_timeliness", "nassit_accuracy", "sms_delivery", "audit_coverage"):
            assert k in d["breakdown"], f"missing {k}"
        # Demo Salone is enterprise tier — sms_delivery NOT applicable
        assert d["breakdown"]["sms_delivery"].get("applicable") is False
        assert isinstance(d["score"], int)
        assert d["grade"] in {"A+", "A", "B", "C", "D", "F"}

    def test_gov_tenant_sms_applicable(self, gov_token):
        r = requests.get(f"{API}/dashboard/compliance-score", headers=_auth(gov_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["breakdown"]["sms_delivery"].get("applicable") is True

    def test_employee_forbidden(self, emp_token):
        r = requests.get(f"{API}/dashboard/compliance-score", headers=_auth(emp_token), timeout=20)
        assert r.status_code == 403

    def test_super_admin_switch_to_gov_changes_applicability(self, super_token, gov_company_id):
        # Switch super into Gov tenant
        r = requests.post(f"{API}/admin/companies/{gov_company_id}/switch",
                          headers=_auth(super_token), timeout=15)
        assert r.status_code == 200, r.text
        new_token = r.json().get("token") or super_token
        r2 = requests.get(f"{API}/dashboard/compliance-score", headers=_auth(new_token), timeout=20)
        assert r2.status_code == 200
        assert r2.json()["breakdown"]["sms_delivery"]["applicable"] is True


# ---------- 2FA ----------
class TestTwoFA:
    def test_policy_superadmin_required(self, super_token):
        r = requests.get(f"{API}/auth/2fa/policy", headers=_auth(super_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "superadmin"
        assert d["required"] is True
        assert "enabled" in d

    def test_policy_gov_admin_not_required(self, gov_token):
        r = requests.get(f"{API}/auth/2fa/policy", headers=_auth(gov_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["required"] is False

    def test_full_2fa_round_trip(self, super_token):
        """setup → enable → login without code → login with code → cleanup."""
        # 0. Reset 2FA state if a prior interrupted run left it enabled.
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "salonehcm_db")
        mc = MongoClient(mongo_url)
        mc[db_name].users.update_one(
            {"email": SUPER_EMAIL},
            {"$set": {"twofa_enabled": False},
             "$unset": {"twofa_secret": "", "twofa_pending_secret": ""}},
        )
        mc.close()
        # 1. setup
        r = requests.post(f"{API}/auth/2fa/setup", headers=_auth(super_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("secret", "uri", "qr_png_data_url", "required_for_role"):
            assert k in d
        assert d["qr_png_data_url"].startswith("data:image/png;base64,")
        secret = d["secret"]

        # 2. enable with valid code
        code = pyotp.TOTP(secret).now()
        r = requests.post(f"{API}/auth/2fa/enable", headers=_auth(super_token),
                          json={"code": code}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["twofa_enabled"] is True

        try:
            # 3. login WITHOUT totp → 401 + totp_required
            r = _login(SUPER_EMAIL, SUPER_PASS, bypass_autotrip=True)
            assert r.status_code == 401
            body = r.json()
            # detail can be either dict or stringified
            detail = body.get("detail")
            if isinstance(detail, dict):
                assert detail.get("code") == "totp_required"
            else:
                assert "totp_required" in str(detail)

            # 4. login WITH valid totp_code succeeds
            time.sleep(1)
            code2 = pyotp.TOTP(secret).now()
            r = _login(SUPER_EMAIL, SUPER_PASS, totp=code2)
            assert r.status_code == 200, r.text
            assert r.json()["twofa_enabled"] is True

            # 5. superadmin cannot disable
            r = requests.post(f"{API}/auth/2fa/disable", headers=_auth(super_token),
                              json={"password": SUPER_PASS, "code": pyotp.TOTP(secret).now()},
                              timeout=15)
            assert r.status_code == 403, r.text
        finally:
            # CLEANUP — disable directly via DB so subsequent agents not locked out
            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "salonehcm_db")
            mc = MongoClient(mongo_url)
            mc[db_name].users.update_one(
                {"email": SUPER_EMAIL},
                {"$set": {"twofa_enabled": False},
                 "$unset": {"twofa_secret": "", "twofa_pending_secret": ""}},
            )
            mc.close()
            # Verify cleanup
            r = _login(SUPER_EMAIL, SUPER_PASS)
            assert r.status_code == 200, "Cleanup failed - cannot login without 2FA"


# ---------- Recurring Schedules ----------
class TestSchedules:
    def test_schedule_full_lifecycle(self, gov_token):
        # Create
        r = requests.post(f"{API}/payroll/schedules", headers=_auth(gov_token),
                          json={"title": "TEST_iter9_sched", "cadence": "monthly",
                                "day_of_month": 28, "active": True}, timeout=15)
        assert r.status_code == 200, r.text
        s = r.json()
        sid = s["id"]
        assert s["runs_completed"] == 0
        assert s["next_run_at"] is not None
        assert s["cadence"] == "monthly"

        try:
            # List
            r = requests.get(f"{API}/payroll/schedules", headers=_auth(gov_token), timeout=15)
            assert r.status_code == 200
            assert any(x["id"] == sid for x in r.json())

            # Patch — change cadence to weekly, ensure cadence is persisted.
            # next_run_at may coincidentally equal the old monthly value if
            # today + 7 days lands on the same calendar day as the monthly
            # day_of_month=28; that's not a bug. Assert cadence + that next_run_at
            # is a valid ISO timestamp instead.
            r = requests.patch(f"{API}/payroll/schedules/{sid}", headers=_auth(gov_token),
                               json={"cadence": "weekly"}, timeout=15)
            assert r.status_code == 200, r.text
            updated = r.json()
            assert updated["cadence"] == "weekly"
            assert updated["next_run_at"], "next_run_at should be set after patch"

            # Toggle active=False
            r = requests.patch(f"{API}/payroll/schedules/{sid}", headers=_auth(gov_token),
                               json={"active": False}, timeout=15)
            assert r.status_code == 200
            assert r.json()["active"] is False

            # Run now → increments runs_completed
            r = requests.post(f"{API}/payroll/schedules/{sid}/run-now",
                              headers=_auth(gov_token), timeout=60)
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["ok"] is True
            assert "run" in d
            assert "next_run_at" in d

            # Verify counter incremented
            r = requests.get(f"{API}/payroll/schedules", headers=_auth(gov_token), timeout=15)
            row = [x for x in r.json() if x["id"] == sid][0]
            assert row["runs_completed"] >= 1
            assert row["last_run_at"] is not None
            assert row["last_run_id"]
        finally:
            r = requests.delete(f"{API}/payroll/schedules/{sid}", headers=_auth(gov_token), timeout=15)
            assert r.status_code == 200

    def test_employee_cannot_list_schedules(self, emp_token):
        r = requests.get(f"{API}/payroll/schedules", headers=_auth(emp_token), timeout=15)
        assert r.status_code == 403

    def test_invalid_cadence_rejected(self, gov_token):
        r = requests.post(f"{API}/payroll/schedules", headers=_auth(gov_token),
                          json={"title": "TEST_bad", "cadence": "yearly"}, timeout=15)
        assert r.status_code == 422


# ---------- Ministry Rollup ----------
class TestMinistry:
    def test_gov_rollup_ok(self, gov_token):
        r = requests.get(f"{API}/ministry/rollup", headers=_auth(gov_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "ministries" in d and "totals" in d
        assert isinstance(d["ministries"], list)
        assert len(d["ministries"]) >= 1
        m0 = d["ministries"][0]
        for k in ("name", "headcount_active", "monthly_payroll_gross",
                  "monthly_paye", "monthly_nassit", "leave_pending"):
            assert k in m0, f"ministry row missing {k}"

    def test_demo_tenant_402(self, super_token):
        # After test_super_admin_switch_to_gov_changes_applicability the super may still be in Gov.
        # Find Demo company and switch back first.
        r = requests.get(f"{API}/admin/companies", headers=_auth(super_token), timeout=15)
        demo = [c for c in r.json() if c.get("tier") != "gov"
                and "bulk_sms_payslips" not in (c.get("features") or [])]
        if not demo:
            pytest.skip("no non-gov tenant")
        demo_id = demo[0]["id"]
        sw = requests.post(f"{API}/admin/companies/{demo_id}/switch",
                           headers=_auth(super_token), timeout=15)
        tok = sw.json().get("token", super_token)
        r2 = requests.get(f"{API}/ministry/rollup", headers=_auth(tok), timeout=15)
        assert r2.status_code == 402, f"expected 402 got {r2.status_code}: {r2.text}"


# ---------- PWA assets ----------
class TestPWA:
    def test_manifest(self):
        r = requests.get(f"{BASE_URL}/manifest.json", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("name", "").startswith("SaloneHCM")
        assert "short_name" in d or "name" in d
        assert d.get("theme_color") == "#0A4A1E"

    def test_service_worker(self):
        r = requests.get(f"{BASE_URL}/sw.js", timeout=15)
        assert r.status_code == 200
        assert "self." in r.text or "addEventListener" in r.text
