"""iter53 — interview scheduling + announcement reminders + leavers report."""
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
ADM = ("admin1@salonehcm.com", "Test@Admin1")
EMP = ("employee1@salonehcm.com", "Test@Employee1")


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


def _wait(coll, query, tries=12):
    for _ in range(tries):
        row = getattr(_db, coll).find_one(query)
        if row:
            return row
        time.sleep(0.5)
    return None


class TestInterviewScheduling:
    def test_schedule_validate_email_and_reminder(self):
        h = _h(*HR)
        vac = requests.post(f"{API}/recruitment/vacancies", headers=h, timeout=15,
                            json={"title": "Iter53 Interview Role", "department": "IT",
                                  "grade_level": "6", "closing_date": "2031-09-30",
                                  "description": "t"}).json()
        applicant = f"iter53.cand.{uuid.uuid4().hex[:8]}@example.com"
        try:
            requests.post(f"{API}/careers/{vac['public_token']}/apply", timeout=20,
                          data={"name": "Interview Cand", "email": applicant, "phone": "076"},
                          files={"cv": ("cv.pdf", b"%PDF-1.4", "application/pdf")})
            app_doc = _wait("job_applications", {"email": applicant})
            aid = app_doc["id"]

            # validation + role gates
            assert requests.put(f"{API}/recruitment/applications/{aid}/interview",
                                headers=h, json={"date": "2020-01-01", "time": "09:00"},
                                timeout=15).status_code == 422
            assert requests.put(f"{API}/recruitment/applications/{aid}/interview",
                                headers=h, json={"date": "bad", "time": "xx"},
                                timeout=15).status_code == 422
            assert requests.put(f"{API}/recruitment/applications/{aid}/interview",
                                headers=_h(*EMP), json={"date": "2031-01-01", "time": "09:00"},
                                timeout=15).status_code == 403

            # schedule within next 24h so the reminder sweep picks it up
            start = datetime.now(timezone.utc) + timedelta(hours=20)
            r = requests.put(f"{API}/recruitment/applications/{aid}/interview", headers=h,
                             json={"date": start.strftime("%Y-%m-%d"),
                                   "time": start.strftime("%H:%M"),
                                   "location": "https://meet.example/iter53"}, timeout=15)
            assert r.status_code == 200, r.text
            assert _wait("email_logs", {"kind": "interview_scheduled", "to": applicant})
            assert _db.audit_logs.find_one({"action": "interview_scheduled",
                                            "resource": f"job_applications/{aid}"})
            # interview shows on the application record (powers the card chip)
            apps = requests.get(f"{API}/recruitment/vacancies/{vac['id']}/applications",
                                headers=h, timeout=15).json()
            mine = next(a for a in apps if a["id"] == aid)
            assert mine["interview"]["location"] == "https://meet.example/iter53"

            # reminder sweep: sends once, then never again
            r1 = requests.post(f"{API}/recruitment/run-interview-reminders",
                               headers=_h(*ADM), timeout=30)
            assert r1.status_code == 200 and r1.json()["sent"] >= 1
            assert _wait("email_logs", {"kind": "interview_reminder", "to": applicant})
            assert _db.job_applications.find_one({"id": aid})["interview"]["reminder_sent"] is True
            before = _db.email_logs.count_documents({"kind": "interview_reminder", "to": applicant})
            requests.post(f"{API}/recruitment/run-interview-reminders", headers=_h(*ADM), timeout=30)
            assert _db.email_logs.count_documents(
                {"kind": "interview_reminder", "to": applicant}) == before
            # sweep trigger is admin-only
            assert requests.post(f"{API}/recruitment/run-interview-reminders",
                                 headers=h, timeout=15).status_code == 403
        finally:
            _db.job_vacancies.delete_many({"id": vac["id"]})
            _db.job_applications.delete_many({"email": applicant})
            _db.email_logs.delete_many({"to": applicant})


class TestAnnouncementReminders:
    def test_reminder_once_per_employee_and_status(self):
        aid = requests.post(f"{API}/announcements", headers=_h(*HR), timeout=15,
                            json={"title": "Iter53 urgent reminder test", "body": "x",
                                  "priority": "urgent"}).json()["id"]
        try:
            # backdate 25h so the sweep considers it
            old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
            _db.announcements.update_one({"id": aid}, {"$set": {"created_at": old}})
            # employee1 reads it — must NOT be reminded
            requests.post(f"{API}/announcements/mark-seen", headers=_h(*EMP),
                          json={"ids": [aid]}, timeout=15)
            emp_uid = _tok[EMP[0]]["id"]

            assert requests.post(f"{API}/announcements/run-reminders",
                                 headers=_h(*EMP), timeout=15).status_code == 403
            r = requests.post(f"{API}/announcements/run-reminders", headers=_h(*ADM), timeout=60)
            assert r.status_code == 200 and r.json()["sent"] >= 1

            assert _db.announcement_reminders.find_one(
                {"announcement_id": aid, "user_id": emp_uid}) is None
            n = _db.announcement_reminders.count_documents({"announcement_id": aid})
            assert n >= 1
            ann = _db.announcements.find_one({"id": aid})
            assert ann["reminder_count"] == n and ann.get("reminder_last_at")

            # second run adds nothing for this announcement (once per employee)
            requests.post(f"{API}/announcements/run-reminders", headers=_h(*ADM), timeout=60)
            assert _db.announcement_reminders.count_documents({"announcement_id": aid}) == n

            # admin list view exposes reminder status
            rows = requests.get(f"{API}/announcements", headers=_h(*HR), timeout=15).json()
            mine = next(a for a in rows if a["id"] == aid)
            assert mine["reminder_count"] == n
        finally:
            _db.announcements.delete_many({"id": aid})
            _db.announcement_reads.delete_many({"announcement_id": aid})
            _db.announcement_reminders.delete_many({"announcement_id": aid})


class TestLeaversReport:
    def test_report_rows_csv_and_roles(self):
        company_id = _h(*HR) and _tok[HR[0]]["company_id"]
        eid, oid = str(uuid.uuid4()), str(uuid.uuid4())
        _db.employees.insert_one({
            "id": eid, "company_id": company_id, "first_name": "Left", "last_name": "InNov",
            "email": f"l.{eid[:8]}@x.com", "department": "Finance", "job_title": "Accountant",
            "employment_type": "full_time", "basic_salary_sle": 1000, "allowances_sle": 0,
            "status": "exited", "hire_date": "2024-01-01",
            "created_at": datetime.now(timezone.utc).isoformat()})
        _db.offboardings.insert_one({
            "id": oid, "company_id": company_id, "employee_id": eid,
            "employee_name": "Left InNov", "status": "completed",
            "items": [], "started_by": "t", "started_at": "2030-11-01T08:00:00+00:00",
            "completed_at": "2030-11-15T10:00:00+00:00",
            "exit_interview": {"leaving_reason": "retirement", "notes": "n",
                               "recorded_by": "t", "recorded_at": "2030-11-15T10:00:00+00:00"}})
        try:
            r = requests.get(f"{API}/offboarding/report", headers=_h(*HR),
                             params={"month": "2030-11"}, timeout=15)
            assert r.status_code == 200, r.text
            rows = [x for x in r.json()["rows"] if x["employee_id"] == eid]
            assert rows and rows[0]["leaving_date"] == "2030-11-15"
            assert rows[0]["leaving_reason"] == "retirement"
            assert rows[0]["job_title"] == "Accountant" and rows[0]["department"] == "Finance"
            # wrong month excludes it
            r2 = requests.get(f"{API}/offboarding/report", headers=_h(*HR),
                              params={"month": "2030-12"}, timeout=15).json()
            assert not any(x["employee_id"] == eid for x in r2["rows"])
            # validation + roles
            assert requests.get(f"{API}/offboarding/report", headers=_h(*HR),
                                params={"month": "late-2030"}, timeout=15).status_code == 422
            assert requests.get(f"{API}/offboarding/report", headers=_h(*EMP),
                                params={"month": "2030-11"}, timeout=15).status_code == 403
            # CSV
            csv_r = requests.get(f"{API}/offboarding/report.csv", headers=_h(*ADM),
                                 params={"month": "2030-11"}, timeout=15)
            assert csv_r.status_code == 200
            assert "text/csv" in csv_r.headers.get("content-type", "")
            assert "Left InNov" in csv_r.text and "retirement" in csv_r.text
        finally:
            _db.employees.delete_many({"id": eid})
            _db.offboardings.delete_many({"id": oid})
