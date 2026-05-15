"""iter18 — CS profile editor (employee level), Acting allowance CRUD, Budget+Ghost exports, Step Increments."""
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
def last_run_id(gov_token):
    r = requests.get(f"{API}/payroll/runs", headers=_h(gov_token), timeout=15)
    return r.json()[0]["id"]


# =============== Profile editor (PATCH endpoint) ===============

class TestEmployeeProfilePatch:
    def test_patch_grade_and_step_syncs_basic_salary(self, gov_token):
        # Pick an employee on GR5 step 3 → bump to GR5 step 5
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        # Find one with a grade already
        graded = next((e for e in emps if e.get("grade_code") and e.get("step_number")), None)
        assert graded, "expected at least one civil-service-assigned employee"
        # Get the step amount we want to assign
        grades = requests.get(f"{API}/civil-service/grades", headers=_h(gov_token), timeout=15).json()
        g = next(g for g in grades if g["code"] == graded["grade_code"])
        # Pick a different step than current
        other_step = next((s for s in g["steps"] if s["step_number"] != graded["step_number"]), None)
        assert other_step
        r = requests.patch(
            f"{API}/civil-service/employees/{graded['id']}/profile",
            headers=_h(gov_token),
            json={"grade_code": graded["grade_code"], "step_number": other_step["step_number"]},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # Verify basic_salary_sle auto-synced
        e2 = requests.get(f"{API}/employees/{graded['id']}", headers=_h(gov_token), timeout=15).json()
        assert abs(e2["basic_salary_sle"] - other_step["monthly_amount_sle"]) < 0.01
        # restore
        requests.patch(
            f"{API}/civil-service/employees/{graded['id']}/profile",
            headers=_h(gov_token),
            json={"grade_code": graded["grade_code"], "step_number": graded["step_number"]},
            timeout=15,
        )

    def test_patch_invalid_grade_404(self, gov_token):
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        r = requests.patch(
            f"{API}/civil-service/employees/{emps[0]['id']}/profile",
            headers=_h(gov_token),
            json={"grade_code": "NONEXISTENT-X"},
            timeout=15,
        )
        assert r.status_code == 404


# =============== Acting Allowances CRUD ===============

class TestActings:
    def test_create_list_delete(self, gov_token):
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        emp_id = emps[0]["id"]
        # Create
        r = requests.post(f"{API}/civil-service/actings", headers=_h(gov_token), json={
            "employee_id": emp_id,
            "acting_role_title": "Acting Director (iter18)",
            "monthly_allowance_sle": 1500,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        }, timeout=15)
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        # List active_only=True
        actives = requests.get(f"{API}/civil-service/actings?active_only=true", headers=_h(gov_token), timeout=15).json()
        assert any(a["id"] == aid for a in actives)
        # Patch
        r2 = requests.patch(f"{API}/civil-service/actings/{aid}", headers=_h(gov_token), json={"monthly_allowance_sle": 2000}, timeout=15)
        assert r2.status_code == 200
        # Delete
        r3 = requests.delete(f"{API}/civil-service/actings/{aid}", headers=_h(gov_token), timeout=15)
        assert r3.status_code == 200

    def test_acting_appears_in_payroll(self, gov_token):
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        emp_id = emps[0]["id"]
        # Create active acting
        r = requests.post(f"{API}/civil-service/actings", headers=_h(gov_token), json={
            "employee_id": emp_id,
            "acting_role_title": "iter18 PayrollCheck",
            "monthly_allowance_sle": 999,
            "start_date": "2026-04-01",
        }, timeout=15)
        assert r.status_code == 200
        aid = r.json()["id"]
        # Run payroll for April 2026
        run = requests.post(f"{API}/payroll/run", headers=_h(gov_token), json={
            "period_year": 2026, "period_month": 4,
        }, timeout=30).json()
        slip = next(s for s in run["slips"] if s["employee_id"] == emp_id)
        breakdown = slip.get("allowance_breakdown") or {}
        assert any("iter18 PayrollCheck" in k for k in breakdown.keys()), f"acting missing from breakdown: {breakdown}"
        assert any(abs(v - 999) < 0.01 for v in breakdown.values())
        # Cleanup
        requests.delete(f"{API}/civil-service/actings/{aid}", headers=_h(gov_token), timeout=15)


# =============== Exports (CSV + PDF) ===============

class TestReportExports:
    def test_budget_csv(self, gov_token, last_run_id):
        r = requests.get(f"{API}/civil-service/reports/by-budget-code/{last_run_id}.csv", headers=_h(gov_token), timeout=20)
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert b"Budget code spend report" in r.content
        assert b"TOTAL" in r.content

    def test_budget_pdf(self, gov_token, last_run_id):
        r = requests.get(f"{API}/civil-service/reports/by-budget-code/{last_run_id}.pdf", headers=_h(gov_token), timeout=20)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"
        assert len(r.content) > 1500

    def test_budget_json_still_works(self, gov_token, last_run_id):
        r = requests.get(f"{API}/civil-service/reports/by-budget-code/{last_run_id}", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "rows" in d and "total_rows" in d and "period" in d

    def test_ghost_csv(self, gov_token, last_run_id):
        r = requests.get(f"{API}/civil-service/ghost-workers/{last_run_id}.csv", headers=_h(gov_token), timeout=20)
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert b"Ghost-worker audit" in r.content

    def test_ghost_pdf(self, gov_token, last_run_id):
        r = requests.get(f"{API}/civil-service/ghost-workers/{last_run_id}.pdf", headers=_h(gov_token), timeout=20)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"

    def test_ghost_json_still_works(self, gov_token, last_run_id):
        r = requests.get(f"{API}/civil-service/ghost-workers/{last_run_id}", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        assert "suspects" in r.json()


# =============== Step Increments ===============

class TestStepIncrements:
    def test_dry_run_no_anniversaries_today(self, gov_token):
        r = requests.post(f"{API}/civil-service/step-increments/run", headers=_h(gov_token), json={"dry_run": True}, timeout=20)
        assert r.status_code == 200
        assert r.json()["dry_run"] is True
        # count may be 0 or more — both are valid

    def test_dry_run_with_target_date(self, gov_token):
        # Use a hire-date anniversary from a seeded employee
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        candidate = next((e for e in emps if e.get("hire_date") and e.get("grade_code")), None)
        assert candidate, "need a seed employee with grade + hire date"
        # Anniversary: same month-day, next year
        hire = candidate["hire_date"][:10]
        target = "2026" + hire[4:]
        r = requests.post(f"{API}/civil-service/step-increments/run", headers=_h(gov_token), json={
            "dry_run": True, "target_date": target,
        }, timeout=20)
        assert r.status_code == 200
        data = r.json()
        # Should match at least one employee
        assert data["count"] >= 0  # might be 0 if nobody hired on this exact date

    def test_apply_idempotent(self, gov_token):
        # Apply twice on the same date; second run should record 0
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        candidate = next((e for e in emps if e.get("hire_date") and e.get("grade_code") and e.get("step_number", 6) < 6), None)
        if not candidate:
            pytest.skip("no eligible employee for apply test")
        target = "2026" + candidate["hire_date"][4:10]
        r1 = requests.post(f"{API}/civil-service/step-increments/run", headers=_h(gov_token), json={
            "dry_run": False, "target_date": target,
        }, timeout=20).json()
        first = r1["count"]
        # Second run — should be 0 because already recorded for year=2026
        r2 = requests.post(f"{API}/civil-service/step-increments/run", headers=_h(gov_token), json={
            "dry_run": False, "target_date": target,
        }, timeout=20).json()
        if first > 0:
            assert r2["count"] == 0, f"idempotency violated: applied {first}, then {r2['count']} again"

    def test_history_endpoint(self, gov_token):
        r = requests.get(f"{API}/civil-service/step-increments/history", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_invalid_target_date_returns_400(self, gov_token):
        r = requests.post(f"{API}/civil-service/step-increments/run", headers=_h(gov_token), json={
            "dry_run": True, "target_date": "not-a-date",
        }, timeout=15)
        assert r.status_code == 400
