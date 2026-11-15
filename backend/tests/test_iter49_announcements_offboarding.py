"""iter49 — Announcements/Notice Board + Offboarding workflow."""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]
_tok = {}

HR = ("hradmin1@salonehcm.com", "Test@HRAdmin1")
PAY = ("payroll1@salonehcm.com", "Test@Payroll1")
ADM = ("admin1@salonehcm.com", "Test@Admin1")
EMP = ("employee1@salonehcm.com", "Test@Employee1")
AUD = ("auditor1@salonehcm.com", "Test@Auditor1")


def _login(email, password):
    if email in _tok:
        return _tok[email]
    for _ in range(8):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
        if r.status_code != 429:
            break
        time.sleep(5)
    r.raise_for_status()
    _tok[email] = r.json()
    return _tok[email]


def _h(email, pw):
    return {"Authorization": f"Bearer {_login(email, pw)['token']}"}


class TestAnnouncements:
    def test_post_visibility_and_roles(self):
        r = requests.post(f"{API}/announcements", headers=_h(*HR), timeout=15,
                          json={"title": "Office closed Friday", "body": "Public holiday.", "priority": "normal"})
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        try:
            rows = requests.get(f"{API}/announcements", headers=_h(*EMP), timeout=15).json()
            assert any(a["id"] == aid for a in rows)
            # employees may not post
            r2 = requests.post(f"{API}/announcements", headers=_h(*EMP), timeout=15,
                               json={"title": "x", "body": "y"})
            assert r2.status_code == 403
            # employees may not delete
            assert requests.delete(f"{API}/announcements/{aid}", headers=_h(*EMP), timeout=15).status_code == 403
            # HR delete works
            assert requests.delete(f"{API}/announcements/{aid}", headers=_h(*HR), timeout=15).status_code == 200
        finally:
            _db.announcements.delete_many({"id": aid})

    def test_validation(self):
        h = _h(*HR)
        assert requests.post(f"{API}/announcements", headers=h, timeout=15,
                             json={"title": " ", "body": "x"}).status_code == 422
        assert requests.post(f"{API}/announcements", headers=h, timeout=15,
                             json={"title": "x", "body": "y", "priority": "loud"}).status_code == 422
        assert requests.post(f"{API}/announcements", headers=h, timeout=15,
                             json={"title": "x", "body": "y", "expires_at": "2020-01-01"}).status_code == 422

    def test_expired_hidden_from_staff_but_archived_for_admins(self):
        company_id = _login(*HR)["company_id"]
        aid = str(uuid.uuid4())
        yday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        _db.announcements.insert_one({
            "id": aid, "company_id": company_id, "title": "Old notice", "body": "stale",
            "priority": "normal", "expires_at": yday, "posted_by": "Test",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            emp_rows = requests.get(f"{API}/announcements", headers=_h(*EMP),
                                    params={"include_expired": "true"}, timeout=15).json()
            assert not any(a["id"] == aid for a in emp_rows)  # staff never see expired
            hr_rows = requests.get(f"{API}/announcements", headers=_h(*HR),
                                   params={"include_expired": "true"}, timeout=15).json()
            match = [a for a in hr_rows if a["id"] == aid]
            assert match and match[0]["expired"] is True
            # default HR view also hides expired
            hr_active = requests.get(f"{API}/announcements", headers=_h(*HR), timeout=15).json()
            assert not any(a["id"] == aid for a in hr_active)
        finally:
            _db.announcements.delete_many({"id": aid})

    def test_urgent_post_and_audit(self):
        r = requests.post(f"{API}/announcements", headers=_h(*ADM), timeout=15,
                          json={"title": "Generator down", "body": "HQ power off 2pm", "priority": "urgent"})
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        try:
            assert r.json()["priority"] == "urgent"
            log = _db.audit_logs.find_one({"action": "announcement_posted", "resource": f"announcements/{aid}"})
            assert log is not None
        finally:
            _db.announcements.delete_many({"id": aid})


def _mk_temp_employee_and_user(company_id):
    eid = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    email = f"offboard.test.{uid[:8]}@salonehcm.com"
    _db.employees.insert_one({
        "id": eid, "company_id": company_id, "first_name": "Exit", "last_name": "Tester",
        "email": email, "department": "Operations", "job_title": "Clerk",
        "employment_type": "full_time", "basic_salary_sle": 2000, "allowances_sle": 0,
        "status": "active", "hire_date": "2024-01-01",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    ref = _db.users.find_one({"email": EMP[0]}, {"password_hash": 1})
    _db.users.insert_one({
        "id": uid, "company_id": company_id, "email": email, "name": "Exit Tester",
        "role": "employee", "employee_id": eid, "password_hash": ref["password_hash"],
        "is_test_account": True, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return eid, uid, email


def _cleanup_temp(eid, uid):
    _db.employees.delete_many({"id": eid})
    _db.users.delete_many({"id": uid})
    _db.offboardings.delete_many({"employee_id": eid})


class TestOffboarding:
    def test_full_workflow_role_gates_and_deactivation(self):
        company_id = _login(*HR)["company_id"]
        eid, uid, email = _mk_temp_employee_and_user(company_id)
        try:
            # temp account logs in fine before offboarding completes
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": EMP[1]}, timeout=15)
            assert r.status_code == 200, r.text

            # employee cannot start offboarding
            assert requests.post(f"{API}/offboarding/{eid}/start", headers=_h(*EMP), timeout=15).status_code == 403
            # HR starts it
            r = requests.post(f"{API}/offboarding/{eid}/start", headers=_h(*HR), timeout=15)
            assert r.status_code == 200, r.text
            ob = r.json()
            oid = ob["id"]
            assert len(ob["items"]) == 4 and ob["status"] == "in_progress"
            assert _db.employees.find_one({"id": eid})["status"] == "exiting"
            # duplicate start blocked
            assert requests.post(f"{API}/offboarding/{eid}/start", headers=_h(*HR), timeout=15).status_code == 409

            # role gates: payroll can't sign documents, HR can't sign settlement, non-admin can't revoke access
            assert requests.put(f"{API}/offboarding/{oid}/items/document_handover/complete",
                                headers=_h(*PAY), timeout=15).status_code == 403
            assert requests.put(f"{API}/offboarding/{oid}/items/final_settlement/complete",
                                headers=_h(*HR), timeout=15).status_code == 403
            assert requests.put(f"{API}/offboarding/{oid}/items/access_revocation/complete",
                                headers=_h(*PAY), timeout=15).status_code == 403

            # correct roles complete their items
            assert requests.put(f"{API}/offboarding/{oid}/items/final_settlement/complete",
                                headers=_h(*PAY), timeout=15).json()["all_complete"] is False
            assert requests.put(f"{API}/offboarding/{oid}/items/document_handover/complete",
                                headers=_h(*HR), timeout=15).status_code == 200
            # double-complete blocked
            assert requests.put(f"{API}/offboarding/{oid}/items/document_handover/complete",
                                headers=_h(*HR), timeout=15).status_code == 409
            assert requests.put(f"{API}/offboarding/{oid}/items/equipment_return/complete",
                                headers=_h(*HR), timeout=15).status_code == 200
            last = requests.put(f"{API}/offboarding/{oid}/items/access_revocation/complete",
                                headers=_h(*ADM), timeout=15).json()
            assert last["all_complete"] is True and last["account_deactivated"] is True

            # account deactivated + employee exited + audit trail
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": EMP[1]}, timeout=15)
            assert r.status_code == 401 and "deactivated" in r.text.lower()
            assert _db.employees.find_one({"id": eid})["status"] == "exited"
            assert _db.users.find_one({"id": uid})["disabled"] is True
            for action in ("offboarding_started", "offboarding_completed", "offboarding_item_completed"):
                assert _db.audit_logs.find_one({"action": action, "resource": f"offboardings/{oid}"})

            # status visible on profile fetch for HR + auditor (read-only), not for employee
            r = requests.get(f"{API}/offboarding/employee/{eid}", headers=_h(*HR), timeout=15)
            assert r.status_code == 200 and r.json()["status"] == "completed"
            assert requests.get(f"{API}/offboarding/employee/{eid}", headers=_h(*AUD), timeout=15).status_code == 200
            assert requests.get(f"{API}/offboarding/employee/{eid}", headers=_h(*EMP), timeout=15).status_code == 403
        finally:
            _cleanup_temp(eid, uid)

    def test_cancel_restores_employee(self):
        company_id = _login(*HR)["company_id"]
        eid, uid, _ = _mk_temp_employee_and_user(company_id)
        try:
            oid = requests.post(f"{API}/offboarding/{eid}/start", headers=_h(*HR), timeout=15).json()["id"]
            # payroll cannot cancel
            assert requests.delete(f"{API}/offboarding/{oid}", headers=_h(*PAY), timeout=15).status_code == 403
            assert requests.delete(f"{API}/offboarding/{oid}", headers=_h(*HR), timeout=15).status_code == 200
            assert _db.employees.find_one({"id": eid})["status"] == "active"
            # cancelled offboarding no longer surfaces on the profile
            assert requests.get(f"{API}/offboarding/employee/{eid}", headers=_h(*HR), timeout=15).status_code == 404
        finally:
            _cleanup_temp(eid, uid)
