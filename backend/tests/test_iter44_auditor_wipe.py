"""iter44 — Read-only Auditor role + superadmin test-account wipe."""
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]


def _login(email, password):
    for _ in range(6):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
        if r.status_code != 429:
            break
        time.sleep(5)
    r.raise_for_status()
    return r.json()


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def auditor():
    return _login("auditor1@salonehcm.com", "Test@Auditor1")


@pytest.fixture(scope="module")
def gov_admin():
    return _login("admin@gov.sl", "GovAdmin@2026")


class TestAuditorReads:
    def test_login_role_is_auditor(self, auditor):
        assert auditor["role"] == "auditor"

    def test_audit_log_list(self, auditor):
        r = requests.get(f"{API}/audit", headers=_h(auditor["token"]), timeout=15)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_audit_export_csv(self, auditor):
        r = requests.get(f"{API}/audit/export.csv", headers=_h(auditor["token"]), timeout=20)
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert r.text.splitlines()[0].startswith("timestamp_utc,action,resource")

    def test_audit_export_pdf(self, auditor):
        r = requests.get(f"{API}/audit/export.pdf", headers=_h(auditor["token"]), timeout=30)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"

    def test_compliance_reads(self, auditor):
        for path in ("/compliance/summary", "/compliance/filings"):
            r = requests.get(f"{API}{path}", headers=_h(auditor["token"]), timeout=15)
            assert r.status_code == 200, f"{path}: {r.text}"

    def test_scan_logs(self, auditor):
        r = requests.get(f"{API}/payroll/verification-scans",
                         headers=_h(auditor["token"]), timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_punch_map(self, auditor):
        r = requests.get(f"{API}/mobile/punch/team", headers=_h(auditor["token"]), timeout=15)
        assert r.status_code == 200 and "punches" in r.json()

    def test_leave_records_all_tenant(self, auditor):
        r = requests.get(f"{API}/leave", headers=_h(auditor["token"]), timeout=15)
        assert r.status_code == 200
        expected = min(1000, _db.leave_requests.count_documents(
            {"company_id": auditor["company_id"]}))
        assert len(r.json()) == expected

    def test_attendance_all_tenant(self, auditor):
        r = requests.get(f"{API}/attendance", headers=_h(auditor["token"]), timeout=15)
        assert r.status_code == 200
        expected = min(1000, _db.attendance.count_documents(
            {"company_id": auditor["company_id"]}))
        assert len(r.json()) == expected

    def test_roles_catalog_includes_auditor(self, gov_admin):
        r = requests.get(f"{API}/users/roles", headers=_h(gov_admin["token"]), timeout=15)
        assert "auditor" in [x["role"] for x in r.json()]


class TestAuditorWritesBlocked:
    def test_cannot_create_employee(self, auditor):
        r = requests.post(f"{API}/employees", headers=_h(auditor["token"]), timeout=15,
                          json={"first_name": "No", "last_name": "Way",
                                "email": "noway@x.com", "position": "x",
                                "department": "x", "salary_sle": 1000})
        assert r.status_code == 403

    def test_cannot_decide_leave(self, auditor):
        from datetime import datetime, timezone
        lid = str(uuid.uuid4())
        _db.leave_requests.insert_one({
            "id": lid, "company_id": auditor["company_id"], "employee_id": "x",
            "employee_name": "Iter44 Seed", "leave_type": "annual",
            "start_date": "2027-01-04", "end_date": "2027-01-04", "days": 1,
            "reason": "iter44", "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()})
        try:
            r = requests.put(f"{API}/leave/{lid}/decision",
                             headers=_h(auditor["token"]),
                             json={"status": "approved"}, timeout=15)
            assert r.status_code == 403
            assert _db.leave_requests.find_one({"id": lid})["status"] == "pending"
        finally:
            _db.leave_requests.delete_many({"id": lid})

    def test_cannot_change_roles(self, auditor, gov_admin):
        r = requests.patch(f"{API}/users/{gov_admin.get('user_id', 'x')}/role",
                           headers=_h(auditor["token"]), json={"role": "employee"}, timeout=15)
        assert r.status_code == 403

    def test_cannot_wipe_test_accounts(self, auditor):
        r = requests.delete(f"{API}/users/test-accounts",
                            headers=_h(auditor["token"]), timeout=15)
        assert r.status_code == 403


class TestWipeTestAccounts:
    Q = {"test_account": True, "email": {"$regex": r"@salonehcm\.(com|sl)$"}}

    def test_tenant_admin_blocked(self, gov_admin):
        r = requests.delete(f"{API}/users/test-accounts",
                            headers=_h(gov_admin["token"]), timeout=15)
        assert r.status_code == 403

    def test_superadmin_wipes_and_audits_then_restore(self):
        backup = list(_db.users.find(self.Q))
        assert len(backup) >= 1, "expected seeded test accounts present"
        sa = _login("superadmin1@salonehcm.com", "Test@SuperAdmin1")
        try:
            r = requests.delete(f"{API}/users/test-accounts",
                                headers=_h(sa["token"]), timeout=20)
            assert r.status_code == 200, r.text
            assert r.json()["deleted"] == len(backup)
            assert _db.users.count_documents(self.Q) == 0
            log = _db.audit_logs.find_one({"action": "test_accounts_wiped"},
                                          sort=[("ts", -1)])
            assert log and log["meta"]["deleted"] == len(backup)
            assert log["user_email"] == "superadmin1@salonehcm.com"
        finally:
            for doc in backup:
                doc.pop("_id", None)
            if backup:
                _db.users.insert_many(backup)
            _db.audit_logs.delete_many({"action": "test_accounts_wiped"})

    def test_real_accounts_never_matched(self):
        """The wipe query must not match real (non-flagged) accounts."""
        assert _db.users.count_documents(
            {**self.Q, "email": "admin@salonehcm.sl"}) == 0
        real = _db.users.find_one({"email": "admin@salonehcm.sl"})
        assert real and not real.get("test_account")
