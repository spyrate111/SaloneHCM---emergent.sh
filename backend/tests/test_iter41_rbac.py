"""iter41 — RBAC matrix: hr / payroll / manager / employee role enforcement."""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
_db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

PW = "Rbac@Test2026"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.text}"
    return r.json()


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def rbac_users(admin):
    """Create one temp user per new role via the invite API; clean up after."""
    created = {}
    # manager must be linked to an employee that HAS direct reports
    boss = _db.employees.find_one({"company_id": admin["company_id"],
                                   "manager_id": {"$nin": [None, ""]}})
    mgr_emp = _db.employees.find_one({"id": boss["manager_id"]}) if boss else None
    assert mgr_emp, "gov tenant needs an employee with a manager for this test"
    for role in ("hr", "payroll", "manager"):
        email = f"rbac.{role}@gov.sl"
        _db.users.delete_many({"email": email})
        payload = {"email": email, "name": f"RBAC {role.title()}",
                   "role": role, "password": PW}
        if role == "manager":
            payload["employee_id"] = mgr_emp["id"]
        r = requests.post(f"{API}/users/invite", json=payload,
                          headers=_h(admin["token"]), timeout=15)
        assert r.status_code == 200, f"invite {role}: {r.text}"
        created[role] = _login(email, PW)
    created["manager_emp"] = mgr_emp
    yield created
    _db.users.delete_many({"email": {"$regex": "^rbac\\."}})


def _seed_leave(company_id, emp, day_offset=170):
    from datetime import timedelta
    day = (datetime.now(timezone.utc) + timedelta(days=day_offset)).strftime("%Y-%m-%d")
    doc = {"id": str(uuid.uuid4()), "company_id": company_id, "employee_id": emp["id"],
           "employee_name": f'{emp["first_name"]} {emp["last_name"]}',
           "leave_type": "annual", "start_date": day, "end_date": day, "days": 1,
           "reason": "iter41 rbac seed", "status": "pending",
           "created_at": datetime.now(timezone.utc).isoformat()}
    _db.leave_requests.insert_one(doc)
    return doc


class TestHrRole:
    def test_hr_can_manage_employees(self, rbac_users):
        hr = rbac_users["hr"]
        r = requests.post(f"{API}/employees", headers=_h(hr["token"]), json={
            "first_name": "Rbac", "last_name": "Temp", "email": "rbac.temp@gov.sl",
            "job_title": "Clerk", "department": "Admin", "basic_salary_sle": 4000,
            "hire_date": "2026-01-15"},
            timeout=15)
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        d = requests.delete(f"{API}/employees/{eid}", headers=_h(hr["token"]), timeout=15)
        assert d.status_code == 200

    def test_hr_can_decide_leave(self, rbac_users, admin):
        hr = rbac_users["hr"]
        emp = _db.employees.find_one({"company_id": admin["company_id"], "status": "active"})
        lv = _seed_leave(admin["company_id"], emp)
        try:
            r = requests.put(f"{API}/leave/{lv['id']}/decision",
                             json={"status": "approved"},
                             headers=_h(hr["token"]), timeout=15)
            assert r.status_code == 200, r.text
        finally:
            _db.leave_requests.delete_many({"id": lv["id"]})

    def test_hr_can_view_training_stats(self, rbac_users):
        r = requests.get(f"{API}/training-progress/reminders/stats",
                         headers=_h(rbac_users["hr"]["token"]), timeout=15)
        assert r.status_code == 200

    def test_hr_blocked_from_payroll_and_users(self, rbac_users):
        hr = rbac_users["hr"]
        assert requests.post(f"{API}/payroll/preview", json={},
                             headers=_h(hr["token"]), timeout=15).status_code == 403
        assert requests.get(f"{API}/payroll/schedules", headers=_h(hr["token"]), timeout=15).status_code == 403
        assert requests.get(f"{API}/users", headers=_h(hr["token"]), timeout=15).status_code == 403


class TestPayrollRole:
    def test_payroll_can_view_runs_and_schedules(self, rbac_users):
        p = rbac_users["payroll"]
        assert requests.get(f"{API}/payroll/runs", headers=_h(p["token"]), timeout=15).status_code == 200
        assert requests.get(f"{API}/payroll/schedules", headers=_h(p["token"]), timeout=15).status_code == 200

    def test_payroll_read_only_employees(self, rbac_users):
        p = rbac_users["payroll"]
        assert requests.get(f"{API}/employees", headers=_h(p["token"]), timeout=15).status_code == 200
        r = requests.post(f"{API}/employees", headers=_h(p["token"]), json={
            "first_name": "No", "last_name": "Way", "email": "rbac.noway@gov.sl",
            "job_title": "X", "department": "X", "basic_salary_sle": 1000}, timeout=15)
        assert r.status_code == 403

    def test_payroll_blocked_from_hr_and_users(self, rbac_users):
        p = rbac_users["payroll"]
        assert requests.get(f"{API}/training-progress/reminders/stats",
                            headers=_h(p["token"]), timeout=15).status_code == 403
        assert requests.get(f"{API}/users", headers=_h(p["token"]), timeout=15).status_code == 403


class TestManagerRole:
    def test_manager_can_decide_direct_reports_leave(self, rbac_users, admin):
        m = rbac_users["manager"]
        report = _db.employees.find_one({"company_id": admin["company_id"],
                                         "manager_id": rbac_users["manager_emp"]["id"]})
        assert report
        lv = _seed_leave(admin["company_id"], report, 171)
        try:
            r = requests.put(f"{API}/leave/{lv['id']}/decision",
                             json={"status": "approved"},
                             headers=_h(m["token"]), timeout=15)
            assert r.status_code == 200, r.text
        finally:
            _db.leave_requests.delete_many({"id": lv["id"]})

    def test_manager_cannot_decide_non_report(self, rbac_users, admin):
        m = rbac_users["manager"]
        stranger = _db.employees.find_one({
            "company_id": admin["company_id"], "status": "active",
            "manager_id": {"$ne": rbac_users["manager_emp"]["id"]},
            "id": {"$ne": rbac_users["manager_emp"]["id"]}})
        lv = _seed_leave(admin["company_id"], stranger, 172)
        try:
            r = requests.put(f"{API}/leave/{lv['id']}/decision",
                             json={"status": "approved"},
                             headers=_h(m["token"]), timeout=15)
            assert r.status_code == 403
        finally:
            _db.leave_requests.delete_many({"id": lv["id"]})

    def test_manager_blocked_from_admin_areas(self, rbac_users):
        m = rbac_users["manager"]
        assert requests.get(f"{API}/payroll/runs", headers=_h(m["token"]), timeout=15).status_code == 403
        assert requests.get(f"{API}/users", headers=_h(m["token"]), timeout=15).status_code == 403
        r = requests.post(f"{API}/employees", headers=_h(m["token"]), json={
            "first_name": "No", "last_name": "Way", "email": "rbac.no2@gov.sl",
            "job_title": "X", "department": "X", "basic_salary_sle": 1000}, timeout=15)
        assert r.status_code == 403


class TestEmployeeRoleUnchanged:
    def test_employee_still_blocked_everywhere(self):
        sia = _login("sia.kallon@gov.sl", "Employee@2026")
        for path in ("/payroll/runs", "/payroll/schedules", "/users",
                     "/training-progress/reminders/stats"):
            assert requests.get(f"{API}{path}", headers=_h(sia["token"]),
                                timeout=15).status_code == 403, path


class TestRoleChange:
    def test_admin_changes_role_and_it_takes_effect(self, rbac_users, admin):
        target = _db.users.find_one({"email": "rbac.manager@gov.sl"})
        r = requests.patch(f"{API}/users/{target['id']}/role", json={"role": "hr"},
                           headers=_h(admin["token"]), timeout=15)
        assert r.status_code == 200 and r.json()["role"] == "hr"
        # takes effect immediately (role read from DB, not the JWT)
        m = rbac_users["manager"]
        assert requests.get(f"{API}/training-progress/reminders/stats",
                            headers=_h(m["token"]), timeout=15).status_code == 200
        # revert
        requests.patch(f"{API}/users/{target['id']}/role", json={"role": "manager"},
                       headers=_h(admin["token"]), timeout=15)
        log = _db.audit_logs.find_one({"action": "user_role_changed",
                                       "resource": f"users/{target['id']}"})
        assert log and log["meta"]["to"] in ("hr", "manager")
        _db.audit_logs.delete_many({"resource": f"users/{target['id']}"})

    def test_cannot_change_own_role_or_invalid(self, admin):
        me = _db.users.find_one({"email": "admin@gov.sl"})
        r = requests.patch(f"{API}/users/{me['id']}/role", json={"role": "employee"},
                           headers=_h(admin["token"]), timeout=15)
        assert r.status_code == 400
        other = _db.users.find_one({"email": "rbac.hr@gov.sl"})
        bad = requests.patch(f"{API}/users/{other['id']}/role", json={"role": "wizard"},
                             headers=_h(admin["token"]), timeout=15)
        assert bad.status_code == 422

    def test_non_admin_cannot_change_roles(self, rbac_users):
        hr = rbac_users["hr"]
        target = _db.users.find_one({"email": "rbac.payroll@gov.sl"})
        r = requests.patch(f"{API}/users/{target['id']}/role", json={"role": "admin"},
                           headers=_h(hr["token"]), timeout=15)
        assert r.status_code == 403
