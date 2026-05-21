"""SaloneHCM backend API tests."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://salonepaycms.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@salonehcm.sl", "password": "Admin@2026"}
EMPLOYEE = {"email": "aminata.kamara@salonehcm.sl", "password": "Employee@2026"}


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


def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Auth ----------
def test_login_admin_returns_token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200
    d = r.json()
    # admin@salonehcm.sl was promoted to superadmin in iter9 — keep this test
    # accepting both legacy and current roles so it survives future re-seeds.
    assert d["role"] in ("admin", "superadmin")
    assert isinstance(d["token"], str) and len(d["token"]) > 10


def test_login_invalid_creds():
    r = requests.post(f"{API}/auth/login", json={"email": "x@y.z", "password": "bad"}, timeout=30)
    assert r.status_code == 401


def test_auth_me(admin_token):
    r = requests.get(f"{API}/auth/me", headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN["email"]


# ---------- Employees ----------
def test_list_employees_seeded(admin_token):
    r = requests.get(f"{API}/employees", headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 10


def test_create_and_get_employee(admin_token):
    payload = {
        "first_name": "TEST",
        "last_name": f"User{uuid.uuid4().hex[:6]}",
        "email": f"test_{uuid.uuid4().hex[:8]}@salonehcm.sl",
        "job_title": "Tester",
        "department": "QA",
        "basic_salary_sle": 3000,
        "allowances_sle": 500,
        "hire_date": "2025-01-01",
    }
    r = requests.post(f"{API}/employees", json=payload, headers=H(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    eid = r.json()["id"]

    g = requests.get(f"{API}/employees/{eid}", headers=H(admin_token), timeout=30)
    assert g.status_code == 200
    assert g.json()["email"] == payload["email"]

    # cleanup
    requests.delete(f"{API}/employees/{eid}", headers=H(admin_token), timeout=30)


def test_employee_cannot_create(employee_token):
    payload = {
        "first_name": "Bad", "last_name": "Actor",
        "email": f"bad_{uuid.uuid4().hex[:6]}@x.sl",
        "job_title": "X", "department": "X",
        "basic_salary_sle": 1000, "hire_date": "2025-01-01",
    }
    r = requests.post(f"{API}/employees", json=payload, headers=H(employee_token), timeout=30)
    assert r.status_code == 403


# ---------- Payroll ----------
def test_payroll_preview(admin_token):
    r = requests.post(f"{API}/payroll/preview", headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    t = r.json()["totals"]
    assert t["employee_count"] >= 10
    assert t["paye"] > 0
    assert t["nassit_employee"] > 0
    assert t["gross"] > 0


def test_payroll_run_and_list(admin_token):
    r = requests.post(f"{API}/payroll/run", json={"period_year": 2026, "period_month": 1},
                     headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    rid = r.json()["id"]
    g = requests.get(f"{API}/payroll/runs/{rid}", headers=H(admin_token), timeout=30)
    assert g.status_code == 200
    lst = requests.get(f"{API}/payroll/runs", headers=H(admin_token), timeout=30)
    assert lst.status_code == 200 and len(lst.json()) >= 1
    pytest.run_id = rid  # share


def test_my_payslip_employee(employee_token):
    r = requests.get(f"{API}/payroll/my-payslip", headers=H(employee_token), timeout=30)
    assert r.status_code == 200
    assert r.json()["slip"] is not None


# ---------- Compliance ----------
def test_compliance_summary(admin_token):
    r = requests.get(f"{API}/compliance/summary", headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "ytd_paye_sle" in d and "ytd_nassit_sle" in d
    assert "paye_bands" in d["regs"]


def test_nra_export(admin_token):
    runs = requests.get(f"{API}/payroll/runs", headers=H(admin_token), timeout=30).json()
    assert runs
    rid = runs[0]["id"]
    r = requests.get(f"{API}/compliance/nra-export/{rid}", headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    assert "rows" in r.json() and len(r.json()["rows"]) > 0


# ---------- Leave ----------
def test_leave_create_and_decision(admin_token):
    emps = requests.get(f"{API}/employees", headers=H(admin_token), timeout=30).json()
    eid = emps[0]["id"]
    payload = {"employee_id": eid, "leave_type": "annual",
               "start_date": "2026-02-01", "end_date": "2026-02-03", "reason": "test"}
    r = requests.post(f"{API}/leave", json=payload, headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    lid = r.json()["id"]
    d = requests.put(f"{API}/leave/{lid}/decision", json={"status": "approved"},
                    headers=H(admin_token), timeout=30)
    assert d.status_code == 200 and d.json()["status"] == "approved"


def test_leave_employee_only_own(employee_token):
    r = requests.get(f"{API}/leave", headers=H(employee_token), timeout=30)
    assert r.status_code == 200


# ---------- Attendance ----------
def test_attendance_create_list(admin_token):
    emps = requests.get(f"{API}/employees", headers=H(admin_token), timeout=30).json()
    eid = emps[0]["id"]
    r = requests.post(f"{API}/attendance",
                     json={"employee_id": eid, "date": "2026-01-15", "hours": 8, "overtime_hours": 1},
                     headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    lst = requests.get(f"{API}/attendance", headers=H(admin_token), timeout=30)
    assert lst.status_code == 200 and len(lst.json()) >= 1


# ---------- Dashboard ----------
def test_dashboard_overview(admin_token):
    r = requests.get(f"{API}/dashboard/overview", headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ("headcount", "monthly_payroll_sle", "departments", "runs_history"):
        assert k in d
    assert d["headcount"] >= 10


# ---------- AI Assistant ----------
def test_assistant_chat(admin_token):
    r = requests.post(f"{API}/assistant/chat",
                     json={"message": "What is NASSIT employee rate? Reply briefly."},
                     headers=H(admin_token), timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "reply" in d and len(d["reply"]) > 0
    sid = d["session_id"]
    h = requests.get(f"{API}/assistant/history/{sid}", headers=H(admin_token), timeout=30)
    assert h.status_code == 200 and len(h.json()) >= 2
