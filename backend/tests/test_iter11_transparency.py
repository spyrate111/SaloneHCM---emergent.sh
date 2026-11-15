"""Iter11 — Public Open-Government Transparency Dashboard tests."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://salonepaycms.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER = {"email": "admin@salonehcm.sl", "password": "Admin@2026"}
GOV = {"email": "admin@gov.sl", "password": "GovAdmin@2026"}
GOV_SLUG = "government-of-sierra-leone"


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def gov_token():
    return _login(GOV)


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Public read endpoint (no auth) ----------
class TestPublicTransparency:
    def test_public_no_auth_returns_200(self):
        r = requests.get(f"{API}/public/transparency/{GOV_SLUG}", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "organization" in data
        assert "totals" in data
        assert "ministries" in data
        assert "compliance" in data
        org = data["organization"]
        for k in ("name", "country", "tier_label", "published_at"):
            assert k in org
        totals = data["totals"]
        for k in ("ministries", "headcount", "monthly_gross_sle", "monthly_paye_sle", "monthly_nassit_sle"):
            assert k in totals
        # last_payroll may be None
        assert "last_payroll" in data
        # compliance shape
        assert "returns_filed_12m" in data["compliance"]
        assert "most_recent_filing" in data["compliance"]
        assert "as_of" in data

    def test_ministries_ranked_by_gross_desc(self):
        r = requests.get(f"{API}/public/transparency/{GOV_SLUG}", timeout=20)
        rows = r.json()["ministries"]
        grosses = [m["monthly_gross_sle"] for m in rows]
        assert grosses == sorted(grosses, reverse=True)
        # headcount sums to totals
        data = r.json()
        assert data["totals"]["headcount"] == sum(m["headcount"] for m in rows)
        assert data["totals"]["ministries"] == len(rows)

    def test_unknown_slug_404(self):
        r = requests.get(f"{API}/public/transparency/this-slug-does-not-exist-xyz", timeout=20)
        assert r.status_code == 404

    def test_privacy_invariant_no_pii(self):
        """Response must contain ZERO personally identifiable employee data."""
        r = requests.get(f"{API}/public/transparency/{GOV_SLUG}", timeout=20)
        assert r.status_code == 200
        body = r.text.lower()
        # No emails in response
        assert "@gov.sl" not in body
        assert "@salonehcm.sl" not in body
        assert not re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", body), "Email leaked in public response"
        data = r.json()
        forbidden_keys = {"email", "phone", "tin", "nassit_number", "employee_id", "first_name",
                         "last_name", "national_id", "bank_account", "salary"}

        def _walk(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    kl = k.lower()
                    # Allow innocuous "name" only for organization/ministry
                    if kl in forbidden_keys:
                        raise AssertionError(f"PII key '{k}' found at {path}")
                    _walk(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _walk(v, f"{path}[{i}]")

        _walk(data)

    def test_tenant_isolation_no_demo_data(self):
        """Gov public response must not contain any Demo Salone employees / ministries."""
        r = requests.get(f"{API}/public/transparency/{GOV_SLUG}", timeout=20)
        assert r.status_code == 200
        body = r.text.lower()
        # Demo Salone has e.g. 'aminata kamara' / 'salonehcm' references — none should appear
        assert "demo salone" not in body
        assert "salonehcm.sl" not in body


# ---------- Auth required for admin endpoints ----------
class TestAdminAuthRequired:
    def test_admin_status_requires_auth(self):
        r = requests.get(f"{API}/public/transparency/admin/status", timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_toggle_requires_auth(self):
        r = requests.post(f"{API}/public/transparency/admin/toggle", json={"enabled": True}, timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_views_requires_auth(self):
        r = requests.get(f"{API}/public/transparency/admin/views", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Admin status + views ----------
class TestAdminStatusViews:
    def test_status_gov_admin(self, gov_token):
        r = requests.get(f"{API}/public/transparency/admin/status", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert d["slug"] == GOV_SLUG
        assert d["public_url"] == f"/transparency/{GOV_SLUG}"
        assert d["published_at"]

    def test_views_increment(self, gov_token):
        before = requests.get(f"{API}/public/transparency/admin/views", headers=_h(gov_token), timeout=15)
        assert before.status_code == 200
        b_total = before.json()["total_views"]
        # trigger 2 public reads
        requests.get(f"{API}/public/transparency/{GOV_SLUG}", timeout=15)
        requests.get(f"{API}/public/transparency/{GOV_SLUG}", timeout=15)
        after = requests.get(f"{API}/public/transparency/admin/views", headers=_h(gov_token), timeout=15)
        assert after.status_code == 200
        a_total = after.json()["total_views"]
        assert a_total >= b_total + 2, f"views did not increment: {b_total}->{a_total}"
        assert "last_7d" in after.json()


# ---------- Toggle: slug uniqueness, normalisation, audit ----------
class TestToggle:
    def test_slug_clash_returns_409(self, super_token):
        # super_token = Demo Salone. Trying to take the Gov-tenant slug should 409.
        r = requests.post(
            f"{API}/public/transparency/admin/toggle",
            headers=_h(super_token),
            json={"enabled": True, "slug": GOV_SLUG},
            timeout=20,
        )
        assert r.status_code == 409, f"expected 409 clash, got {r.status_code} {r.text}"

    def test_slug_normalisation_strips_non_alnum(self, super_token):
        """Spec: body.slug normalises to lowercase alphanumeric + hyphens."""
        # Try a dirty slug — backend should normalise to alphanumeric + hyphens only
        dirty = " Demo-Salone-TEST!!@@ "
        r = requests.post(
            f"{API}/public/transparency/admin/toggle",
            headers=_h(super_token),
            json={"enabled": True, "slug": dirty},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        saved = r.json()["transparency_slug"]
        # Must contain only [a-z0-9-]
        assert re.fullmatch(r"[a-z0-9-]+", saved), f"slug not normalised: '{saved}'"
        # cleanup
        requests.post(
            f"{API}/public/transparency/admin/toggle",
            headers=_h(super_token),
            json={"enabled": False},
            timeout=20,
        )

    def test_demo_can_publish_own_slug_then_unpublish(self, super_token):
        unique_slug = "demo-salone-transparency-test"
        r = requests.post(
            f"{API}/public/transparency/admin/toggle",
            headers=_h(super_token),
            json={"enabled": True, "slug": unique_slug},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["transparency_public"] is True
        assert body["transparency_slug"] == unique_slug
        # status reflects
        s = requests.get(f"{API}/public/transparency/admin/status", headers=_h(super_token), timeout=15)
        assert s.status_code == 200 and s.json()["enabled"] is True
        # public read works
        pub = requests.get(f"{API}/public/transparency/{unique_slug}", timeout=15)
        assert pub.status_code == 200
        # tenant isolation: Demo's public response must NOT contain Gov data
        assert "gov.sl" not in pub.text.lower()
        # unpublish
        off = requests.post(
            f"{API}/public/transparency/admin/toggle",
            headers=_h(super_token),
            json={"enabled": False},
            timeout=20,
        )
        assert off.status_code == 200
        assert off.json()["transparency_public"] is False
        # public read now 404
        pub2 = requests.get(f"{API}/public/transparency/{unique_slug}", timeout=15)
        assert pub2.status_code == 404
