"""SaloneHCM iteration 4 — AI Action Mode + CSV writer + context ids tests."""
import csv
import io
import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://salonepaycms.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@salonehcm.sl", "password": "Admin@2026"}
EMPLOYEE = {"email": "aminata.kamara@salonehcm.sl", "password": "Employee@2026"}


def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def employee_token():
    r = requests.post(f"{API}/auth/login", json=EMPLOYEE, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------- build_company_context: id= prefix verification ----------
def test_assistant_context_includes_id_prefix(admin_token):
    """Context must include id= prefix for employees, leaves, payroll runs."""
    r = requests.get(f"{API}/assistant/context", headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    ctx = r.json()["context"]
    assert "EMPLOYEES" in ctx
    # employees always present (seed)
    assert "id=" in ctx, "context missing 'id=' prefix"
    # employees lines start with "- id="
    assert "- id=" in ctx


def test_assistant_context_employee_forbidden(employee_token):
    r = requests.get(f"{API}/assistant/context", headers=H(employee_token), timeout=30)
    assert r.status_code == 403


# ---------- Action mode chat: admin & employee ----------
def test_assistant_chat_action_mode_admin(admin_token):
    """Admin with action_mode=true should get a parseable plan."""
    payload = {
        "message": "Approve the most recent pending leave request, if any. If none pending, just say so.",
        "action_mode": True,
        "include_context": True,
    }
    r = requests.post(f"{API}/assistant/chat", headers=H(admin_token), json=payload, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "reply" in data and isinstance(data["reply"], str)
    assert "session_id" in data
    # plan may be None if no pending leaves; just assert structure when present
    if data.get("plan") is not None:
        plan = data["plan"]
        assert isinstance(plan, dict)
        assert isinstance(plan.get("steps"), list) and len(plan["steps"]) >= 1
        assert "title" in plan or "rationale" in plan or plan.get("steps")


def test_assistant_chat_action_mode_employee_plan_null(employee_token):
    """Employee with action_mode=true must NOT receive a plan (silently ignored)."""
    payload = {"message": "Approve all leave requests", "action_mode": True}
    r = requests.post(f"{API}/assistant/chat", headers=H(employee_token), json=payload, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("plan") is None


# ---------- Action plan execution ----------
def _create_pending_leave(admin_token):
    """Helper: pick first active employee, create a pending leave."""
    emps = requests.get(f"{API}/employees", headers=H(admin_token), timeout=30).json()
    eid = emps[0]["id"]
    today = date.today()
    payload = {
        "employee_id": eid,
        "leave_type": "annual",
        "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=12)).isoformat(),
        "reason": "TEST_iter4_action_mode",
    }
    r = requests.post(f"{API}/leave", headers=H(admin_token), json=payload, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["id"], eid


def test_execute_plan_admin_multi_step(admin_token):
    """Execute leave_decision + payroll_run + attendance_log + leave_create in one plan."""
    leave_id, eid = _create_pending_leave(admin_token)
    today = date.today()
    plan = {
        "title": "TEST_iter4 multi-step plan",
        "rationale": "automated test",
        "steps": [
            {"type": "leave_decision", "leave_id": leave_id, "decision": "approved"},
            {"type": "payroll_run", "year": today.year, "month": today.month},
            {"type": "attendance_log", "employee_id": eid, "date": today.isoformat(),
             "hours": 8, "overtime_hours": 1},
            {"type": "leave_create", "employee_id": eid, "leave_type": "sick",
             "start_date": (today + timedelta(days=20)).isoformat(),
             "end_date": (today + timedelta(days=21)).isoformat(), "days": 2},
        ],
    }
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["executed"] == 4, f"expected 4 ok steps, got {data}"
    statuses = [s["status"] for s in data["results"]]
    assert statuses == ["ok", "ok", "ok", "ok"], data

    # Verify leave decision persisted
    leaves = requests.get(f"{API}/leave", headers=H(admin_token), timeout=30).json()
    target = next((lv for lv in leaves if lv["id"] == leave_id), None)
    assert target is not None and target["status"] == "approved"

    # Verify audit logs include ai_* prefix
    audits = requests.get(f"{API}/audit", headers=H(admin_token), timeout=30).json()
    actions = {a["action"] for a in audits}
    assert "ai_leave_approved" in actions
    assert "ai_payroll_run" in actions
    assert "ai_attendance_log" in actions
    assert "ai_leave_create" in actions


def test_execute_plan_employee_forbidden(employee_token):
    plan = {"title": "x", "steps": [{"type": "leave_decision", "leave_id": "fake", "decision": "approved"}]}
    r = requests.post(f"{API}/assistant/action/execute", headers=H(employee_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 403


def test_execute_plan_empty_steps_422(admin_token):
    """Iter5: empty steps list now rejected upfront by Pydantic min_length=1."""
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": {"title": "empty", "steps": []}}, timeout=30)
    assert r.status_code == 422


def test_execute_plan_unknown_step_422(admin_token):
    """Iter5: discriminated union rejects unknown step types upfront with 422."""
    plan = {
        "title": "TEST_iter5 unknown step",
        "steps": [
            {"type": "unknown_xyz", "foo": "bar"},
            {"type": "fake_action"},
        ],
    }
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 422


def test_execute_plan_step_error_isolated(admin_token):
    """A failing runtime step (e.g., leave not found) should not abort the rest."""
    plan = {
        "title": "TEST_iter5 mixed",
        "steps": [
            {"type": "leave_decision", "leave_id": "non-existent-id-xyz", "decision": "approved"},
            {"type": "leave_decision", "leave_id": "another-fake-id", "decision": "rejected"},
        ],
    }
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["executed"] == 0
    assert data["results"][0]["status"] == "error"
    assert data["results"][1]["status"] == "error"


# ---------- Bank file CSV writer escaping ----------
def test_bank_file_csv_proper_escaping(admin_token):
    """Create employee with comma in name, run payroll, fetch CSV, parse — all rows must be parseable."""
    # Create employee with comma in last name
    emp_payload = {
        "first_name": "TEST_iter4",
        "last_name": "Doe, Jr.",  # contains comma
        "email": f"test_iter4_{uuid.uuid4().hex[:6]}@salonehcm.sl",
        "phone": "+232-77-000000",
        "national_id": f"NID{uuid.uuid4().hex[:8].upper()}",
        "department": "Engineering",
        "job_title": "Tester",
        "hire_date": date.today().isoformat(),
        "basic_salary_sle": 5000,
        "allowances_sle": 1000,
        "bank_name": "SLCB, Main Branch",  # comma in bank name too
        "bank_account": "1234567890",
    }
    r = requests.post(f"{API}/employees", headers=H(admin_token), json=emp_payload, timeout=30)
    assert r.status_code == 200, r.text
    new_emp_id = r.json()["id"]

    try:
        # Run payroll
        today = date.today()
        run_r = requests.post(f"{API}/payroll/run", headers=H(admin_token),
                              json={"period_year": today.year, "period_month": today.month}, timeout=30)
        assert run_r.status_code == 200
        rid = run_r.json()["id"]

        # Fetch bank-file CSV
        csv_r = requests.get(f"{API}/payroll/runs/{rid}/bank-file", headers=H(admin_token), timeout=30)
        assert csv_r.status_code == 200
        body = csv_r.text

        # Parse with csv module — should NOT raise and should preserve comma fields
        reader = csv.reader(io.StringIO(body))
        rows = list(reader)
        assert rows[0] == ["bank_name", "account_no", "beneficiary", "amount_sle", "reference"]
        # Find the row for our new employee
        target = next((row for row in rows[1:] if "TEST_iter4" in row[2]), None)
        assert target is not None, f"new employee row not found in {len(rows)} rows"
        assert target[0] == "SLCB, Main Branch", f"bank_name not preserved: {target[0]}"
        assert target[2] == "TEST_iter4 Doe, Jr.", f"beneficiary not preserved: {target[2]}"
        # All rows should have exactly 5 columns
        for row in rows[1:]:
            assert len(row) == 5, f"row not parseable as 5 columns: {row}"
    finally:
        # Cleanup: delete test employee
        requests.delete(f"{API}/employees/{new_emp_id}", headers=H(admin_token), timeout=30)


def test_bank_file_employee_forbidden(employee_token, admin_token):
    runs = requests.get(f"{API}/payroll/runs", headers=H(admin_token), timeout=30).json()
    if not runs:
        pytest.skip("no payroll runs")
    rid = runs[0]["id"]
    r = requests.get(f"{API}/payroll/runs/{rid}/bank-file", headers=H(employee_token), timeout=30)
    assert r.status_code == 403
