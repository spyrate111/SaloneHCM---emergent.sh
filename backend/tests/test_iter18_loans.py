"""Loans & Salary Advances tests:
  - issue / patch / lifecycle
  - schedule projection
  - payroll deduction lifecycle (idempotent per period)
  - tier-gating
"""
import os
import requests
import pyotp
import pytest
from pymongo import MongoClient

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"
GOV_EMAIL = "admin@gov.sl"
GOV_PASS = "GovAdmin@2026"
SUPER_EMAIL = "admin@salonehcm.sl"
SUPER_PASS = "Admin@2026"
SUPER_SECRET = os.environ.get("SUPERADMIN_TOTP_SECRET", "KRSXG5BANFXSAYTBORQXG43LMR2A")


@pytest.fixture
def gov_h():
    tok = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def _mongo():
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "salonehcm_db")]


@pytest.fixture(autouse=True)
def _wipe_loans_and_periods():
    """Each test starts from a clean slate."""
    db = _mongo()
    db.loans.delete_many({"purpose": {"$regex": "TEST"}})
    db.payroll_runs.delete_many({"period": {"$in": ["2099-01", "2099-02", "2099-03"]}})
    yield
    db.loans.delete_many({"purpose": {"$regex": "TEST"}})
    db.payroll_runs.delete_many({"period": {"$in": ["2099-01", "2099-02", "2099-03"]}})


def _issue(gov_h, employee_id, principal=1500, term=3, purpose="TEST-loan"):
    return requests.post(f"{API}/loans", headers=gov_h, json={
        "employee_id": employee_id, "principal_sle": principal,
        "term_months": term, "purpose": purpose,
    })


def test_issue_loan_auto_computes_monthly(gov_h):
    emp = requests.get(f"{API}/employees", headers=gov_h).json()[0]
    r = _issue(gov_h, emp["id"], principal=1200, term=4)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["monthly_deduction_sle"] == 300.0
    assert body["remaining_balance_sle"] == 1200.0
    assert body["status"] == "active"
    assert body["repayment_count"] == 0


def test_cannot_double_issue_active_loan(gov_h):
    emp = requests.get(f"{API}/employees", headers=gov_h).json()[0]
    r1 = _issue(gov_h, emp["id"])
    assert r1.status_code == 201
    r2 = _issue(gov_h, emp["id"], purpose="TEST-second")
    assert r2.status_code == 409
    assert "active loan" in r2.text.lower()


def test_monthly_deduction_above_50pct_of_salary_blocked(gov_h):
    emp = next(e for e in requests.get(f"{API}/employees", headers=gov_h).json()
               if (e.get("basic_salary_sle") or 0) > 0)
    basic = emp["basic_salary_sle"]
    # 80% of basic should fail
    r = requests.post(f"{API}/loans", headers=gov_h, json={
        "employee_id": emp["id"], "principal_sle": basic * 4,
        "term_months": 4, "monthly_deduction_sle": basic * 0.8, "purpose": "TEST-toomuch",
    })
    assert r.status_code == 409


def test_schedule_projects_to_zero(gov_h):
    emp = requests.get(f"{API}/employees", headers=gov_h).json()[0]
    r = _issue(gov_h, emp["id"], principal=900, term=3)
    lid = r.json()["id"]
    sched = requests.get(f"{API}/loans/{lid}/schedule", headers=gov_h).json()
    assert sched["projected_periods"] == 3
    assert sched["schedule"][-1]["remaining_after"] == 0


def test_payroll_run_deducts_loan_idempotently(gov_h):
    emp = requests.get(f"{API}/employees", headers=gov_h).json()[0]
    r = _issue(gov_h, emp["id"], principal=900, term=3)
    lid = r.json()["id"]

    # 1st run on the test period
    rp = requests.post(f"{API}/payroll/run", headers=gov_h, json={"period_year": 2099, "period_month": 1})
    assert rp.status_code == 200, rp.text
    run = rp.json()
    slip = next(s for s in run["slips"] if s["employee_id"] == emp["id"])
    assert slip["loan_deduction"] == 300.0
    assert run["totals"]["loan_deductions"] >= 300.0

    loan = requests.get(f"{API}/loans/{lid}", headers=gov_h).json()
    assert loan["remaining_balance_sle"] == 600.0
    assert loan["repayment_count"] == 1

    # 2nd run SAME period — should NOT double-deduct
    rp2 = requests.post(f"{API}/payroll/run", headers=gov_h, json={"period_year": 2099, "period_month": 1})
    assert rp2.status_code == 200
    loan2 = requests.get(f"{API}/loans/{lid}", headers=gov_h).json()
    assert loan2["remaining_balance_sle"] == 600.0, "idempotency violated"
    assert loan2["repayment_count"] == 1

    # 3rd run for next period — should deduct another 300
    rp3 = requests.post(f"{API}/payroll/run", headers=gov_h, json={"period_year": 2099, "period_month": 2})
    assert rp3.status_code == 200
    loan3 = requests.get(f"{API}/loans/{lid}", headers=gov_h).json()
    assert loan3["remaining_balance_sle"] == 300.0
    assert loan3["repayment_count"] == 2

    # Final run pays it off
    rp4 = requests.post(f"{API}/payroll/run", headers=gov_h, json={"period_year": 2099, "period_month": 3})
    assert rp4.status_code == 200
    loan4 = requests.get(f"{API}/loans/{lid}", headers=gov_h).json()
    assert loan4["remaining_balance_sle"] == 0
    assert loan4["status"] == "paid"
    assert loan4["repayment_count"] == 3


def test_employee_can_view_only_own_loans(gov_h):
    emp = requests.get(f"{API}/employees", headers=gov_h).json()[0]
    _issue(gov_h, emp["id"])
    # Login as the employee
    user_email = emp["email"]
    # Look up the user account password for this employee (Gov tenant uses Employee@2026)
    r = requests.post(f"{API}/auth/login", json={"email": user_email, "password": "Employee@2026"})
    if r.status_code != 200:
        pytest.skip(f"No login account for {user_email} — skipping ESS scope test")
    emp_token = r.json()["token"]
    emp_h = {"Authorization": f"Bearer {emp_token}"}
    loans = requests.get(f"{API}/loans", headers=emp_h).json()
    # Should see only their own
    assert all(loan["employee_id"] == emp["id"] for loan in loans)


def test_patch_cancel_then_reissue(gov_h):
    emp = requests.get(f"{API}/employees", headers=gov_h).json()[0]
    r = _issue(gov_h, emp["id"])
    lid = r.json()["id"]
    p = requests.patch(f"{API}/loans/{lid}", headers=gov_h, json={"status": "cancelled"})
    assert p.status_code == 200
    # Now reissue allowed since previous is cancelled
    r2 = _issue(gov_h, emp["id"], purpose="TEST-reissue")
    assert r2.status_code == 201


def test_lite_tier_blocked_by_402():
    super_tok = requests.post(f"{API}/auth/login", json={
        "email": SUPER_EMAIL, "password": SUPER_PASS,
        "totp_code": pyotp.TOTP(SUPER_SECRET).now(),
    }).json()["token"]
    h_super = {"Authorization": f"Bearer {super_tok}"}
    payload = {
        "name": f"LOAN_TEST_LITE_{os.urandom(2).hex()}",
        "tier": "lite", "admin_name": "Loan Lite",
        "admin_email": f"loan_lite_{os.urandom(2).hex()}@nope.sl",
        "admin_password": "TestLite@2026",
    }
    r = requests.post(f"{API}/admin/companies", headers=h_super, json=payload)
    assert r.status_code == 200, r.text
    cid = r.json()["company"]["id"]
    try:
        lt = requests.post(f"{API}/auth/login",
                           json={"email": payload["admin_email"], "password": payload["admin_password"]}).json()["token"]
        r = requests.get(f"{API}/loans", headers={"Authorization": f"Bearer {lt}"})
        assert r.status_code == 402
    finally:
        requests.delete(f"{API}/admin/companies/{cid}", headers=h_super)
