"""SaloneHCM iteration 2 tests: payslip PDF, bank-file CSV, audit log, my-payslips, bank fields backfill."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@salonehcm.sl", "password": "Admin@2026"}
EMPLOYEE = {"email": "aminata.kamara@salonehcm.sl", "password": "Employee@2026"}


def H(t):
    return {"Authorization": f"Bearer {t}"}


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


@pytest.fixture(scope="module")
def employee_user(employee_token):
    r = requests.get(f"{API}/auth/me", headers=H(employee_token), timeout=30)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def payroll_run(admin_token):
    """Ensure at least one payroll run exists; reuse latest."""
    runs = requests.get(f"{API}/payroll/runs", headers=H(admin_token), timeout=30).json()
    if runs:
        return runs[0]
    r = requests.post(f"{API}/payroll/run", json={"period_year": 2026, "period_month": 1},
                      headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    return r.json()


# -------- Bank fields backfill on startup --------
def test_employees_have_bank_fields(admin_token):
    emps = requests.get(f"{API}/employees", headers=H(admin_token), timeout=30).json()
    assert emps
    for e in emps:
        assert e.get("bank_name"), f"missing bank_name for {e['email']}"
        assert e.get("bank_account"), f"missing bank_account for {e['email']}"


# -------- Payslip PDF --------
def test_payslip_pdf_admin_returns_pdf(admin_token, payroll_run):
    eid = payroll_run["slips"][0]["employee_id"]
    rid = payroll_run["id"]
    r = requests.get(f"{API}/payroll/runs/{rid}/payslip/{eid}.pdf",
                     headers=H(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF", "Response is not a valid PDF binary"
    assert len(r.content) > 1000


def test_payslip_pdf_employee_own(employee_token, employee_user, payroll_run):
    rid = payroll_run["id"]
    eid = employee_user["employee_id"]
    r = requests.get(f"{API}/payroll/runs/{rid}/payslip/{eid}.pdf",
                     headers=H(employee_token), timeout=30)
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


def test_payslip_pdf_employee_forbidden_others(employee_token, employee_user, payroll_run):
    rid = payroll_run["id"]
    own = employee_user["employee_id"]
    other = next(s["employee_id"] for s in payroll_run["slips"] if s["employee_id"] != own)
    r = requests.get(f"{API}/payroll/runs/{rid}/payslip/{other}.pdf",
                     headers=H(employee_token), timeout=30)
    assert r.status_code == 403


def test_payslip_pdf_404(admin_token):
    r = requests.get(f"{API}/payroll/runs/nope/payslip/nope.pdf",
                     headers=H(admin_token), timeout=30)
    assert r.status_code == 404


# -------- Bank file CSV --------
def test_bank_file_admin(admin_token, payroll_run):
    rid = payroll_run["id"]
    r = requests.get(f"{API}/payroll/runs/{rid}/bank-file",
                     headers=H(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "")
    assert "text/csv" in ct
    text = r.text
    lines = text.strip().split("\n")
    assert lines[0] == "bank_name,account_no,beneficiary,amount_sle,reference"
    assert len(lines) >= 2
    # row should contain 5 comma-sep fields (beneficiary may be quoted)
    for ln in lines[1:]:
        assert ln.count(",") >= 4


def test_bank_file_employee_forbidden(employee_token, payroll_run):
    rid = payroll_run["id"]
    r = requests.get(f"{API}/payroll/runs/{rid}/bank-file",
                     headers=H(employee_token), timeout=30)
    assert r.status_code == 403


def test_bank_file_404(admin_token):
    r = requests.get(f"{API}/payroll/runs/nonexistent/bank-file",
                     headers=H(admin_token), timeout=30)
    assert r.status_code == 404


# -------- Audit log --------
def test_audit_admin_lists(admin_token):
    r = requests.get(f"{API}/audit", headers=H(admin_token), timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    if rows:
        first = rows[0]
        for k in ("action", "resource", "user_email", "ts"):
            assert k in first


def test_audit_employee_forbidden(employee_token):
    r = requests.get(f"{API}/audit", headers=H(employee_token), timeout=30)
    assert r.status_code == 403


def test_audit_auto_create_on_employee_mutation(admin_token):
    payload = {
        "first_name": "TEST", "last_name": f"Audit{uuid.uuid4().hex[:6]}",
        "email": f"audit_{uuid.uuid4().hex[:8]}@salonehcm.sl",
        "job_title": "QA", "department": "QA",
        "basic_salary_sle": 1000, "hire_date": "2025-01-01",
    }
    cr = requests.post(f"{API}/employees", json=payload, headers=H(admin_token), timeout=30)
    assert cr.status_code == 200
    eid = cr.json()["id"]

    rows = requests.get(f"{API}/audit", headers=H(admin_token), timeout=30).json()
    assert any(r["action"] == "create" and r["resource"] == f"employees/{eid}" for r in rows)

    requests.delete(f"{API}/employees/{eid}", headers=H(admin_token), timeout=30)
    rows2 = requests.get(f"{API}/audit", headers=H(admin_token), timeout=30).json()
    assert any(r["action"] == "delete" and r["resource"] == f"employees/{eid}" for r in rows2)


def test_audit_auto_create_on_bank_file_export(admin_token, payroll_run):
    rid = payroll_run["id"]
    requests.get(f"{API}/payroll/runs/{rid}/bank-file", headers=H(admin_token), timeout=30)
    rows = requests.get(f"{API}/audit", headers=H(admin_token), timeout=30).json()
    assert any(r["action"] == "export_bank_file" and r["resource"] == f"payroll_runs/{rid}" for r in rows)


# -------- My payslips (employee) --------
def test_my_payslips_employee(employee_token, payroll_run):
    r = requests.get(f"{API}/payroll/my-payslips", headers=H(employee_token), timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    row = rows[0]
    assert "run_id" in row and "period" in row and "slip" in row
    assert row["slip"]["net"] > 0
