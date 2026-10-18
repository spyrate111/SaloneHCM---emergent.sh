"""iter47 — strict RBAC matrix: per-role allows & denials across the app.
Backend enforcement is the contract: 403 for unauthorized actions."""
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]

_tok_cache = {}


def _login(email, password):
    if email in _tok_cache:
        return _tok_cache[email]
    for _ in range(8):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
        if r.status_code != 429:
            break
        time.sleep(5)
    r.raise_for_status()
    _tok_cache[email] = r.json()
    return _tok_cache[email]


def _h(email, pw):
    return {"Authorization": f"Bearer {_login(email, pw)['token']}", "Content-Type": "application/json"}


EMP = ("employee1@salonehcm.com", "Test@Employee1")
MGR = ("manager1@salonehcm.com", "Test@Manager1")
AUD = ("auditor1@salonehcm.com", "Test@Auditor1")
PAY = ("payroll1@salonehcm.com", "Test@Payroll1")
HR = ("hradmin1@salonehcm.com", "Test@HRAdmin1")
ADM = ("admin1@salonehcm.com", "Test@Admin1")
SA = ("superadmin1@salonehcm.com", "Test@SuperAdmin1")


class TestEmployeeScope:
    def test_sees_only_own_employee_record(self):
        me = _login(*EMP)
        r = requests.get(f"{API}/employees", headers=_h(*EMP), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1 and rows[0]["id"] == me["employee_id"]

    def test_cannot_open_other_employee_record(self):
        me = _login(*EMP)
        other = _db.employees.find_one(
            {"company_id": me["company_id"], "id": {"$ne": me["employee_id"]}})
        r = requests.get(f"{API}/employees/{other['id']}", headers=_h(*EMP), timeout=15)
        assert r.status_code == 403

    def test_own_payslips_accessible(self):
        me = _login(*EMP)
        r = requests.get(f"{API}/payroll/my-payslips", headers=_h(*EMP), timeout=15)
        assert r.status_code == 200
        slips = r.json()
        assert len(slips) >= 1, "linked employee should have payslips"
        assert all(s["slip"]["employee_id"] == me["employee_id"] for s in slips)

    def test_cannot_fetch_other_payslip_pdf(self):
        me = _login(*EMP)
        other = _db.employees.find_one(
            {"company_id": me["company_id"], "id": {"$ne": me["employee_id"]}})
        run = _db.payroll_runs.find_one({"company_id": me["company_id"]})
        r = requests.get(f"{API}/payroll/runs/{run['id']}/payslip/{other['id']}.pdf",
                         headers=_h(*EMP), timeout=15)
        assert r.status_code == 403

    def test_blocked_from_privileged_reads(self):
        for path in ("/payroll/runs", "/audit", "/compliance/summary",
                     "/analytics/payroll-trend", "/analytics/top-earners",
                     "/users", "/dashboard/overview", "/mobile/punch/team",
                     "/payroll/verification-scans", "/compliance/filings"):
            r = requests.get(f"{API}{path}", headers=_h(*EMP), timeout=15)
            assert r.status_code == 403, f"{path} -> {r.status_code}"

    def test_own_time_entry_forced_to_self(self):
        me = _login(*EMP)
        other = _db.employees.find_one(
            {"company_id": me["company_id"], "id": {"$ne": me["employee_id"]}})
        r = requests.post(f"{API}/attendance", headers=_h(*EMP), timeout=15,
                          json={"employee_id": other["id"], "date": "2027-02-01",
                                "hours": 8, "overtime_hours": 0, "notes": "iter47"})
        assert r.status_code == 200
        row = r.json()
        assert row["employee_id"] == me["employee_id"], "entry must be forced to own id"
        _db.attendance.delete_many({"id": row["id"]})

    def test_leave_list_is_own_only(self):
        me = _login(*EMP)
        r = requests.get(f"{API}/leave", headers=_h(*EMP), timeout=15)
        assert r.status_code == 200
        assert all(lv["employee_id"] == me["employee_id"] for lv in r.json())


class TestAuditorReadOnly:
    def test_all_writes_blocked(self):
        h = _h(*AUD)
        checks = [
            ("post", "/attendance", {"date": "2027-02-01", "hours": 8}),
            ("post", "/leave", {"leave_type": "annual", "start_date": "2027-03-01",
                                "end_date": "2027-03-01", "reason": "x"}),
            ("post", "/mobile/punch", {"kind": "in"}),
            ("post", "/employees", {"first_name": "X", "last_name": "Y"}),
            ("put", "/leave/fake/decision", {"status": "approved"}),
            ("post", "/payroll/run", {"period": "2027-01"}),
            ("post", "/compliance/file-nra/fake", {}),
            ("patch", "/users/fake/role", {"role": "employee"}),
            ("delete", "/employees/fake", None),
            ("post", "/benefits/enrollments", {"plan_id": "x"}),
        ]
        for method, path, body in checks:
            r = getattr(requests, method)(f"{API}{path}", headers=h, json=body, timeout=15)
            assert r.status_code == 403, f"{method.upper()} {path} -> {r.status_code}"

    def test_own_account_writes_still_allowed(self):
        h = _h(*AUD)
        r = requests.post(f"{API}/users/me/role-tour-seen", headers=h, timeout=15)
        assert r.status_code == 200
        r2 = requests.post(f"{API}/auth/2fa/setup", headers=h, timeout=15)
        assert r2.status_code == 200
        _db.users.update_one({"email": AUD[0]}, {"$unset": {"totp_secret_pending": ""}})

    def test_reads_still_work(self):
        h = _h(*AUD)
        for path in ("/audit", "/compliance/summary", "/compliance/filings",
                     "/payroll/verification-scans", "/leave", "/attendance",
                     "/employees", "/mobile/punch/team"):
            r = requests.get(f"{API}{path}", headers=h, timeout=20)
            assert r.status_code == 200, f"{path} -> {r.status_code}"


class TestManagerScope:
    def test_employees_limited_to_self_and_reports(self):
        me = _login(*MGR)
        r = requests.get(f"{API}/employees", headers=_h(*MGR), timeout=15)
        assert r.status_code == 200
        for e in r.json():
            assert e["id"] == me["employee_id"] or e.get("manager_id") == me["employee_id"]

    def test_no_payroll_access(self):
        h = _h(*MGR)
        for method, path in (("get", "/payroll/runs"), ("post", "/payroll/preview"),
                             ("get", "/compliance/summary"), ("get", "/analytics/payroll-trend"),
                             ("get", "/payroll/sms/logs"), ("get", "/users")):
            r = getattr(requests, method)(f"{API}{path}", headers=h, timeout=15)
            assert r.status_code == 403, f"{path} -> {r.status_code}"

    def test_own_payslips_ok(self):
        r = requests.get(f"{API}/payroll/my-payslips", headers=_h(*MGR), timeout=15)
        assert r.status_code == 200 and len(r.json()) >= 1


class TestPayrollScope:
    def test_payroll_functions_allowed(self):
        h = _h(*PAY)
        assert requests.get(f"{API}/payroll/runs", headers=h, timeout=15).status_code == 200
        assert requests.post(f"{API}/payroll/preview", headers=h, timeout=30).status_code == 200
        assert requests.get(f"{API}/employees", headers=h, timeout=15).status_code == 200

    def test_no_hr_leave_admin_functions(self):
        h = _h(*PAY)
        cid = _login(*PAY)["company_id"]
        emp = _db.employees.find_one({"company_id": cid})
        lid = str(uuid.uuid4())
        _db.leave_requests.insert_one({
            "id": lid, "company_id": cid, "employee_id": emp["id"],
            "employee_name": "Iter47 Seed", "leave_type": "annual",
            "start_date": "2027-04-01", "end_date": "2027-04-01", "days": 1,
            "reason": "iter47", "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()})
        checks = [
            ("post", "/employees", {"first_name": "X", "last_name": "Y", "email": "x@y.com",
                                    "job_title": "x", "department": "x",
                                    "basic_salary_sle": 1, "hire_date": "2027-01-01"}),
            ("put", f"/employees/{emp['id']}", {"first_name": "X", "last_name": "Y",
                                                "email": "x@y.com", "job_title": "x",
                                                "department": "x", "basic_salary_sle": 1,
                                                "hire_date": "2027-01-01"}),
            ("delete", f"/employees/{emp['id']}", None),
            ("put", f"/leave/{lid}/decision", {"status": "approved"}),
            ("get", "/users", None),
        ]
        try:
            for method, path, body in checks:
                r = getattr(requests, method)(f"{API}{path}", headers=h, json=body, timeout=15)
                assert r.status_code == 403, f"{method} {path} -> {r.status_code}"
            assert _db.leave_requests.find_one({"id": lid})["status"] == "pending"
        finally:
            _db.leave_requests.delete_many({"id": lid})
        # leave list collapses to own records (none linked) — no tenant leak
        r = requests.get(f"{API}/leave", headers=h, timeout=15)
        assert r.status_code == 200 and r.json() == []


class TestHrScope:
    def test_hr_functions_allowed(self):
        h = _h(*HR)
        assert requests.get(f"{API}/employees", headers=h, timeout=15).status_code == 200
        assert requests.get(f"{API}/leave", headers=h, timeout=15).status_code == 200
        assert requests.get(f"{API}/attendance", headers=h, timeout=15).status_code == 200

    def test_no_payroll_processing(self):
        h = _h(*HR)
        for method, path in (("post", "/payroll/preview"), ("post", "/payroll/run"),
                             ("get", "/payroll/runs/fake/bank-file"), ("get", "/users")):
            r = getattr(requests, method)(f"{API}{path}", headers=h,
                                          json={"period": "2027-01"}, timeout=15)
            assert r.status_code == 403, f"{path} -> {r.status_code}"

    def test_can_manage_employees(self):
        h = _h(*HR)
        r = requests.post(f"{API}/employees", headers=h, timeout=15, json={
            "first_name": "Iter47", "last_name": "Temp", "email": "iter47@x.com",
            "job_title": "Clerk", "department": "Admin",
            "basic_salary_sle": 1000, "hire_date": "2027-01-01"})
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        try:
            assert requests.get(f"{API}/employees/{eid}", headers=h, timeout=15).status_code == 200
        finally:
            requests.delete(f"{API}/employees/{eid}", headers=h, timeout=15)
            _db.employees.delete_many({"id": eid})
            _db.audit_logs.delete_many({"resource": f"employees/{eid}"})


class TestAdminScope:
    def test_full_company_access(self):
        h = _h(*ADM)
        for path in ("/dashboard/overview", "/payroll/runs", "/employees",
                     "/leave", "/audit", "/users"):
            assert requests.get(f"{API}{path}", headers=h, timeout=15).status_code == 200, path

    def test_no_tenant_management(self):
        h = _h(*ADM)
        assert requests.get(f"{API}/admin/companies", headers=h, timeout=15).status_code == 403
        assert requests.post(f"{API}/users/test-accounts/seed", headers=h, timeout=15).status_code == 403


class TestSuperadminScope:
    def test_tenant_management(self):
        h = _h(*SA)
        assert requests.get(f"{API}/admin/companies", headers=h, timeout=15).status_code == 200
