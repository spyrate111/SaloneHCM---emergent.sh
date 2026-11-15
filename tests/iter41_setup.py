"""iter41 setup: throwaway vacancy+application, urgent announcement, leaver offboarding."""
import json, os, sys, time, uuid
from datetime import datetime, timedelta, timezone
import requests
from pymongo import MongoClient

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = f"{BASE}/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]


def login(e, p):
    for _ in range(8):
        r = requests.post(f"{API}/auth/login", json={"email": e, "password": p}, timeout=20)
        if r.status_code != 429:
            break
        time.sleep(5)
    r.raise_for_status()
    return r.json()


hr = login("hradmin1@salonehcm.com", "Test@HRAdmin1")
H = {"Authorization": f"Bearer {hr['token']}"}
out = {"company_id": hr["company_id"]}

vac = requests.post(f"{API}/recruitment/vacancies", headers=H, timeout=20,
                    json={"title": "TEST_Iter41 Interview Role", "department": "IT",
                          "grade_level": "6", "closing_date": "2031-09-30", "description": "t"}).json()
out["vacancy_id"] = vac["id"]
applicant = f"test_iter41.{uuid.uuid4().hex[:6]}@example.com"
out["applicant"] = applicant
requests.post(f"{API}/careers/{vac['public_token']}/apply", timeout=20,
              data={"name": "TEST_Iter41 Cand", "email": applicant, "phone": "076"},
              files={"cv": ("cv.pdf", b"%PDF-1.4", "application/pdf")})
for _ in range(10):
    a = db.job_applications.find_one({"email": applicant})
    if a:
        break
    time.sleep(0.5)
out["application_id"] = a["id"]

ann = requests.post(f"{API}/announcements", headers=H, timeout=20,
                    json={"title": "TEST_Iter41 urgent reminder", "body": "x",
                          "priority": "urgent"}).json()
out["announcement_id"] = ann["id"]

eid = str(uuid.uuid4())
db.employees.insert_one({"id": eid, "company_id": hr["company_id"], "first_name": "TEST_Leaver",
                         "last_name": "Iter41", "job_title": "TEST Analyst", "department": "Finance",
                         "status": "terminated", "email": f"test_leaver_{eid[:6]}@example.com"})
oid = str(uuid.uuid4())
db.offboardings.insert_one({"id": oid, "company_id": hr["company_id"], "employee_id": eid,
                            "employee_name": "TEST_Leaver Iter41", "status": "completed",
                            "items": [], "started_at": "2025-03-01T09:00:00+00:00",
                            "completed_at": "2025-03-14T10:00:00+00:00",
                            "exit_interview": {"leaving_reason": "Relocation abroad"}})
out["leaver_employee_id"] = eid
out["offboarding_id"] = oid
json.dump(out, open("/tmp/iter41.json", "w"))
print(json.dumps(out, indent=1))
