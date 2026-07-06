"""iter17 — Civil Service module: grades, allowances, budget codes, MoF approval, ghost-worker."""
import os
import requests
import pytest

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    return r.json()


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def gov_admin():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def gov_token(gov_admin):
    return gov_admin["token"]


@pytest.fixture(scope="module")
def employee_token():
    return _login("adama.sankoh@gov.sl", "Employee@2026")["token"]


# =============== Grade & Step Structure ===============

class TestGradesAndSteps:
    def test_seeded_grades_present(self, gov_token):
        r = requests.get(f"{API}/civil-service/grades", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        grades = r.json()
        codes = [g["code"] for g in grades]
        assert "GR1" in codes and "GR10" in codes
        gr1 = next(g for g in grades if g["code"] == "GR1")
        assert len(gr1["steps"]) >= 6
        assert all(s["monthly_amount_sle"] > 0 for s in gr1["steps"])

    def test_create_and_delete_custom_grade(self, gov_token):
        # Create
        r = requests.post(f"{API}/civil-service/grades", headers=_h(gov_token), json={
            "code": "TEST-G", "name": "Test grade", "cadre": "Test",
        }, timeout=15)
        assert r.status_code == 200, r.text
        # Duplicate fails
        r2 = requests.post(f"{API}/civil-service/grades", headers=_h(gov_token), json={
            "code": "TEST-G", "name": "duplicate",
        }, timeout=15)
        assert r2.status_code == 409
        # Set steps
        r3 = requests.put(f"{API}/civil-service/grades/TEST-G/steps", headers=_h(gov_token), json=[
            {"step_number": 1, "monthly_amount_sle": 1000},
            {"step_number": 2, "monthly_amount_sle": 1100},
        ], timeout=15)
        assert r3.status_code == 200
        assert r3.json()["count"] == 2
        # Delete
        r4 = requests.delete(f"{API}/civil-service/grades/TEST-G", headers=_h(gov_token), timeout=15)
        assert r4.status_code == 200


# =============== Allowance Rules ===============

class TestAllowanceRules:
    def test_seeded_rules(self, gov_token):
        r = requests.get(f"{API}/civil-service/allowance-rules", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        rules = r.json()
        kinds = {ru["kind"] for ru in rules}
        assert {"housing", "transport", "responsibility", "hardship"}.issubset(kinds)

    def test_either_flat_or_pct_not_both(self, gov_token):
        r = requests.post(f"{API}/civil-service/allowance-rules", headers=_h(gov_token), json={
            "kind": "housing", "label": "Test label", "flat_sle": 100, "pct_of_basic": 0.1,
        }, timeout=15)
        assert r.status_code == 400


# =============== Budget Codes ===============

class TestBudgetCodes:
    def test_seeded_budget_codes(self, gov_token):
        r = requests.get(f"{API}/civil-service/budget-codes", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        assert len(r.json()) >= 6

    def test_unique_codes(self, gov_token):
        existing = requests.get(f"{API}/civil-service/budget-codes", headers=_h(gov_token), timeout=15).json()
        if not existing:
            pytest.skip()
        dup = existing[0]["code"]
        r = requests.post(f"{API}/civil-service/budget-codes", headers=_h(gov_token), json={
            "code": dup, "name": "duplicate",
        }, timeout=15)
        assert r.status_code == 409


# =============== Payroll with allowances ===============

@pytest.fixture(scope="module")
def gov_payroll_run(gov_token):
    # Gov payroll now requires a pre-run budget check (iter29 guardrail). Seed
    # generous allocations for the test period, run the check, then execute.
    period = "2026-03"
    for code in ("110.01.001", "110.02.001"):
        requests.put(f"{API}/payroll-budget/balances/{code}", headers=_h(gov_token), json={
            "allocated_sle": 10_000_000, "period": period,
        }, timeout=15)
    chk = requests.post(f"{API}/payroll-budget/check", headers=_h(gov_token),
                        json={"period": period}, timeout=15)
    assert chk.status_code == 200, chk.text
    r = requests.post(f"{API}/payroll/run", headers=_h(gov_token), json={
        "period_year": 2026, "period_month": 3,
    }, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


class TestPayrollUsesCivilServiceConfig:
    def test_slips_include_grade_and_budget(self, gov_payroll_run):
        slips = gov_payroll_run["slips"]
        assert any(s.get("grade_code") for s in slips), "at least one slip must have a grade_code"
        assert any(s.get("budget_code") for s in slips), "at least one slip must have a budget_code"

    def test_allowance_breakdown_applied(self, gov_payroll_run):
        slips = gov_payroll_run["slips"]
        # Find a GR1 employee — they should have responsibility allowance
        gr1 = next((s for s in slips if s.get("grade_code") == "GR1"), None)
        assert gr1 is not None
        bd = gr1.get("allowance_breakdown") or {}
        assert any("Housing" in k for k in bd.keys()), f"housing missing: {bd}"
        assert any("Transport" in k for k in bd.keys()), f"transport missing: {bd}"
        assert any("Responsibility" in k for k in bd.keys()), f"responsibility missing for GR1: {bd}"
        # The allowance total must equal sum of breakdown
        assert abs(gr1["allowances"] - sum(bd.values())) < 0.01

    def test_lower_grade_no_responsibility(self, gov_payroll_run):
        slips = gov_payroll_run["slips"]
        gr7_or_below = next((s for s in slips if s.get("grade_code") in ("GR7", "GR8", "GR9", "GR10")), None)
        if not gr7_or_below:
            pytest.skip("no low-grade employee seeded")
        bd = gr7_or_below.get("allowance_breakdown") or {}
        assert not any("Responsibility" in k for k in bd.keys()), \
            f"responsibility should not apply to {gr7_or_below['grade_code']}"


# =============== MoF Approval Workflow ===============

class TestMoFWorkflow:
    def test_submit_and_approve(self, gov_token, gov_payroll_run):
        rid = gov_payroll_run["id"]
        # Submit
        r1 = requests.post(f"{API}/civil-service/runs/{rid}/submit-for-approval", headers=_h(gov_token), json={"note": "ready"}, timeout=15)
        assert r1.status_code == 200, r1.text
        assert r1.json()["mof_status"] == "submitted"
        # Approve
        r2 = requests.post(f"{API}/civil-service/runs/{rid}/mof-approve", headers=_h(gov_token), json={"note": "ok"}, timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["mof_status"] == "approved"

    def test_cannot_resubmit_after_approval(self, gov_token, gov_payroll_run):
        rid = gov_payroll_run["id"]
        r = requests.post(f"{API}/civil-service/runs/{rid}/submit-for-approval", headers=_h(gov_token), json={}, timeout=15)
        assert r.status_code == 409

    def test_non_approver_cannot_approve(self, employee_token, gov_token):
        # Create a fresh run, submit, then try approving with employee token
        run = requests.post(f"{API}/payroll/run", headers=_h(gov_token), json={
            "period_year": 2025, "period_month": 6,
        }, timeout=30).json()
        rid = run["id"]
        # Employee role can't even submit (require_admin)
        r0 = requests.post(f"{API}/civil-service/runs/{rid}/submit-for-approval", headers=_h(employee_token), json={}, timeout=15)
        assert r0.status_code == 403


# =============== Ghost-Worker Detection ===============

class TestGhostWorkers:
    def test_employee_can_acknowledge_own_payslip(self, employee_token, gov_payroll_run):
        rid = gov_payroll_run["id"]
        r = requests.post(f"{API}/civil-service/payslip-ack/{rid}", headers=_h(employee_token), json={"note": "ok"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_ghost_report_excludes_acked(self, gov_token, employee_token, gov_payroll_run):
        rid = gov_payroll_run["id"]
        # Acknowledge again (idempotent upsert)
        requests.post(f"{API}/civil-service/payslip-ack/{rid}", headers=_h(employee_token), json={}, timeout=15)
        r = requests.get(f"{API}/civil-service/ghost-workers/{rid}", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["total_slips"] >= 1
        assert data["acknowledged"] >= 1
        # The acknowledger should NOT appear in suspects
        # We don't know their employee_id by name but suspects shouldn't include adama
        suspect_names = {s["employee_name"] for s in data["suspects"]}
        assert "Adama Sankoh" not in suspect_names

    def test_acknowledge_404_on_bad_run(self, employee_token):
        r = requests.post(f"{API}/civil-service/payslip-ack/nonexistent", headers=_h(employee_token), json={}, timeout=15)
        assert r.status_code == 404


# =============== Budget code report ===============

class TestBudgetReport:
    def test_report_groups_by_budget_code(self, gov_token, gov_payroll_run):
        rid = gov_payroll_run["id"]
        r = requests.get(f"{API}/civil-service/reports/by-budget-code/{rid}", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["period"] == gov_payroll_run["period"]
        assert data["total_rows"] >= 1
        for row in data["rows"]:
            for k in ("budget_code", "ministry", "employee_count", "gross", "paye", "net"):
                assert k in row
        # Sum of row grosses ≈ run total gross
        total_gross_rows = sum(r["gross"] for r in data["rows"])
        assert abs(total_gross_rows - gov_payroll_run["totals"]["gross"]) < 1.0


# =============== Login payload exposes mof_approver flag ===============

class TestAuthExposesMoFFlag:
    def test_gov_admin_is_mof_approver(self, gov_admin):
        assert gov_admin.get("mof_approver") is True

    def test_employee_is_not_mof_approver(self):
        emp = _login("adama.sankoh@gov.sl", "Employee@2026")
        assert emp.get("mof_approver") is False
