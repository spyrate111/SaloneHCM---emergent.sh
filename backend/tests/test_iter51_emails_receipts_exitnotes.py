"""iter51 — application emails, announcement read receipts, exit interview notes."""
import os
import time
import uuid
from datetime import datetime, timezone

import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]
_tok = {}

HR = ("hradmin1@salonehcm.com", "Test@HRAdmin1")
EMP = ("employee1@salonehcm.com", "Test@Employee1")
PAY = ("payroll1@salonehcm.com", "Test@Payroll1")


def _h(email, pw):
    if email not in _tok:
        for _ in range(8):
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
            if r.status_code != 429:
                break
            time.sleep(5)
        r.raise_for_status()
        _tok[email] = r.json()
    return {"Authorization": f"Bearer {_tok[email]['token']}"}


def _wait_email_log(query, tries=12):
    for _ in range(tries):
        row = _db.email_logs.find_one(query)
        if row:
            return row
        time.sleep(0.5)
    return None


class TestApplicationEmails:
    def test_confirmation_and_stage_emails_logged(self):
        h = _h(*HR)
        vac = requests.post(f"{API}/recruitment/vacancies", headers=h, timeout=15,
                            json={"title": "Iter51 Email Role", "department": "IT",
                                  "grade_level": "5", "closing_date": "2031-06-30",
                                  "description": "t"}).json()
        applicant = f"iter51.applicant.{uuid.uuid4().hex[:8]}@example.com"
        aid = None
        try:
            r = requests.post(f"{API}/careers/{vac['public_token']}/apply", timeout=20,
                              data={"name": "Email Tester", "email": applicant,
                                    "phone": "076000000", "cover_note": "hi"},
                              files={"cv": ("cv.pdf", b"%PDF-1.4 test", "application/pdf")})
            assert r.status_code == 200, r.text
            app_doc = _db.job_applications.find_one({"email": applicant})
            aid = app_doc["id"]

            conf = _wait_email_log({"kind": "application_confirmation", "to": applicant})
            assert conf is not None, "confirmation email was not logged"
            assert conf["status"] in ("sent", "failed", "dry_run")

            r2 = requests.patch(f"{API}/recruitment/applications/{aid}/stage",
                                headers=h, json={"stage": "shortlisted"}, timeout=15)
            assert r2.status_code == 200, r2.text
            stage = _wait_email_log({"kind": "application_stage", "to": applicant,
                                     "meta.stage": "shortlisted"})
            assert stage is not None, "shortlisted stage email was not logged"

            # 'applied' stage change sends no email
            before = _db.email_logs.count_documents({"kind": "application_stage", "to": applicant})
            requests.patch(f"{API}/recruitment/applications/{aid}/stage",
                           headers=h, json={"stage": "applied"}, timeout=15)
            time.sleep(1.5)
            after = _db.email_logs.count_documents({"kind": "application_stage", "to": applicant})
            assert after == before
        finally:
            _db.job_vacancies.delete_many({"id": vac["id"]})
            _db.job_applications.delete_many({"email": applicant})
            _db.email_logs.delete_many({"to": applicant})


class TestReadReceipts:
    def test_mark_seen_counts_and_unread_list(self):
        r = requests.post(f"{API}/announcements", headers=_h(*HR), timeout=15,
                          json={"title": "Iter51 read receipt", "body": "check", "priority": "urgent"})
        aid = r.json()["id"]
        emp_uid = _tok[EMP[0]]["id"] if EMP[0] in _tok else None
        try:
            rr = requests.post(f"{API}/announcements/mark-seen", headers=_h(*EMP),
                               json={"ids": [aid]}, timeout=15)
            assert rr.status_code == 200 and rr.json()["marked"] == 1
            emp_uid = _tok[EMP[0]]["id"]
            # idempotent
            requests.post(f"{API}/announcements/mark-seen", headers=_h(*EMP),
                          json={"ids": [aid]}, timeout=15)
            assert _db.announcement_reads.count_documents(
                {"announcement_id": aid, "user_id": emp_uid}) == 1

            rows = requests.get(f"{API}/announcements", headers=_h(*HR), timeout=15).json()
            mine = next(a for a in rows if a["id"] == aid)
            assert mine["read_count"] >= 1 and mine["total_staff"] > mine["read_count"]
            # employees get no counts
            emp_rows = requests.get(f"{API}/announcements", headers=_h(*EMP), timeout=15).json()
            emp_mine = next(a for a in emp_rows if a["id"] == aid)
            assert "read_count" not in emp_mine

            unread = requests.get(f"{API}/announcements/{aid}/unread", headers=_h(*HR), timeout=15)
            assert unread.status_code == 200
            ids = {u["id"] for u in unread.json()}
            assert emp_uid not in ids and len(ids) > 0
            assert requests.get(f"{API}/announcements/{aid}/unread",
                                headers=_h(*EMP), timeout=15).status_code == 403
        finally:
            _db.announcements.delete_many({"id": aid})
            _db.announcement_reads.delete_many({"announcement_id": aid})


class TestExitInterview:
    def test_record_validate_and_audit(self):
        company_id = _tok.get(HR[0], {}).get("company_id") or _h(*HR) and _tok[HR[0]]["company_id"]
        eid = str(uuid.uuid4())
        _db.employees.insert_one({
            "id": eid, "company_id": company_id, "first_name": "Exit", "last_name": "Notes",
            "email": f"exit.{eid[:8]}@x.com", "department": "Ops", "job_title": "Clerk",
            "employment_type": "full_time", "basic_salary_sle": 1000, "allowances_sle": 0,
            "status": "active", "hire_date": "2024-01-01",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            oid = requests.post(f"{API}/offboarding/{eid}/start", headers=_h(*HR), timeout=15).json()["id"]
            assert requests.put(f"{API}/offboarding/{oid}/exit-interview", headers=_h(*HR),
                                json={"leaving_reason": "sacked", "notes": "x"},
                                timeout=15).status_code == 422
            assert requests.put(f"{API}/offboarding/{oid}/exit-interview", headers=_h(*PAY),
                                json={"leaving_reason": "resignation", "notes": "x"},
                                timeout=15).status_code == 403
            r = requests.put(f"{API}/offboarding/{oid}/exit-interview", headers=_h(*HR),
                             json={"leaving_reason": "resignation",
                                   "notes": "Moving abroad; would rejoin."}, timeout=15)
            assert r.status_code == 200, r.text
            prof = requests.get(f"{API}/offboarding/employee/{eid}", headers=_h(*HR), timeout=15).json()
            assert prof["exit_interview"]["leaving_reason"] == "resignation"
            assert "rejoin" in prof["exit_interview"]["notes"]
            log = _db.audit_logs.find_one({"action": "exit_interview_recorded",
                                           "resource": f"offboardings/{oid}"})
            assert log is not None
        finally:
            _db.employees.delete_many({"id": eid})
            _db.offboardings.delete_many({"employee_id": eid})
