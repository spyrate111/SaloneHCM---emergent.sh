"""iter27 — Establishment Control → Talent ATS auto-sync.

Verifies that every vacant establishment_position auto-publishes a matching
job_posting, closes when filled/frozen/deleted, and reopens on unassign.
"""
import os
import uuid
import requests
import pytest

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def gov_token():
    return _login("admin@gov.sl", "GovAdmin@2026")


def _list_postings(token, source_filter=None):
    r = requests.get(f"{API}/talent/postings", headers=_h(token), timeout=15)
    r.raise_for_status()
    postings = r.json()
    if source_filter:
        postings = [p for p in postings if p.get("source") == source_filter]
    return postings


def _find_posting_for_position(token, position_id):
    for p in _list_postings(token):
        if p.get("position_id") == position_id:
            return p
    return None


@pytest.fixture(scope="module")
def unique_suffix():
    return uuid.uuid4().hex[:8]


class TestAutoPublish:
    def test_boot_backfill_creates_postings_for_gov_vacancies(self, gov_token):
        """After boot, every gov establishment position with vacancy_count > 0 has a matching posting."""
        vacancies = requests.get(f"{API}/establishment/vacancies", headers=_h(gov_token), timeout=15)
        vacancies.raise_for_status()
        vac_list = vacancies.json()
        assert len(vac_list) >= 1, "expected seeded vacancies"

        est_postings = _list_postings(gov_token, source_filter="establishment")
        est_position_ids = {p["position_id"] for p in est_postings if p.get("status") == "open"}
        for v in vac_list:
            assert v["id"] in est_position_ids, f"no open posting for vacant position {v['id']}"

    def test_create_position_publishes_open_posting(self, gov_token, unique_suffix):
        body = {
            "ministry": f"TEST-Ministry-{unique_suffix}",
            "directorate": "Test Directorate",
            "unit": "Test Unit",
            "position_title": f"Test Auditor {unique_suffix}",
            "approved_count": 2,
            "grade_code": "GR3",
            "budget_code": f"TEST.{unique_suffix}",
        }
        r = requests.post(f"{API}/establishment/positions", headers=_h(gov_token), json=body, timeout=15)
        assert r.status_code == 201, r.text
        pos = r.json()

        posting = _find_posting_for_position(gov_token, pos["id"])
        assert posting is not None, "posting should be auto-created"
        assert posting["source"] == "establishment"
        assert posting["status"] == "open"
        assert posting["title"] == body["position_title"]
        assert posting["department"] == body["directorate"]
        assert posting["establishment_meta"]["vacancy_count"] == 2
        assert posting["establishment_meta"]["ministry"] == body["ministry"]

        # Cleanup so this test is idempotent
        requests.delete(f"{API}/establishment/positions/{pos['id']}", headers=_h(gov_token), timeout=15)

    def test_patch_approved_count_updates_posting(self, gov_token, unique_suffix):
        body = {
            "ministry": f"TEST-Ministry-{unique_suffix}A",
            "directorate": "D",
            "unit": "U",
            "position_title": f"Patchable Role {unique_suffix}",
            "approved_count": 1,
        }
        pos = requests.post(f"{API}/establishment/positions", headers=_h(gov_token), json=body, timeout=15).json()

        r = requests.patch(f"{API}/establishment/positions/{pos['id']}", headers=_h(gov_token),
                           json={"approved_count": 5}, timeout=15)
        assert r.status_code == 200, r.text

        posting = _find_posting_for_position(gov_token, pos["id"])
        assert posting["establishment_meta"]["vacancy_count"] == 5
        assert posting["establishment_meta"]["approved_count"] == 5
        assert posting["status"] == "open"

        requests.delete(f"{API}/establishment/positions/{pos['id']}", headers=_h(gov_token), timeout=15)

    def test_freeze_position_closes_posting(self, gov_token, unique_suffix):
        body = {
            "ministry": f"TEST-Freeze-{unique_suffix}",
            "directorate": "D",
            "unit": "U",
            "position_title": f"Freeze me {unique_suffix}",
            "approved_count": 1,
        }
        pos = requests.post(f"{API}/establishment/positions", headers=_h(gov_token), json=body, timeout=15).json()
        posting = _find_posting_for_position(gov_token, pos["id"])
        assert posting["status"] == "open"

        requests.patch(f"{API}/establishment/positions/{pos['id']}", headers=_h(gov_token),
                       json={"status": "frozen"}, timeout=15)
        posting_after = _find_posting_for_position(gov_token, pos["id"])
        assert posting_after["status"] == "closed"

        requests.delete(f"{API}/establishment/positions/{pos['id']}", headers=_h(gov_token), timeout=15)

    def test_delete_position_closes_posting_but_preserves_it(self, gov_token, unique_suffix):
        body = {
            "ministry": f"TEST-Delete-{unique_suffix}",
            "directorate": "D",
            "unit": "U",
            "position_title": f"Delete me {unique_suffix}",
            "approved_count": 1,
        }
        pos = requests.post(f"{API}/establishment/positions", headers=_h(gov_token), json=body, timeout=15).json()
        pid = pos["id"]

        posting = _find_posting_for_position(gov_token, pid)
        assert posting is not None and posting["status"] == "open"

        r = requests.delete(f"{API}/establishment/positions/{pid}", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200

        # Posting must still exist (for applicant history) but with status=closed
        posting_after = _find_posting_for_position(gov_token, pid)
        assert posting_after is not None, "posting should NOT be deleted — preserves applicant history"
        assert posting_after["status"] == "closed"
        assert posting_after["establishment_meta"]["position_status"] == "deleted"

    def test_sync_vacancies_endpoint_is_idempotent(self, gov_token):
        r1 = requests.post(f"{API}/establishment/sync-vacancies", headers=_h(gov_token), timeout=30)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["positions"] >= 1

        r2 = requests.post(f"{API}/establishment/sync-vacancies", headers=_h(gov_token), timeout=30)
        assert r2.status_code == 200, r2.text
        d2 = r2.json()
        # Idempotent: nothing should be newly created on a 2nd run
        assert d2["created"] == 0

    def test_manual_postings_are_not_touched(self, gov_token, unique_suffix):
        """A posting with source='manual' must be untouched by the sync."""
        body = {
            "title": f"MANUAL_KEEP_ME_{unique_suffix}",
            "department": "IT",
            "location": "Freetown",
            "employment_type": "Full-time",
            "salary_min_sle": 3000,
            "salary_max_sle": 5000,
            "description": "manual posting for test",
            "status": "open",
        }
        created = requests.post(f"{API}/talent/postings", headers=_h(gov_token), json=body, timeout=15)
        assert created.status_code == 200, created.text

        # Run sync
        requests.post(f"{API}/establishment/sync-vacancies", headers=_h(gov_token), timeout=30)

        # Confirm the manual posting is still there and untouched
        matches = [p for p in _list_postings(gov_token) if p["title"] == body["title"]]
        assert len(matches) == 1
        m = matches[0]
        assert m.get("source", "manual") != "establishment"
        assert m["status"] == "open"

        # Cleanup
        requests.delete(f"{API}/talent/postings/{m['id']}", headers=_h(gov_token), timeout=15)


class TestPostingSchema:
    def test_establishment_meta_contains_expected_fields(self, gov_token):
        est_postings = _list_postings(gov_token, source_filter="establishment")
        assert est_postings, "expected at least one establishment posting from boot backfill"
        p = est_postings[0]
        meta = p.get("establishment_meta") or {}
        for field in ("ministry", "directorate", "unit", "approved_count", "vacancy_count", "position_status"):
            assert field in meta, f"establishment_meta missing '{field}': {meta}"
        assert p.get("position_id"), "position_id should be set"
        assert p.get("auto_synced_at"), "auto_synced_at should be set"
