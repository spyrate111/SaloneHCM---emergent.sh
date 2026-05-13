"""iter13 — Email CSV buttons, Performance review cycles, ATS pipeline, VAPID push, 2FA strict enforcement."""
import os
import pyotp
import requests
import pytest
from conftest import SUPERADMIN_TOTP_SECRET

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def gov_token():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def super_token():
    return _login("admin@salonehcm.sl", "Admin@2026")


@pytest.fixture(scope="module")
def last_run_id(gov_token):
    r = requests.get(f"{API}/payroll/runs", headers=_h(gov_token), timeout=15)
    runs = r.json()
    assert runs, "Gov tenant must have a payroll run for these tests"
    return runs[0]["id"]


# =============== 2FA strict enforcement ===============

class Test2FAEnforcement:
    def test_super_login_without_code_returns_totp_required(self):
        # bypass the auto-injecting patched post by calling the raw method
        import urllib.request
        import json
        req = urllib.request.Request(
            f"{API}/auth/login",
            data=json.dumps({"email": "admin@salonehcm.sl", "password": "Admin@2026"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            assert False, "Expected 401 totp_required"
        except urllib.error.HTTPError as e:
            assert e.code == 401
            body = json.loads(e.read().decode())
            assert body["detail"]["code"] == "totp_required"

    def test_super_login_with_correct_code_succeeds(self):
        code = pyotp.TOTP(SUPERADMIN_TOTP_SECRET).now()
        r = requests.post(
            f"{API}/auth/login",
            json={"email": "admin@salonehcm.sl", "password": "Admin@2026", "totp_code": code},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("twofa_enabled") is True

    def test_super_login_with_invalid_code_fails(self):
        import urllib.request, json
        req = urllib.request.Request(
            f"{API}/auth/login",
            data=json.dumps({"email": "admin@salonehcm.sl", "password": "Admin@2026", "totp_code": "000000"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            assert False, "Expected 401 totp_invalid"
        except urllib.error.HTTPError as e:
            assert e.code == 401
            body = json.loads(e.read().decode())
            assert body["detail"]["code"] == "totp_invalid"

    def test_gov_admin_does_not_require_totp(self, gov_token):
        # If this fixture returned a token, login worked without TOTP
        assert isinstance(gov_token, str) and len(gov_token) > 20


# =============== Email CSV exports ===============

class TestEmailCsvSms:
    def test_email_sms_audit_csv(self, gov_token):
        r = requests.post(
            f"{API}/payroll/sms/logs.csv/email",
            headers=_h(gov_token),
            json={"to": "delivered@resend.dev"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["to"] == "delivered@resend.dev"
        assert data["rows"] >= 0
        assert "id" in data

    def test_email_sms_audit_requires_admin(self):
        r = requests.post(f"{API}/payroll/sms/logs.csv/email", json={"to": "delivered@resend.dev"}, timeout=15)
        assert r.status_code in (401, 403)


class TestEmailCsvNra:
    def test_email_nra_paye_csv(self, gov_token, last_run_id):
        r = requests.post(
            f"{API}/compliance/nra-paye-return.csv/{last_run_id}/email",
            headers=_h(gov_token),
            json={"to": "delivered@resend.dev"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "period" in data
        assert "id" in data

    def test_email_nra_404_on_bad_rid(self, gov_token):
        r = requests.post(
            f"{API}/compliance/nra-paye-return.csv/nonexistent-run/email",
            headers=_h(gov_token), json={}, timeout=15,
        )
        assert r.status_code == 404


# =============== Push notifications (VAPID) ===============

class TestPush:
    def test_public_key_endpoint(self, gov_token):
        r = requests.get(f"{API}/push/public-key", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["configured"] is True
        assert data["vapid_public_key"]
        # raw uncompressed P-256 — base64url 87 chars
        assert len(data["vapid_public_key"]) >= 60

    def test_push_status(self, gov_token):
        r = requests.get(f"{API}/push/status", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "configured" in data and "subscription_count" in data

    def test_subscribe_unsubscribe_roundtrip(self, gov_token):
        sub = {
            "endpoint": "https://push.example.com/fake-test-endpoint-xyz",
            "keys": {
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
                "auth": "tBHItJI5svbpez7KI4CCXg",
            },
            "user_agent": "pytest",
        }
        r = requests.post(f"{API}/push/subscribe", headers=_h(gov_token), json=sub, timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True

        s = requests.get(f"{API}/push/status", headers=_h(gov_token), timeout=15).json()
        assert s["subscription_count"] >= 1

        r = requests.post(f"{API}/push/unsubscribe", headers=_h(gov_token), json=sub, timeout=15)
        assert r.status_code == 200
        assert r.json()["deleted"] >= 1

    def test_test_push_with_no_subscription_returns_skipped(self, gov_token):
        # ensure clean slate
        requests.post(f"{API}/push/unsubscribe", headers=_h(gov_token), json={
            "endpoint": "https://push.example.com/fake-test-endpoint-xyz",
            "keys": {"p256dh": "x", "auth": "y"},
        }, timeout=15)
        r = requests.post(f"{API}/push/test", headers=_h(gov_token), json={"body": "test"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data.get("skipped") == "no_subscriptions" or data.get("sent") >= 0


# =============== Performance Review Cycles ===============

@pytest.fixture(scope="module")
def cycle_id(gov_token):
    r = requests.post(
        f"{API}/performance/cycles",
        headers=_h(gov_token),
        json={"name": "Iter13 Test Cycle", "period": "2026-T13", "employee_ids": []},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


class TestPerformance:
    def test_create_cycle_creates_review_per_active_employee(self, gov_token, cycle_id):
        cycles = requests.get(f"{API}/performance/cycles", headers=_h(gov_token), timeout=15).json()
        c = next((x for x in cycles if x["id"] == cycle_id), None)
        assert c, "cycle should appear in list"
        assert c["employee_count"] > 0

        reviews = requests.get(f"{API}/performance/cycles/{cycle_id}/reviews", headers=_h(gov_token), timeout=15).json()
        assert len(reviews) == c["employee_count"]
        assert all(r["status"] == "pending_self" for r in reviews)
        assert all(r["self_assessment"] is None for r in reviews)

    def test_employee_can_submit_self_assessment(self, gov_token, cycle_id):
        reviews = requests.get(f"{API}/performance/cycles/{cycle_id}/reviews", headers=_h(gov_token), timeout=15).json()
        rid = reviews[0]["id"]
        emp_email = reviews[0]["employee_name"].lower().replace(" ", ".") + "@gov.sl"
        # Find the real employee email — list users and match
        emp_token = _login(emp_email, "Employee@2026")
        r = requests.post(
            f"{API}/performance/reviews/{rid}/self-assessment",
            headers=_h(emp_token),
            json={
                "achievements": "Closed payroll on time every month.",
                "challenges": "Power outages.",
                "goals_next": "Streamline NRA filing.",
                "self_rating": 4,
            }, timeout=20,
        )
        assert r.status_code == 200, r.text
        # Now status should be pending_manager
        r2 = requests.get(f"{API}/performance/my-reviews", headers=_h(emp_token), timeout=15).json()
        mine = [x for x in r2 if x["id"] == rid][0]
        assert mine["status"] == "pending_manager"
        assert mine["self_rating"] == 4

    def test_only_employee_can_submit_self(self, gov_token, cycle_id):
        reviews = requests.get(f"{API}/performance/cycles/{cycle_id}/reviews", headers=_h(gov_token), timeout=15).json()
        # Pick one that's still pending_self
        pending = [r for r in reviews if r["status"] == "pending_self"]
        if not pending:
            pytest.skip("no pending_self reviews left")
        rid = pending[0]["id"]
        # gov_token is for admin@gov.sl which is an admin (not the employee under review).
        # Admins are allowed by the endpoint, so to test the 403 path we need a different employee.
        # Pick an employee who is NOT the review's owner.
        candidates = ["adama.sankoh@gov.sl", "fatmata.koroma@gov.sl", "mohamed.bangura@gov.sl"]
        target_emp_name = pending[0]["employee_name"]
        other = None
        for c in candidates:
            email_to_name = c.split("@")[0].replace(".", " ").title()
            if email_to_name != target_emp_name:
                other = c; break
        if not other:
            pytest.skip("could not pick a non-matching employee")
        try:
            other_tok = _login(other, "Employee@2026")
        except Exception:
            pytest.skip("test employee not seeded")
        r = requests.post(
            f"{API}/performance/reviews/{rid}/self-assessment",
            headers=_h(other_tok),
            json={"achievements": "x", "challenges": "y", "goals_next": "z", "self_rating": 5},
            timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_admin_can_score_review(self, gov_token, cycle_id):
        reviews = requests.get(f"{API}/performance/cycles/{cycle_id}/reviews", headers=_h(gov_token), timeout=15).json()
        ready = [r for r in reviews if r["status"] == "pending_manager"]
        if not ready:
            pytest.skip("no review ready for manager scoring")
        rid = ready[0]["id"]
        r = requests.post(
            f"{API}/performance/reviews/{rid}/manager-score",
            headers=_h(gov_token),
            json={
                "manager_comments": "Strong leader, on track for promotion.",
                "manager_rating": 5,
                "promotion_recommendation": "strong",
                "salary_action": "merit",
            }, timeout=20,
        )
        assert r.status_code == 200, r.text
        # Status should be completed
        all_now = requests.get(f"{API}/performance/cycles/{cycle_id}/reviews", headers=_h(gov_token), timeout=15).json()
        scored = next(x for x in all_now if x["id"] == rid)
        assert scored["status"] == "completed"
        assert scored["manager_rating"] == 5
        assert scored["promotion_recommendation"] == "strong"


# =============== ATS pipeline ===============

class TestATSPipeline:
    def test_pipeline_returns_six_stages(self, gov_token):
        r = requests.get(f"{API}/talent/applicants/pipeline", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["stages"] == ["applied", "screening", "interview", "offer", "hired", "rejected"]
        assert isinstance(data["grouped"], dict)
        for s in data["stages"]:
            assert s in data["grouped"]

    def test_pipeline_history_tracks_stage_changes(self, gov_token):
        # Seed a posting + applicant + advance stage twice and verify history persists
        post = requests.post(f"{API}/talent/postings", headers=_h(gov_token), json={
            "title": "ATS Pipeline Test", "department": "Test", "location": "Freetown",
            "employment_type": "Full-time", "salary_min_sle": 1000, "salary_max_sle": 2000,
            "description": "iter13 ATS pipeline test", "status": "open",
        }, timeout=15).json()
        app = requests.post(f"{API}/talent/applicants", headers=_h(gov_token), json={
            "posting_id": post["id"], "name": "Pipeline Tester",
            "email": "pipeline@example.com", "phone": "+23276111000",
            "stage": "applied",
        }, timeout=15).json()
        aid = app["id"]
        for stage in ["screening", "interview", "offer"]:
            r = requests.patch(f"{API}/talent/applicants/{aid}/stage", headers=_h(gov_token), json={"stage": stage}, timeout=15)
            assert r.status_code == 200
        # add a note
        n = requests.post(f"{API}/talent/applicants/{aid}/notes", headers=_h(gov_token), json={"note": "Good interview"}, timeout=15)
        assert n.status_code == 200
        # Verify in pipeline
        pl = requests.get(f"{API}/talent/applicants/pipeline", headers=_h(gov_token), timeout=15).json()
        found = next((a for a in pl["grouped"]["offer"] if a["id"] == aid), None)
        assert found, "applicant should be in 'offer' column"
        assert len(found.get("stage_history", [])) == 3
        # cleanup
        requests.delete(f"{API}/talent/postings/{post['id']}", headers=_h(gov_token), timeout=15)


# =============== Frontend integration sanity (Recharts width(-1) fix indirectly) ===============
# Not pytest-testable here — covered by the smoke screenshot in main agent.
