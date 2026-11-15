import json
from iter41_setup_common import db
c = json.load(open("/tmp/iter41.json"))
hr = db.users.find_one({"email": "hradmin1@salonehcm.com"}, {"id": 1})
print("poster self-reminded:", db.announcement_reminders.count_documents({"announcement_id": c["announcement_id"], "user_id": hr["id"]}))
print(db.job_vacancies.delete_one({"id": c["vacancy_id"]}).deleted_count,
      db.job_applications.delete_one({"id": c["application_id"]}).deleted_count,
      db.email_logs.delete_many({"to": c["applicant"]}).deleted_count,
      db.announcements.delete_one({"id": c["announcement_id"]}).deleted_count,
      db.announcement_reads.delete_many({"announcement_id": c["announcement_id"]}).deleted_count,
      db.announcement_reminders.delete_many({"announcement_id": c["announcement_id"]}).deleted_count,
      db.offboardings.delete_one({"id": c["offboarding_id"]}).deleted_count,
      db.employees.delete_one({"id": c["leaver_employee_id"]}).deleted_count)
