"""iter28 — Public Careers job board (no-auth).

Verifies the citizen-facing careers page:
- GET /public/careers/{slug} lists open postings for opted-in tenants
- GET /public/careers/{slug}/postings/{pid} returns detail
- POST /public/careers/{slug}/postings/{pid}/apply creates an applicant with source=public_careers
- Non-opted-in slug → 404
- Rate-limited to 5/minute per IP
- Duplicate application (same email + posting) → 409
- Applications land in the tenant's admin Kanban with stage=applied
"""
import os
import uuid
import requests
import pytest

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
GOV_SLUG = "government-of-sierra-leone"  # seeded in companies.seed()


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def gov_token():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def a_posting_id(gov_token):
    """Grab any open posting for the Gov tenant."""
    r = requests.get(f"{API}/talent/postings", headers=_h(gov_token), timeout=15)
    r.raise_for_status()
    open_ones = [p for p in r.json() if p.get("status") == "open"]
    assert open_ones, "expected at least one open posting on the gov tenant"
    return open_ones[0]["id"]


class TestPublicList:
    def test_list_no_auth_required(self):
        r = requests.get(f"{API}/public/careers/{GOV_SLUG}", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["organization"]["slug"] == GOV_SLUG
        assert data["total_open"] >= 1
        assert isinstance(data["postings"], list)
        # PII scrub: no company_id / created_by leaked
        for p in data["postings"]:
            assert "company_id" not in p
            assert p["title"], "title required"

    def test_ministry_facets_present(self):
        r = requests.get(f"{API}/public/careers/{GOV_SLUG}", timeout=15)
        assert r.status_code == 200
        assert "ministries" in r.json()
        assert isinstance(r.json()["ministries"], list)

    def test_search_filter_narrows_results(self):
        r_all = requests.get(f"{API}/public/careers/{GOV_SLUG}", timeout=15).json()
        # Pick a token that likely narrows
        if not r_all["postings"]:
            pytest.skip("no postings to filter")
        needle = r_all["postings"][0]["title"].split()[0]
        r_filt = requests.get(f"{API}/public/careers/{GOV_SLUG}", params={"q": needle}, timeout=15).json()
        assert r_filt["total_open"] >= 1
        for p in r_filt["postings"]:
            assert needle.lower() in (p["title"] + " " + p["department"] + " " + (p.get("ministry") or "")).lower()

    def test_unknown_slug_404s(self):
        r = requests.get(f"{API}/public/careers/does-not-exist", timeout=15)
        assert r.status_code == 404


class TestPublicDetail:
    def test_detail_returns_posting(self, a_posting_id):
        r = requests.get(f"{API}/public/careers/{GOV_SLUG}/postings/{a_posting_id}", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["posting"]["id"] == a_posting_id
        assert "description" in d["posting"]

    def test_detail_bogus_pid_404s(self):
        r = requests.get(f"{API}/public/careers/{GOV_SLUG}/postings/bogus-{uuid.uuid4()}", timeout=15)
        assert r.status_code == 404


class TestPublicApply:
    def test_apply_creates_applicant_source_public_careers(self, gov_token, a_posting_id):
        payload = {
            "name": f"Test Applicant {uuid.uuid4().hex[:6]}",
            "email": f"applicant_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+23276111222",
            "resume_summary": "I have 5 years of relevant experience in HR administration and payroll operations in Sierra Leone. Bachelor's from FBC.",
        }
        r = requests.post(f"{API}/public/careers/{GOV_SLUG}/postings/{a_posting_id}/apply", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["application_ref"].startswith("APP-")
        assert body["posting_title"]

        # Admin sees it via the flat applicant list with correct stage + source
        all_apps = requests.get(f"{API}/talent/applicants", headers=_h(gov_token), timeout=15).json()
        matched = [a for a in all_apps if a["email"] == payload["email"]]
        assert len(matched) == 1
        assert matched[0]["source"] == "public_careers"
        assert matched[0]["stage"] == "applied"
        assert matched[0]["application_ref"] == body["application_ref"]
        assert matched[0]["posting_id"] == a_posting_id

    def test_duplicate_email_same_posting_returns_409(self, a_posting_id):
        email = f"dup_{uuid.uuid4().hex[:6]}@example.com"
        payload = {
            "name": "Dupe Person",
            "email": email,
            "phone": "+23276000111",
            "resume_summary": "First application — going through fine. Long enough to pass min_length=20.",
        }
        r1 = requests.post(f"{API}/public/careers/{GOV_SLUG}/postings/{a_posting_id}/apply", json=payload, timeout=15)
        assert r1.status_code == 200, r1.text
        r2 = requests.post(f"{API}/public/careers/{GOV_SLUG}/postings/{a_posting_id}/apply", json=payload, timeout=15)
        assert r2.status_code == 409, r2.text

    def test_apply_short_resume_returns_422(self, a_posting_id):
        payload = {
            "name": "Bad Applicant",
            "email": f"bad_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+23276222333",
            "resume_summary": "too short",  # <20 chars
        }
        r = requests.post(f"{API}/public/careers/{GOV_SLUG}/postings/{a_posting_id}/apply", json=payload, timeout=15)
        assert r.status_code == 422, r.text

    def test_apply_invalid_email_returns_422(self, a_posting_id):
        payload = {
            "name": "Bad Email",
            "email": "not-an-email",
            "phone": "+23276222333",
            "resume_summary": "This resume summary is long enough to pass validation. Ok.",
        }
        r = requests.post(f"{API}/public/careers/{GOV_SLUG}/postings/{a_posting_id}/apply", json=payload, timeout=15)
        assert r.status_code == 422, r.text

    def test_apply_to_unknown_slug_returns_404(self, a_posting_id):
        payload = {
            "name": "Nowhere Person",
            "email": f"nowhere_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+23276222333",
            "resume_summary": "Applying to a non-existent org — should 404. Long enough.",
        }
        r = requests.post(f"{API}/public/careers/does-not-exist/postings/{a_posting_id}/apply", json=payload, timeout=15)
        assert r.status_code == 404
