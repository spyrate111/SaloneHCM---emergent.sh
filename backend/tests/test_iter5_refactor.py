"""SaloneHCM iteration 5 — Polish trio: shared run_payroll, max-50 cap, discriminated PlanStep + router refactor."""
import os
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://salonepaycms.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@salonehcm.sl", "password": "Admin@2026"}


def H(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---------- Refactor: all routers still mounted at /api/* ----------
ENDPOINTS = [
    ("GET", "/"),
    ("GET", "/auth/me"),
    ("GET", "/employees"),
    ("GET", "/payroll/runs"),
    ("GET", "/leave"),
    ("GET", "/attendance"),
    ("GET", "/dashboard/overview"),
    ("GET", "/audit"),
    ("GET", "/compliance/summary"),
]


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_router_mounted(admin_token, method, path):
    r = requests.request(method, f"{API}{path}", headers=H(admin_token), timeout=30)
    assert r.status_code in (200, 201), f"{path} → {r.status_code}: {r.text[:200]}"


# ---------- Pydantic discriminated union validation ----------
def test_plan_unknown_step_type_422(admin_token):
    plan = {"title": "x", "steps": [{"type": "totally_unknown", "foo": "bar"}]}
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 422, r.text


def test_plan_max_50_steps_cap_422(admin_token):
    """51 steps must be rejected by Pydantic max_length=50."""
    steps = [{"type": "leave_decision", "leave_id": f"id-{i}", "decision": "approved"} for i in range(51)]
    plan = {"title": "too-many", "steps": steps}
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 422, r.text


def test_plan_exactly_50_steps_accepted(admin_token):
    """Boundary: 50 steps must validate (steps fail at runtime since IDs don't exist, but no 422)."""
    steps = [{"type": "leave_decision", "leave_id": f"fake-{i}", "decision": "approved"} for i in range(50)]
    plan = {"title": "boundary-50", "steps": steps}
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    # All steps will error (leave not found) but the plan itself was accepted
    assert len(data["results"]) == 50


def test_plan_empty_steps_422(admin_token):
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": {"title": "x", "steps": []}}, timeout=30)
    assert r.status_code == 422


def test_plan_payroll_run_missing_fields_422(admin_token):
    """payroll_run step without year/month must fail validation."""
    plan = {"title": "x", "steps": [{"type": "payroll_run"}]}
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 422


def test_plan_leave_decision_missing_fields_422(admin_token):
    plan = {"title": "x", "steps": [{"type": "leave_decision"}]}
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 422


def test_plan_attendance_log_missing_fields_422(admin_token):
    plan = {"title": "x", "steps": [{"type": "attendance_log", "employee_id": "e1"}]}
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 422


def test_plan_payroll_run_invalid_month_422(admin_token):
    plan = {"title": "x", "steps": [{"type": "payroll_run", "year": 2026, "month": 13}]}
    r = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                      json={"plan": plan}, timeout=30)
    assert r.status_code == 422


# ---------- Shared run_payroll() helper: equivalence between both call sites ----------
def test_shared_run_payroll_equivalent_outputs(admin_token):
    """Doc structure produced by /payroll/run and AI plan payroll_run must match."""
    today = date.today()
    # Direct run
    r1 = requests.post(f"{API}/payroll/run", headers=H(admin_token),
                       json={"period_year": today.year, "period_month": today.month}, timeout=30)
    assert r1.status_code == 200, r1.text
    direct = r1.json()

    # AI plan run
    plan = {"title": "TEST_iter5 shared run", "steps": [
        {"type": "payroll_run", "year": today.year, "month": today.month}
    ]}
    r2 = requests.post(f"{API}/assistant/action/execute", headers=H(admin_token),
                       json={"plan": plan}, timeout=60)
    assert r2.status_code == 200, r2.text
    assert r2.json()["executed"] == 1

    # Fetch latest run via list (will be the AI one — sorted by created_at desc)
    runs = requests.get(f"{API}/payroll/runs", headers=H(admin_token), timeout=30).json()
    ai_run = runs[0]

    # Same structural keys
    for key in ("id", "period", "period_year", "period_month", "slips", "totals", "status", "created_at"):
        assert key in direct, f"direct run missing {key}"
        assert key in ai_run, f"AI run missing {key}"

    # Same period
    assert direct["period"] == ai_run["period"]

    # Same totals (active employees + same engine)
    for k in ("employee_count", "gross", "nassit_employee", "nassit_employer", "paye", "net"):
        assert direct["totals"][k] == ai_run["totals"][k], f"totals.{k} mismatch"


# ---------- Audit prefixes: payroll_run vs ai_payroll_run ----------
def test_audit_action_prefixes_distinguish_source(admin_token):
    audits = requests.get(f"{API}/audit", headers=H(admin_token), timeout=30).json()
    actions = {a["action"] for a in audits}
    assert "payroll_run" in actions, "direct payroll_run audit missing"
    assert "ai_payroll_run" in actions, "ai_payroll_run audit missing (different prefix)"


# ---------- Lifespan / startup: seed admin reachable ----------
def test_lifespan_seed_admin_login_works(admin_token):
    """If lifespan startup ran, admin token is present (fixture would have failed otherwise)."""
    assert isinstance(admin_token, str) and len(admin_token) > 10


def test_root_endpoint_alive():
    r = requests.get(f"{API}/", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data.get("app") == "SaloneHCM"
    assert data.get("status") == "ok"
