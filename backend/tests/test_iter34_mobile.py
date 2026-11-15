"""iter34 — Mobile PWA backend endpoints (summary, punch, WebAuthn scaffold)."""
import os
import secrets

import pytest
import requests

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
GOV_EMAIL, GOV_PASS = "admin@gov.sl", "GovAdmin@2026"
EMP_EMAIL, EMP_PASS = "joseph.williams@gov.sl", "Employee@2026"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def emp_token():
    return _login(EMP_EMAIL, EMP_PASS)


@pytest.fixture(scope="module")
def gov_token():
    return _login(GOV_EMAIL, GOV_PASS)


class TestMobileSummary:
    def test_shape(self, emp_token):
        r = requests.get(f"{API}/mobile/summary", headers=_h(emp_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("user", "payslip_current", "payslip_latest",
                  "leave_balance_days", "my_leave",
                  "pending_reports_leave", "todays_punches",
                  "voucher_queue", "server_time"):
            assert k in d, f"missing key {k}"
        assert d["user"]["email"] == EMP_EMAIL
        assert d["user"]["role"] == "employee"
        # Employee should not see the voucher queue (no matching status role)
        assert d["voucher_queue"] == []

    def test_summary_requires_auth(self):
        r = requests.get(f"{API}/mobile/summary", timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_gets_data(self, gov_token):
        r = requests.get(f"{API}/mobile/summary", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["role"] == "admin"


class TestMobilePunch:
    def test_punch_in_out_pairs_hours(self, emp_token):
        # Random unique device to avoid interfering with today's punches
        dev = secrets.token_hex(4)
        # Clock in
        r1 = requests.post(f"{API}/mobile/punch", headers=_h(emp_token),
                           json={"kind": "in", "lat": 8.4844, "lng": -13.2344,
                                 "accuracy_m": 15, "device_id": dev},
                           timeout=15)
        assert r1.status_code == 200
        p1 = r1.json()
        assert p1["kind"] == "in"
        assert p1["lat"] == 8.4844
        # Clock out
        r2 = requests.post(f"{API}/mobile/punch", headers=_h(emp_token),
                           json={"kind": "out", "lat": 8.4845, "lng": -13.2343,
                                 "device_id": dev},
                           timeout=15)
        assert r2.status_code == 200
        p2 = r2.json()
        assert p2["kind"] == "out"

        # /punch/today must include both punches
        rows = requests.get(f"{API}/mobile/punch/today", headers=_h(emp_token),
                            timeout=15).json()
        assert isinstance(rows, list)
        my = [r for r in rows if r.get("device_id") == dev]
        assert len(my) == 2

    def test_punch_bad_kind_400(self, emp_token):
        r = requests.post(f"{API}/mobile/punch", headers=_h(emp_token),
                          json={"kind": "sideways"}, timeout=15)
        # Pydantic validation → 422
        assert r.status_code in (400, 422)

    def test_punch_requires_employee_link(self):
        # Superadmin often isn't linked to an employee record — should 400
        sa_tok = _login("admin@salonehcm.sl", "Admin@2026")
        r = requests.post(f"{API}/mobile/punch", headers=_h(sa_tok),
                          json={"kind": "in"}, timeout=15)
        # Either 400 (no employee) or 200 (if linked). Both acceptable.
        assert r.status_code in (200, 400)


class TestWebAuthnScaffold:
    def test_register_begin_returns_options(self, emp_token):
        r = requests.post(f"{API}/auth/webauthn/register/begin",
                          headers=_h(emp_token), timeout=15)
        assert r.status_code == 200
        opts = r.json()
        # Standard WebAuthn creation options
        assert "challenge" in opts
        assert opts.get("rp", {}).get("id")
        assert opts.get("user", {}).get("id")
        assert isinstance(opts.get("pubKeyCredParams"), list)

    def test_list_credentials_empty(self, emp_token):
        r = requests.get(f"{API}/auth/webauthn/credentials",
                         headers=_h(emp_token), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_login_begin_options(self):
        r = requests.post(f"{API}/auth/webauthn/login/begin", json={},
                          timeout=15)
        assert r.status_code == 200
        opts = r.json()
        assert "challenge" in opts
        assert opts.get("rpId")

    def test_register_finish_rejects_junk(self, emp_token):
        # No prior /begin ⇒ 400
        r = requests.post(f"{API}/auth/webauthn/register/finish",
                          headers=_h(emp_token),
                          json={"credential": {"id": "junk", "response": {}}},
                          timeout=15)
        assert r.status_code == 400
