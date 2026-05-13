"""iter12 — Twilio + Resend live integration wire-up validation."""
import os
import requests
import pytest

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
def demo_token():
    return _login("admin@salonehcm.sl", "Admin@2026")


class TestIntegrationsStatus:
    def test_status_returns_both_services(self, gov_token):
        r = requests.get(f"{API}/integrations/status", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "twilio" in data and "resend" in data
        assert "configured" in data["twilio"]
        assert "configured" in data["resend"]

    def test_status_requires_auth(self):
        r = requests.get(f"{API}/integrations/status", timeout=15)
        assert r.status_code in (401, 403)

    def test_twilio_configured_after_env_wireup(self, gov_token):
        r = requests.get(f"{API}/integrations/status", headers=_h(gov_token), timeout=15)
        assert r.json()["twilio"]["configured"] is True

    def test_resend_configured_after_env_wireup(self, gov_token):
        r = requests.get(f"{API}/integrations/status", headers=_h(gov_token), timeout=15)
        assert r.json()["resend"]["configured"] is True


class TestEmailTest:
    def test_send_test_email_to_resend_sandbox(self, gov_token):
        r = requests.post(
            f"{API}/integrations/email/test",
            headers=_h(gov_token),
            json={"to": "delivered@resend.dev", "subject": "iter12 smoke"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert data.get("id")

    def test_send_test_email_rejects_bad_email(self, gov_token):
        r = requests.post(
            f"{API}/integrations/email/test",
            headers=_h(gov_token),
            json={"to": "not-an-email"},
            timeout=15,
        )
        assert r.status_code == 422


class TestSmsStatusReflectsTwilio:
    def test_payroll_sms_status_says_configured(self, gov_token):
        r = requests.get(f"{API}/payroll/sms/status", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["twilio_configured"] is True


class TestSlugNormalisationRegression:
    """Original iter11 minor backend bug — non-alphanumeric chars must be stripped."""

    def test_slug_strips_non_alnum(self, gov_token):
        r = requests.post(
            f"{API}/public/transparency/admin/toggle",
            headers=_h(gov_token),
            json={"enabled": True, "slug": " Government TEST!!@@ "},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        # alphanumeric and hyphens only
        slug = r.json()["transparency_slug"]
        assert all(c.isalnum() or c == "-" for c in slug), f"unexpected chars in {slug!r}"

        # restore canonical slug
        requests.post(
            f"{API}/public/transparency/admin/toggle",
            headers=_h(gov_token),
            json={"enabled": True, "slug": "government-of-sierra-leone"},
            timeout=20,
        )

    def test_slug_empty_after_norm_returns_400(self, gov_token):
        r = requests.post(
            f"{API}/public/transparency/admin/toggle",
            headers=_h(gov_token),
            json={"enabled": True, "slug": "!!!@@@$$$"},
            timeout=20,
        )
        assert r.status_code == 400, r.text
