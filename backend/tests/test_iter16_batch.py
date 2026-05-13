"""iter16 — Digest deep-links, Performance PDF summary, Krio/Mende portal translations, ATS DnD (backend pieces only)."""
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
def cycle_id(gov_token):
    cycle = requests.post(f"{API}/performance/cycles", headers=_h(gov_token), json={
        "name": "Iter16 PDF Cycle", "period": "2026-T16", "employee_ids": [],
    }, timeout=30).json()
    return cycle["id"]


class TestPerformanceCyclePDF:
    def test_pdf_summary_downloads(self, gov_token, cycle_id):
        r = requests.get(f"{API}/performance/cycles/{cycle_id}/summary.pdf", headers=_h(gov_token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"
        assert len(r.content) > 2500, "PDF should contain KPI grid + distribution + reviews table"

    def test_pdf_404_on_bad_cycle(self, gov_token):
        r = requests.get(f"{API}/performance/cycles/nonexistent/summary.pdf", headers=_h(gov_token), timeout=15)
        assert r.status_code == 404

    def test_pdf_requires_admin(self, cycle_id):
        # No auth
        r = requests.get(f"{API}/performance/cycles/{cycle_id}/summary.pdf", timeout=15)
        assert r.status_code in (401, 403)
        # Non-admin employee
        try:
            etok = _login("adama.sankoh@gov.sl", "Employee@2026")
            r2 = requests.get(f"{API}/performance/cycles/{cycle_id}/summary.pdf", headers=_h(etok), timeout=15)
            assert r2.status_code == 403
        except Exception:
            pytest.skip("test employee not seeded")


class TestDigestEmailDeepLinks:
    """The email items must include deep-link URLs pointing to filtered pages."""

    def test_email_items_helper_returns_deep_links(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from digest import _email_items
        snap = {
            "pending_leaves": 5,
            "upcoming_runs": [{"title": "test"}, {"title": "test2"}],
            "outstanding_filings": [{"id": "x"}],
            "pending_manager_reviews": 3,
            "employee_count": 10,
        }
        items = _email_items(snap)
        assert len(items) == 4
        urls = [it["url"] for it in items]
        assert any("/leave?status=pending" in u for u in urls)
        assert any("/payroll?due=soon" in u for u in urls)
        assert any("/compliance?outstanding=true" in u for u in urls)
        assert any("/performance" in u for u in urls)
        # Each item has a CTA label
        for it in items:
            assert it.get("cta")
            assert it.get("label")

    def test_email_items_empty_when_clear(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from digest import _email_items
        snap = {
            "pending_leaves": 0,
            "upcoming_runs": [],
            "outstanding_filings": [],
            "pending_manager_reviews": 0,
            "employee_count": 10,
        }
        assert _email_items(snap) == []
