"""iter38 — Fraud alert push (payslip scan threshold), snooze-from-alert,
coverage planner, reminder nudge stats. Classes added feature-by-feature.
"""
import os
import time
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def gov_admin():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def gov_verification(gov_admin):
    """Ensure a payslip verification exists on the gov tenant."""
    run = _db.payroll_runs.find_one({"company_id": gov_admin["company_id"],
                                     "slips.0": {"$exists": True}})
    assert run, "gov tenant needs a payroll run"
    eid = run["slips"][0]["employee_id"]
    r = requests.get(f"{API}/payroll/runs/{run['id']}/payslip/{eid}.pdf",
                     headers=_h(gov_admin["token"]), timeout=30)
    assert r.status_code == 200
    return _db.payslip_verifications.find_one({"run_id": run["id"], "employee_id": eid})


class TestFraudAlertPush:
    def _clean(self, vid):
        _db.payslip_scans.delete_many({"verification_id": vid})
        _db.payslip_scan_alerts.delete_many({"verification_id": vid})

    def test_alert_fires_once_at_threshold(self, gov_admin, gov_verification):
        vid = gov_verification["id"]
        self._clean(vid)
        try:
            # 4 scans → below threshold → no alert
            for _ in range(4):
                assert requests.get(f"{API}/public/payslip/{vid}", timeout=15).json()["valid"]
            time.sleep(1.2)
            assert _db.payslip_scan_alerts.find_one({"verification_id": vid}) is None

            # 5th scan → flagged → one alert with admin pushes + deep-link payload
            requests.get(f"{API}/public/payslip/{vid}", timeout=15)
            alert = None
            for _ in range(20):
                alert = _db.payslip_scan_alerts.find_one({"verification_id": vid})
                if alert:
                    break
                time.sleep(0.3)
            assert alert, "fraud alert not created"
            assert alert["scan_count"] == 5
            assert alert["employee_name"] == gov_verification["employee_name"]
            assert alert["period"] == gov_verification["period"]
            admin_ids = {u["id"] for u in _db.users.find(
                {"company_id": gov_admin["company_id"], "role": "admin"})}
            assert {n["user_id"] for n in alert["notified"]} == admin_ids

            # 6th scan within 24h → deduped, still exactly one alert
            requests.get(f"{API}/public/payslip/{vid}", timeout=15)
            time.sleep(1.2)
            assert _db.payslip_scan_alerts.count_documents({"verification_id": vid}) == 1
        finally:
            self._clean(vid)

    def test_scan_panel_flag_matches_shared_helper(self, gov_admin, gov_verification):
        """payroll.py now delegates to scan_alerts.flag_scans — same verdicts."""
        vid = gov_verification["id"]
        self._clean(vid)
        try:
            for _ in range(5):
                requests.get(f"{API}/public/payslip/{vid}", timeout=15)
            rows = requests.get(f"{API}/payroll/verification-scans",
                                headers=_h(gov_admin["token"]), timeout=15).json()
            mine = next(r for r in rows if r["verification_id"] == vid)
            assert mine["flagged"] is True and mine["scan_count"] == 5
        finally:
            self._clean(vid)


class TestSnoozeFromAlert:
    """Feature 2 — supervisors may create snoozes for their OWN branch's staff."""

    def test_supervisor_can_snooze_own_branch(self):
        adama = _login("adama.sankoh@gov.sl", "Employee@2026")
        me = _db.employees.find_one({"id": adama["employee_id"]})
        colleague = _db.employees.find_one(
            {"branch_id": me["branch_id"], "id": {"$ne": me["id"]}})
        assert colleague
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = requests.post(f"{API}/mobile/ooz-snoozes", headers=_h(adama["token"]), json={
            "employee_id": colleague["id"], "start_date": today,
            "end_date": today, "reason": "iter38 field assignment"}, timeout=15)
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        try:
            assert r.json()["active"] is True
        finally:
            _db.ooz_snoozes.delete_many({"id": sid})

    def test_supervisor_blocked_for_other_branch(self):
        adama = _login("adama.sankoh@gov.sl", "Employee@2026")
        me = _db.employees.find_one({"id": adama["employee_id"]})
        # deterministically move a colleague to a branch adama does NOT supervise
        other_branch = _db.branches.find_one({
            "company_id": me["company_id"],
            "supervisor_user_id": {"$ne": adama["id"]}})
        assert other_branch, "need a branch adama does not supervise"
        colleague = _db.employees.find_one(
            {"branch_id": me["branch_id"], "id": {"$ne": me["id"]}})
        orig_branch = colleague.get("branch_id")
        _db.employees.update_one({"id": colleague["id"]},
                                 {"$set": {"branch_id": other_branch["id"]}})
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            r = requests.post(f"{API}/mobile/ooz-snoozes", headers=_h(adama["token"]), json={
                "employee_id": colleague["id"], "start_date": today,
                "end_date": today, "reason": "iter38 should fail"}, timeout=15)
            assert r.status_code == 403
        finally:
            _db.employees.update_one({"id": colleague["id"]},
                                     {"$set": {"branch_id": orig_branch}})

    def test_plain_employee_still_blocked(self):
        sia = _login("sia.kallon@gov.sl", "Employee@2026")
        emp = _db.employees.find_one({"id": sia["employee_id"]})
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = requests.post(f"{API}/mobile/ooz-snoozes", headers=_h(sia["token"]), json={
            "employee_id": emp["id"], "start_date": today,
            "end_date": today, "reason": "iter38 should fail"}, timeout=15)
        assert r.status_code == 403


class TestCoveragePlanner:
    """Feature 3 — live branch coverage preview while drafting a leave request."""

    @staticmethod
    def _future(offset):
        from datetime import timedelta
        return (datetime.now(timezone.utc) + timedelta(days=offset)).strftime("%Y-%m-%d")

    def test_employee_previews_own_branch(self):
        sia = _login("sia.kallon@gov.sl", "Employee@2026")
        day = self._future(120)
        r = requests.get(f"{API}/leave/coverage-preview",
                         params={"start_date": day, "end_date": day},
                         headers=_h(sia["token"]), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["threshold"] >= 2
        assert len(body["days"]) == 1
        assert body["days"][0]["off_count"] == 1  # only this draft request
        assert body["days"][0]["breach"] is False
        assert body["warn"] is False

    def test_breach_flags_when_colleagues_off(self):
        import math
        import uuid
        sia = _login("sia.kallon@gov.sl", "Employee@2026")
        me = _db.employees.find_one({"id": sia["employee_id"]})
        staff = list(_db.employees.find({
            "branch_id": me["branch_id"], "status": "active",
            "company_id": me["company_id"], "id": {"$ne": me["id"]}}))
        headcount = len(staff) + 1
        threshold = max(2, math.ceil(0.2 * headcount))
        need = threshold - 1
        assert len(staff) >= need, "branch too small to stage a breach"
        day = self._future(121)
        seeded = []
        for c in staff[:need]:
            doc = {"id": str(uuid.uuid4()), "company_id": me["company_id"],
                   "employee_id": c["id"],
                   "employee_name": f'{c["first_name"]} {c["last_name"]}',
                   "leave_type": "annual", "start_date": day, "end_date": day,
                   "days": 1, "reason": "iter38 coverage seed", "status": "approved",
                   "created_at": datetime.now(timezone.utc).isoformat()}
            _db.leave_requests.insert_one(doc)
            seeded.append(doc["id"])
        try:
            r = requests.get(f"{API}/leave/coverage-preview",
                             params={"start_date": day, "end_date": day},
                             headers=_h(sia["token"]), timeout=15)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["warn"] is True
            assert body["days"][0]["breach"] is True
            assert body["days"][0]["off_count"] == threshold
            assert len(body["days"][0]["already_off"]) == need
        finally:
            _db.leave_requests.delete_many({"id": {"$in": seeded}})

    def test_pending_leaves_do_not_count(self):
        import uuid
        sia = _login("sia.kallon@gov.sl", "Employee@2026")
        me = _db.employees.find_one({"id": sia["employee_id"]})
        colleague = _db.employees.find_one({
            "branch_id": me["branch_id"], "status": "active",
            "company_id": me["company_id"], "id": {"$ne": me["id"]}})
        assert colleague
        day = self._future(122)
        doc = {"id": str(uuid.uuid4()), "company_id": me["company_id"],
               "employee_id": colleague["id"],
               "employee_name": f'{colleague["first_name"]} {colleague["last_name"]}',
               "leave_type": "annual", "start_date": day, "end_date": day,
               "days": 1, "reason": "iter38 pending seed", "status": "pending",
               "created_at": datetime.now(timezone.utc).isoformat()}
        _db.leave_requests.insert_one(doc)
        try:
            r = requests.get(f"{API}/leave/coverage-preview",
                             params={"start_date": day, "end_date": day},
                             headers=_h(sia["token"]), timeout=15)
            assert r.json()["days"][0]["off_count"] == 1
        finally:
            _db.leave_requests.delete_many({"id": doc["id"]})

    def test_admin_previews_for_employee(self, gov_admin):
        emp = _db.employees.find_one({"company_id": gov_admin["company_id"],
                                      "branch_id": {"$ne": None}, "status": "active"})
        day = self._future(123)
        r = requests.get(f"{API}/leave/coverage-preview",
                         params={"start_date": day, "end_date": day,
                                 "employee_id": emp["id"]},
                         headers=_h(gov_admin["token"]), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["headcount"] >= 1

    def test_invalid_dates_rejected(self):
        sia = _login("sia.kallon@gov.sl", "Employee@2026")
        r = requests.get(f"{API}/leave/coverage-preview",
                         params={"start_date": "2026-09-10", "end_date": "2026-09-01"},
                         headers=_h(sia["token"]), timeout=15)
        assert r.status_code == 422
        r = requests.get(f"{API}/leave/coverage-preview",
                         params={"start_date": "nope", "end_date": "2026-09-01"},
                         headers=_h(sia["token"]), timeout=15)
        assert r.status_code == 422


class TestReminderNudgeStats:
    """Feature 4 — admin analytics for weekly training reminder nudges."""

    WEEK = "2020-W01"

    def _clean(self, uids):
        _db.training_reminders.delete_many({"week": self.WEEK})
        _db.training_progress.delete_many({"base_slug": "iter38-nudge-seed",
                                           "user_id": {"$in": uids}})

    def test_week_rollup_and_nudge_rate(self, gov_admin):
        import uuid
        users = list(_db.users.find({"company_id": gov_admin["company_id"]}).limit(2))
        assert len(users) == 2
        uids = [u["id"] for u in users]
        self._clean(uids)
        sent_at = "2020-01-01T09:00:00+00:00"
        for i, uid in enumerate(uids):
            _db.training_reminders.insert_one({
                "id": str(uuid.uuid4()), "user_id": uid,
                "company_id": gov_admin["company_id"], "week": self.WEEK,
                "lang": "en", "remaining": 3, "push_sent": 1 if i == 0 else 0,
                "created_at": sent_at})
        # only the first user completes a video within 7 days of the nudge
        _db.training_progress.insert_one({
            "user_id": uids[0], "base_slug": "iter38-nudge-seed",
            "company_id": gov_admin["company_id"], "lang": "en",
            "completed_at": "2020-01-03T10:00:00+00:00"})
        try:
            r = requests.get(f"{API}/training-progress/reminders/stats",
                             headers=_h(gov_admin["token"]), timeout=15)
            assert r.status_code == 200, r.text
            week = next((w for w in r.json()["weeks"] if w["week"] == self.WEEK), None)
            assert week, "seeded week missing from stats"
            assert week["reminded"] == 2
            assert week["delivered"] == 1
            assert week["completed_after"] == 1
            assert week["nudge_rate"] == 50.0
        finally:
            self._clean(uids)

    def test_completion_outside_window_not_counted(self, gov_admin):
        import uuid
        u = _db.users.find_one({"company_id": gov_admin["company_id"]})
        self._clean([u["id"]])
        _db.training_reminders.insert_one({
            "id": str(uuid.uuid4()), "user_id": u["id"],
            "company_id": gov_admin["company_id"], "week": self.WEEK,
            "lang": "en", "remaining": 1, "push_sent": 1,
            "created_at": "2020-01-01T09:00:00+00:00"})
        # completed 9 days later — outside the 7-day attribution window
        _db.training_progress.insert_one({
            "user_id": u["id"], "base_slug": "iter38-nudge-seed",
            "company_id": gov_admin["company_id"], "lang": "en",
            "completed_at": "2020-01-10T10:00:00+00:00"})
        try:
            r = requests.get(f"{API}/training-progress/reminders/stats",
                             headers=_h(gov_admin["token"]), timeout=15)
            week = next((w for w in r.json()["weeks"] if w["week"] == self.WEEK), None)
            assert week and week["completed_after"] == 0 and week["nudge_rate"] == 0.0
        finally:
            self._clean([u["id"]])

    def test_non_admin_blocked(self):
        sia = _login("sia.kallon@gov.sl", "Employee@2026")
        r = requests.get(f"{API}/training-progress/reminders/stats",
                         headers=_h(sia["token"]), timeout=15)
        assert r.status_code == 403
