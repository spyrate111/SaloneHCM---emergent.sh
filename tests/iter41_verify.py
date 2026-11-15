"""iter41 API/DB verifications: interview emails/reminders, announcement reminders, leavers access."""
import json, sys, time
from datetime import datetime, timedelta, timezone
import requests
sys.path.insert(0, "/app/tests")
from iter41_setup_common import API, db, login  # noqa

cfg = json.load(open("/tmp/iter41.json"))
step = sys.argv[1]
adm = login("admin1@salonehcm.com", "Test@Admin1")
hr = login("hradmin1@salonehcm.com", "Test@HRAdmin1")
A = {"Authorization": f"Bearer {adm['token']}"}
H = {"Authorization": f"Bearer {hr['token']}"}
print("admin1 company == hr company:", adm["company_id"] == hr["company_id"])

if step == "interview":
    app_ = db.job_applications.find_one({"id": cfg["application_id"]}, {"_id": 0})
    print("interview doc:", app_["interview"])
    sch = list(db.email_logs.find({"to": cfg["applicant"], "kind": "interview_scheduled"}, {"_id": 0, "status": 1, "kind": 1}))
    print("interview_scheduled logs:", len(sch), sch[:3])
    r = requests.post(f"{API}/recruitment/run-interview-reminders", headers=H, timeout=20)
    print("HR trigger ->", r.status_code)
    r = requests.post(f"{API}/recruitment/run-interview-reminders", headers=A, timeout=60)
    print("Admin trigger 1 ->", r.status_code, r.text)
    time.sleep(2)
    n1 = db.email_logs.count_documents({"to": cfg["applicant"], "kind": "interview_reminder"})
    r = requests.post(f"{API}/recruitment/run-interview-reminders", headers=A, timeout=60)
    print("Admin trigger 2 ->", r.status_code, r.text)
    time.sleep(2)
    n2 = db.email_logs.count_documents({"to": cfg["applicant"], "kind": "interview_reminder"})
    print("reminder logs after 1st/2nd:", n1, n2)
    print("reminder_sent:", db.job_applications.find_one({"id": cfg["application_id"]})["interview"].get("reminder_sent"))

elif step == "announce":
    aid = cfg["announcement_id"]
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    db.announcements.update_one({"id": aid}, {"$set": {"created_at": old}})
    emp = login("employee1@salonehcm.com", "Test@Employee1")
    E = {"Authorization": f"Bearer {emp['token']}"}
    r = requests.post(f"{API}/announcements/mark-seen", headers=E, json={"ids": [aid]}, timeout=20)
    print("employee1 mark-seen ->", r.status_code)
    print("HR trigger ->", requests.post(f"{API}/announcements/run-reminders", headers=H, timeout=20).status_code)
    print("Employee trigger ->", requests.post(f"{API}/announcements/run-reminders", headers=E, timeout=20).status_code)
    r = requests.post(f"{API}/announcements/run-reminders", headers=A, timeout=120)
    print("Admin trigger ->", r.status_code, r.text)
    doc = db.announcements.find_one({"id": aid}, {"_id": 0})
    print("reminder_count:", doc.get("reminder_count"), "last:", doc.get("reminder_last_at"))
    print("reminders total:", db.announcement_reminders.count_documents({"announcement_id": aid}))
    print("employee1 reminded?", db.announcement_reminders.count_documents({"announcement_id": aid, "user_id": emp["id"]}))
    unread = requests.get(f"{API}/announcements/{aid}/unread", headers=H, timeout=20).json()
    print("unread count via API:", len(unread))
    r = requests.post(f"{API}/announcements/run-reminders", headers=A, timeout=120)
    print("Admin trigger 2 ->", r.status_code, r.text)
    doc = db.announcements.find_one({"id": aid}, {"_id": 0})
    print("reminder_count after 2nd:", doc.get("reminder_count"))

elif step == "leavers":
    for who in [("payroll1@salonehcm.com", "Test@Payroll1"), ("employee1@salonehcm.com", "Test@Employee1")]:
        t = login(*who)
        h = {"Authorization": f"Bearer {t['token']}"}
        print(who[0], "report ->", requests.get(f"{API}/offboarding/report?month=2025-03", headers=h, timeout=20).status_code,
              "csv ->", requests.get(f"{API}/offboarding/report.csv?month=2025-03", headers=h, timeout=20).status_code)
    r = requests.get(f"{API}/offboarding/report?month=2025-03", headers=H, timeout=20)
    print("HR report ->", r.status_code, r.text[:400])
    r = requests.get(f"{API}/offboarding/report?month=bad", headers=H, timeout=20)
    print("HR bad month ->", r.status_code, r.text[:200])
    r = requests.get(f"{API}/offboarding/report", headers=H, timeout=20)
    print("HR missing month ->", r.status_code)
