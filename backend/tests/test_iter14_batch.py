"""iter14 — Magic-link invites, performance analytics, recurring training + certificates, daily digest."""
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


# =============== Magic-link invitations ===============

class TestMagicLinkInvite:
    def test_create_magic_invite_and_email_sends(self, gov_token):
        email = f"iter14-magic-{os.urandom(4).hex()}@example.com"
        r = requests.post(f"{API}/users/invite-magic", headers=_h(gov_token), json={
            "email": email, "name": "Magic Link Tester", "role": "employee",
        }, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email.lower()
        assert "expires_at" in data
        # email_status comes from Resend; ok=False is OK in tests if domain not verified for this address
        assert "email_status" in data

    def test_pending_invites_list(self, gov_token):
        invites = requests.get(f"{API}/users/invites", headers=_h(gov_token), timeout=15).json()
        assert isinstance(invites, list)

    def test_lookup_invite_works_without_auth(self, gov_token):
        # Pull a token from db directly via the invite-magic creation
        email = f"iter14-lookup-{os.urandom(4).hex()}@example.com"
        requests.post(f"{API}/users/invite-magic", headers=_h(gov_token), json={
            "email": email, "name": "Lookup Tester", "role": "employee",
        }, timeout=15)
        # Get token directly from DB through the test helper
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        async def grab():
            c = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            doc = await c["salonehcm_db"].user_invites.find_one({"email": email, "consumed_at": None}, {"_id": 0, "token": 1})
            return doc["token"]
        token = asyncio.run(grab())
        # No auth header
        r = requests.get(f"{API}/auth/invite/{token}", timeout=15)
        assert r.status_code == 200
        info = r.json()
        assert info["email"] == email
        assert info["company"]

    def test_lookup_unknown_invite_returns_404(self):
        r = requests.get(f"{API}/auth/invite/nonexistent-token-12345", timeout=15)
        assert r.status_code == 404
        d = r.json()["detail"]
        assert d.get("code") == "invite_invalid"

    def test_accept_invite_sets_password_and_creates_user(self, gov_token):
        email = f"iter14-accept-{os.urandom(4).hex()}@example.com"
        requests.post(f"{API}/users/invite-magic", headers=_h(gov_token), json={
            "email": email, "name": "Accept Tester", "role": "employee",
        }, timeout=15)
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        async def grab():
            c = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            doc = await c["salonehcm_db"].user_invites.find_one({"email": email, "consumed_at": None}, {"_id": 0, "token": 1})
            return doc["token"]
        token = asyncio.run(grab())

        r = requests.post(f"{API}/auth/accept-invite", json={"token": token, "password": "Iter14Accept!"}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == email
        assert body["role"] == "employee"
        assert body["token"]

        # Login works with the new password
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "Iter14Accept!"}, timeout=15)
        assert r2.status_code == 200, r2.text

        # Token now consumed; lookup returns 404
        r3 = requests.get(f"{API}/auth/invite/{token}", timeout=10)
        assert r3.status_code == 404

    def test_revoke_invite(self, gov_token):
        email = f"iter14-revoke-{os.urandom(4).hex()}@example.com"
        created = requests.post(f"{API}/users/invite-magic", headers=_h(gov_token), json={
            "email": email, "name": "Revoke Tester", "role": "employee",
        }, timeout=15).json()
        iid = created["id"]
        r = requests.delete(f"{API}/users/invites/{iid}", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        # Subsequent revoke errors with 404
        r2 = requests.delete(f"{API}/users/invites/{iid}", headers=_h(gov_token), timeout=15)
        assert r2.status_code == 404


# =============== Performance analytics ===============

@pytest.fixture(scope="module")
def cycle_with_data(gov_token):
    """Create a fresh cycle with at least one completed review for analytics."""
    cycle = requests.post(f"{API}/performance/cycles", headers=_h(gov_token), json={
        "name": "Iter14 Analytics Cycle", "period": "2026-T14", "employee_ids": [],
    }, timeout=30).json()
    cid = cycle["id"]
    reviews = requests.get(f"{API}/performance/cycles/{cid}/reviews", headers=_h(gov_token), timeout=15).json()
    # Submit self-assessment for first review (as the employee)
    r0 = reviews[0]
    emp_email = r0["employee_name"].lower().replace(" ", ".") + "@gov.sl"
    try:
        et = _login(emp_email, "Employee@2026")
        requests.post(f"{API}/performance/reviews/{r0['id']}/self-assessment", headers=_h(et), json={
            "achievements": "x", "challenges": "y", "goals_next": "z", "self_rating": 4,
        }, timeout=15)
        # Manager scores
        requests.post(f"{API}/performance/reviews/{r0['id']}/manager-score", headers=_h(gov_token), json={
            "manager_comments": "Great work", "manager_rating": 5,
            "promotion_recommendation": "strong", "salary_action": "merit",
        }, timeout=15)
    except Exception:
        pass
    return cid


class TestPerformanceAnalytics:
    def test_analytics_returns_full_shape(self, gov_token, cycle_with_data):
        r = requests.get(f"{API}/performance/cycles/{cycle_with_data}/analytics", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200, r.text
        a = r.json()
        for key in [
            "total_reviews", "completed", "completion_rate", "acknowledged",
            "acknowledgement_rate", "avg_self_rating", "avg_manager_rating",
            "rating_distribution", "promotion_recommendations", "salary_actions",
            "department_summary",
        ]:
            assert key in a
        assert set(a["rating_distribution"].keys()) == {"1", "2", "3", "4", "5"}
        assert set(a["promotion_recommendations"].keys()) >= {"none", "consider", "strong"}

    def test_analytics_reflects_at_least_one_completion(self, gov_token, cycle_with_data):
        a = requests.get(f"{API}/performance/cycles/{cycle_with_data}/analytics", headers=_h(gov_token), timeout=15).json()
        assert a["completed"] >= 1
        assert a["avg_manager_rating"] > 0
        # The 5-star slot must have at least 1 from our seed action
        assert a["rating_distribution"]["5"] >= 1
        assert a["promotion_recommendations"]["strong"] >= 1

    def test_analytics_404_on_bad_cycle(self, gov_token):
        r = requests.get(f"{API}/performance/cycles/nonexistent/analytics", headers=_h(gov_token), timeout=15)
        assert r.status_code == 404


# =============== Recurring training + certificate ===============

class TestRecurringTraining:
    def test_create_recurring_program_auto_sets_next_due(self, gov_token):
        r = requests.post(f"{API}/talent/programs", headers=_h(gov_token), json={
            "title": "iter14 GDPR Refresher", "hours": 2, "skill_area": "Compliance",
            "is_recurring": True, "frequency": "quarterly",
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_recurring"] is True
        assert data["frequency"] == "quarterly"
        assert data.get("next_due_at"), "next_due_at must be auto-computed when omitted"

    def test_completion_advances_next_due_at(self, gov_token):
        # Get one of our recurring programs
        progs = requests.get(f"{API}/talent/programs", headers=_h(gov_token), timeout=15).json()
        prog = next((p for p in progs if p.get("is_recurring")), None)
        assert prog, "needs at least one recurring program"
        prev_due = prog.get("next_due_at")
        # Add a completion
        emp = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()[0]
        completion = requests.post(f"{API}/talent/completions", headers=_h(gov_token), json={
            "program_id": prog["id"], "employee_id": emp["id"],
            "completed_on": "2026-05-13", "score": 88,
        }, timeout=15).json()
        # Re-fetch program
        progs2 = requests.get(f"{API}/talent/programs", headers=_h(gov_token), timeout=15).json()
        updated = next(p for p in progs2 if p["id"] == prog["id"])
        # next_due_at must have advanced relative to completion date
        assert updated["next_due_at"] > "2026-05-13"

    def test_certificate_pdf_downloads(self, gov_token):
        # Trigger a completion to download
        progs = requests.get(f"{API}/talent/programs", headers=_h(gov_token), timeout=15).json()
        prog = next((p for p in progs if p.get("is_recurring")), progs[0])
        emp = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()[0]
        comp = requests.post(f"{API}/talent/completions", headers=_h(gov_token), json={
            "program_id": prog["id"], "employee_id": emp["id"],
            "completed_on": "2026-05-13", "score": 92,
        }, timeout=15).json()
        r = requests.get(f"{API}/talent/completions/{comp['id']}/certificate.pdf", headers=_h(gov_token), timeout=20)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-", "must be a real PDF"
        assert len(r.content) > 1000

    def test_certificate_404_on_bad_id(self, gov_token):
        r = requests.get(f"{API}/talent/completions/nope/certificate.pdf", headers=_h(gov_token), timeout=15)
        assert r.status_code == 404

    def test_employee_can_only_download_own_certificate(self, gov_token):
        # Build a completion for the first employee
        progs = requests.get(f"{API}/talent/programs", headers=_h(gov_token), timeout=15).json()
        emp = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()[0]
        comp = requests.post(f"{API}/talent/completions", headers=_h(gov_token), json={
            "program_id": progs[0]["id"], "employee_id": emp["id"],
            "completed_on": "2026-05-13", "score": 70,
        }, timeout=15).json()
        # Try downloading as a DIFFERENT employee
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        other = next((e for e in emps if e["id"] != emp["id"]), None)
        if not other:
            pytest.skip("need at least 2 employees")
        other_email = other.get("email", "").lower()
        if not other_email.endswith("@gov.sl"):
            pytest.skip("no @gov.sl email on other employee")
        try:
            otok = _login(other_email, "Employee@2026")
        except Exception:
            pytest.skip("other employee has no user account")
        r = requests.get(f"{API}/talent/completions/{comp['id']}/certificate.pdf", headers=_h(otok), timeout=15)
        assert r.status_code == 403


# =============== Daily digest preview ===============

class TestDailyDigest:
    def test_digest_module_aggregates(self):
        """Smoke test the aggregator directly (no scheduling)."""
        import asyncio
        import sys
        sys.path.insert(0, "/app/backend")
        from digest import _aggregate_for_tenant
        # Pull a known company_id
        from motor.motor_asyncio import AsyncIOMotorClient
        async def main():
            c = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
            comp = await c["salonehcm_db"].companies.find_one({"name": "Government of Sierra Leone"}, {"_id": 0, "id": 1})
            snap = await _aggregate_for_tenant(comp["id"])
            assert "pending_leaves" in snap
            assert "upcoming_runs" in snap
            assert "outstanding_filings" in snap
            assert "pending_manager_reviews" in snap
            assert snap["employee_count"] > 0
        asyncio.run(main())
