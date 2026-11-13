# Iter52: API checks for announcement read receipts, exit interview validation/roles, application emails
import os, time, uuid, io
import pytest, requests
from pymongo import MongoClient

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
MONGO = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "salonehcm_db")]


def login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module")
def hr():
    return login("hradmin1@salonehcm.com", "Test@HRAdmin1")


@pytest.fixture(scope="module")
def emp():
    return login("employee1@salonehcm.com", "Test@Employee1")


@pytest.fixture(scope="module")
def payroll():
    return login("payroll1@salonehcm.com", "Test@Payroll1")


# Read receipts: employee sees no read_count; unread endpoint 403; mark-seen increments
def test_read_receipts_roles(hr, emp):
    r = hr.post(f"{BASE_URL}/api/announcements", json={"title": "TEST_api_rr", "body": "b", "priority": "urgent"})
    assert r.status_code == 200
    aid = r.json()["id"]
    try:
        rows = emp.get(f"{BASE_URL}/api/announcements").json()
        mine = [a for a in rows if a["id"] == aid]
        assert mine and "read_count" not in mine[0] and "total_staff" not in mine[0]
        assert emp.get(f"{BASE_URL}/api/announcements/{aid}/unread").status_code == 403
        emp_id = emp.get(f"{BASE_URL}/api/auth/me").json().get("id")
        unread = hr.get(f"{BASE_URL}/api/announcements/{aid}/unread").json()
        assert any(u["id"] == emp_id for u in unread)
        m = emp.post(f"{BASE_URL}/api/announcements/mark-seen", json={"ids": [aid, aid, "bogus"]})
        assert m.status_code == 200 and m.json()["marked"] == 1
        emp.post(f"{BASE_URL}/api/announcements/mark-seen", json={"ids": [aid]})  # idempotent
        hrrow = [a for a in hr.get(f"{BASE_URL}/api/announcements").json() if a["id"] == aid][0]
        assert hrrow["read_count"] == 1 and hrrow["total_staff"] > 1
        unread2 = hr.get(f"{BASE_URL}/api/announcements/{aid}/unread").json()
        assert not any(u["id"] == emp_id for u in unread2)
    finally:
        hr.delete(f"{BASE_URL}/api/announcements/{aid}")
    assert MONGO.announcement_reads.count_documents({"announcement_id": aid}) == 0


# Exit interview: bad reason 422, payroll 403, valid save persists
def test_exit_interview_validation_roles(hr, payroll):
    suffix = uuid.uuid4().hex[:6]
    r = hr.post(f"{BASE_URL}/api/employees", json={
        "first_name": "TEST_Exit", "last_name": f"Api{suffix}", "email": f"test_exit_{suffix}@example.com",
        "job_title": "Tester", "department": "QA", "basic_salary_sle": 1000, "hire_date": "2024-01-01"})
    assert r.status_code in (200, 201), r.text
    eid = r.json()["id"]
    try:
        s = hr.post(f"{BASE_URL}/api/offboarding/{eid}/start")
        assert s.status_code == 200, s.text
        oid = s.json().get("id") or hr.get(f"{BASE_URL}/api/offboarding/employee/{eid}").json()["id"]
        bad = hr.put(f"{BASE_URL}/api/offboarding/{oid}/exit-interview", json={"leaving_reason": "bored", "notes": "x"})
        assert bad.status_code == 422
        p = payroll.put(f"{BASE_URL}/api/offboarding/{oid}/exit-interview", json={"leaving_reason": "other", "notes": "x"})
        assert p.status_code == 403
        ok = hr.put(f"{BASE_URL}/api/offboarding/{oid}/exit-interview", json={"leaving_reason": "retirement", "notes": "TEST notes"})
        assert ok.status_code == 200
        got = payroll.get(f"{BASE_URL}/api/offboarding/employee/{eid}").json()
        assert got["exit_interview"]["leaving_reason"] == "retirement"
        assert got["exit_interview"]["notes"] == "TEST notes"
        assert MONGO.audit_logs.find_one({"action": "exit_interview_recorded", "resource": f"offboardings/{oid}"}) is not None
        hr.delete(f"{BASE_URL}/api/offboarding/{oid}")
    finally:
        hr.delete(f"{BASE_URL}/api/employees/{eid}")
        MONGO.offboardings.delete_many({"employee_id": eid})
        MONGO.employees.delete_one({"id": eid})
