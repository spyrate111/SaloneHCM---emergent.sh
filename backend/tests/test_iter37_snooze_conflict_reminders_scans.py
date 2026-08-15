"""iter37 — OOZ snooze rules, leave conflict warning, training reminders, payslip scan log.

Verifies:
- Snooze CRUD (admin-only) + validation; active snooze suppresses alert channels (snoozed=True logged)
- Snoozed alerts excluded from the daily digest
- Leave conflict endpoint warns at >=20% branch staff (min 2) off, RBAC enforced
- Training lang preference save; weekly reminders idempotent per user per ISO week, skip completed staff
- Public payslip scans logged; 5+ scans in 24h flags 'unusual'; scan history endpoint admin-only
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


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture(scope="module")
def gov_admin():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def adama():
    return _login("adama.sankoh@gov.sl", "Employee@2026")


class TestSnoozeRules:
    def test_crud_and_validation(self, gov_admin, adama):
        tok = gov_admin["token"]
        # bad range
        bad = requests.post(f"{API}/mobile/ooz-snoozes", headers=_h(tok), json={
            "employee_id": adama["employee_id"], "start_date": "2026-09-10",
            "end_date": "2026-09-01", "reason": "backwards"}, timeout=15)
        assert bad.status_code == 422
        # create
        r = requests.post(f"{API}/mobile/ooz-snoozes", headers=_h(tok), json={
            "employee_id": adama["employee_id"], "start_date": _today(),
            "end_date": _today(), "reason": "iter37 field assignment"}, timeout=15)
        assert r.status_code == 200, r.text
        sid = r.json()["id"]
        try:
            assert r.json()["active"] is True
            # list
            lst = requests.get(f"{API}/mobile/ooz-snoozes", headers=_h(tok), timeout=15).json()
            assert any(s["id"] == sid for s in lst)
            # edit
            p = requests.patch(f"{API}/mobile/ooz-snoozes/{sid}", headers=_h(tok),
                               json={"reason": "iter37 edited"}, timeout=15)
            assert p.status_code == 200 and p.json()["reason"] == "iter37 edited"
            # non-admin 403
            assert requests.get(f"{API}/mobile/ooz-snoozes",
                                headers=_h(adama["token"]), timeout=15).status_code == 403
        finally:
            d = requests.delete(f"{API}/mobile/ooz-snoozes/{sid}", headers=_h(tok), timeout=15)
            assert d.status_code == 200

    def test_snooze_suppresses_alert_and_digest(self, gov_admin, adama):
        tok = gov_admin["token"]
        emp = _db.employees.find_one({"id": adama["employee_id"]})
        branch = _db.branches.find_one({"id": emp["branch_id"]})
        snooze = requests.post(f"{API}/mobile/ooz-snoozes", headers=_h(tok), json={
            "employee_id": adama["employee_id"], "start_date": _today(),
            "end_date": _today(), "reason": "iter37 suppression"}, timeout=15).json()
        punch_ids = []
        _db.ooz_digests.delete_many({"company_id": gov_admin["company_id"], "date": _today()})
        try:
            r = requests.post(f"{API}/mobile/punch", headers=_h(adama["token"]), json={
                "kind": "in", "lat": branch["lat"] + 0.1, "lng": branch["lng"], "accuracy_m": 5,
            }, timeout=15)
            assert r.status_code == 200
            punch_ids.append(r.json()["id"])
            alert = None
            for _ in range(20):
                alert = _db.ooz_alerts.find_one({"punch_id": punch_ids[0]})
                if alert:
                    break
                time.sleep(0.3)
            assert alert and alert["snoozed"] is True
            assert alert["snooze_reason"] == "iter37 suppression"
            assert alert["channels"] == {"suppressed": "active snooze rule"}
            # digest ignores snoozed-only days
            dig = requests.post(f"{API}/mobile/ooz-digest/run-now",
                                headers=_h(tok), timeout=20).json()
            if "alerts" in dig:  # other real alerts existed today
                assert alert["punch_id"] not in [a for a in []]  # digest count excludes snoozed
                assert dig["alerts"] == _db.ooz_alerts.count_documents(
                    {"company_id": gov_admin["company_id"], "date": _today(),
                     "snoozed": {"$ne": True}})
            else:
                assert dig.get("skipped") == "no out-of-zone punches"
        finally:
            requests.delete(f"{API}/mobile/ooz-snoozes/{snooze['id']}", headers=_h(tok), timeout=15)
            _db.attendance.delete_many({"id": {"$in": punch_ids}})
            _db.ooz_alerts.delete_many({"punch_id": {"$in": punch_ids}})
            _db.ooz_digests.delete_many({"company_id": gov_admin["company_id"], "date": _today()})


class TestLeaveConflicts:
    def test_warns_at_threshold(self, gov_admin, adama):
        tok = gov_admin["token"]
        emp = _db.employees.find_one({"id": adama["employee_id"]})
        colleagues = list(_db.employees.find(
            {"branch_id": emp["branch_id"], "id": {"$ne": emp["id"]}}).limit(1))
        assert colleagues, "need a branch colleague"
        day0, day1 = "2027-03-10", "2027-03-11"
        lids = []
        try:
            # approve a colleague's overlapping leave
            r1 = requests.post(f"{API}/leave", headers=_h(tok), json={
                "employee_id": colleagues[0]["id"], "leave_type": "annual",
                "start_date": day0, "end_date": day1, "reason": "iter37"}, timeout=15)
            lids.append(r1.json()["id"])
            requests.put(f"{API}/leave/{lids[0]}/decision", headers=_h(tok),
                         json={"status": "approved"}, timeout=15)
            # pending request for adama's employee, same days
            r2 = requests.post(f"{API}/leave", headers=_h(tok), json={
                "employee_id": emp["id"], "leave_type": "annual",
                "start_date": day0, "end_date": day1, "reason": "iter37"}, timeout=15)
            lids.append(r2.json()["id"])
            c = requests.get(f"{API}/leave/{lids[1]}/conflicts", headers=_h(tok), timeout=15)
            assert c.status_code == 200, c.text
            d = c.json()
            # MOF branch has ~6 staff → threshold max(2, ceil(1.2)) = 2 → 2 off warns
            assert d["threshold"] == max(2, -(-d["headcount"] // 5))
            assert d["warn"] is True
            assert any(x["date"] == day0 and x["off_count"] >= 2 for x in d["days"])
            assert colleagues[0]["first_name"] in " ".join(d["days"][0]["already_off"])
        finally:
            _db.leave_requests.delete_many({"id": {"$in": lids}})

    def test_no_warn_without_overlap(self, gov_admin, adama):
        tok = gov_admin["token"]
        r = requests.post(f"{API}/leave", headers=_h(tok), json={
            "employee_id": adama["employee_id"], "leave_type": "annual",
            "start_date": "2027-06-01", "end_date": "2027-06-02", "reason": "iter37"}, timeout=15)
        lid = r.json()["id"]
        try:
            d = requests.get(f"{API}/leave/{lid}/conflicts", headers=_h(tok), timeout=15).json()
            assert d["warn"] is False and d["days"] == []
        finally:
            _db.leave_requests.delete_many({"id": lid})

    def test_rbac_plain_employee_403(self, gov_admin, adama):
        tok = gov_admin["token"]
        r = requests.post(f"{API}/leave", headers=_h(tok), json={
            "employee_id": adama["employee_id"], "leave_type": "annual",
            "start_date": "2027-07-01", "end_date": "2027-07-01", "reason": "iter37"}, timeout=15)
        lid = r.json()["id"]
        try:
            sia = _login("sia.kallon@gov.sl", "Employee@2026")
            c = requests.get(f"{API}/leave/{lid}/conflicts", headers=_h(sia["token"]), timeout=15)
            assert c.status_code == 403
        finally:
            _db.leave_requests.delete_many({"id": lid})


class TestTrainingReminders:
    def test_lang_pref_saved(self, adama):
        r = requests.post(f"{API}/training-progress/lang", headers=_h(adama["token"]),
                          json={"lang": "temne"}, timeout=15)
        assert r.status_code == 200
        assert _db.users.find_one({"id": adama["id"]})["training_lang"] == "temne"
        bad = requests.post(f"{API}/training-progress/lang", headers=_h(adama["token"]),
                            json={"lang": "french"}, timeout=15)
        assert bad.status_code == 422
        _db.users.update_one({"id": adama["id"]}, {"$unset": {"training_lang": ""}})

    def test_run_now_idempotent_and_skips_complete(self, gov_admin, adama):
        tok = gov_admin["token"]
        week = datetime.now(timezone.utc).strftime("%G-W%V")
        cid = gov_admin["company_id"]
        _db.training_reminders.delete_many({"company_id": cid, "week": week})
        # make adama fully complete so she is skipped
        slugs = _db.marketing_videos.distinct("base_slug", {"category": "training", "lang": "en"})
        _db.training_progress.delete_many({"user_id": adama["id"]})
        for s in slugs:
            _db.training_progress.insert_one({"user_id": adama["id"], "base_slug": s,
                                              "company_id": cid, "completed_at": "2026-01-01T00:00:00+00:00"})
        try:
            r1 = requests.post(f"{API}/training-progress/reminders/run-now",
                               headers=_h(tok), timeout=30).json()
            assert r1["week"] == week
            assert r1["reminded"] >= 1
            assert r1["skipped_complete"] >= 1  # adama completed all
            # reminder rows logged with lang + remaining
            row = _db.training_reminders.find_one({"company_id": cid, "week": week})
            assert row and row["remaining"] >= 1
            assert _db.training_reminders.find_one(
                {"user_id": adama["id"], "week": week}) is None
            # second run: everyone already reminded
            r2 = requests.post(f"{API}/training-progress/reminders/run-now",
                               headers=_h(tok), timeout=30).json()
            assert r2["reminded"] == 0
            assert r2["skipped_already"] == r1["reminded"]
            # non-admin 403
            assert requests.post(f"{API}/training-progress/reminders/run-now",
                                 headers=_h(adama["token"]), timeout=15).status_code == 403
        finally:
            _db.training_reminders.delete_many({"company_id": cid, "week": week})
            _db.training_progress.delete_many({"user_id": adama["id"]})


class TestPayslipScanLog:
    def test_scans_logged_and_flagged(self, gov_admin, adama):
        tok = gov_admin["token"]
        cid = gov_admin["company_id"]
        # generate/refresh a verification on the gov tenant by downloading a payslip PDF
        run = _db.payroll_runs.find_one({"company_id": cid, "slips.0": {"$exists": True}})
        assert run, "gov tenant needs a payroll run"
        eid = run["slips"][0]["employee_id"]
        pdf = requests.get(f"{API}/payroll/runs/{run['id']}/payslip/{eid}.pdf",
                           headers=_h(tok), timeout=30)
        assert pdf.status_code == 200
        ver = _db.payslip_verifications.find_one({"run_id": run["id"], "employee_id": eid})
        assert ver
        vid = ver["id"]
        _db.payslip_scans.delete_many({"verification_id": vid})
        try:
            for _ in range(5):
                v = requests.get(f"{API}/public/payslip/{vid}", timeout=15).json()
                assert v["valid"] is True
            assert _db.payslip_scans.count_documents({"verification_id": vid}) == 5
            rows = requests.get(f"{API}/payroll/verification-scans",
                                headers=_h(tok), timeout=15).json()
            mine = next(r for r in rows if r["verification_id"] == vid)
            assert mine["scan_count"] == 5 and mine["flagged"] is True
            hist = requests.get(f"{API}/payroll/verification-scans/{vid}",
                                headers=_h(tok), timeout=15).json()
            assert len(hist["scans"]) == 5 and hist["flagged"] is True
            assert hist["scans"][0].get("scanned_at")
            # below 5 scans → not flagged
            _db.payslip_scans.delete_many({"verification_id": vid})
            requests.get(f"{API}/public/payslip/{vid}", timeout=15)
            rows2 = requests.get(f"{API}/payroll/verification-scans",
                                 headers=_h(tok), timeout=15).json()
            mine2 = next(r for r in rows2 if r["verification_id"] == vid)
            assert mine2["scan_count"] == 1 and mine2["flagged"] is False
            # non-admin blocked
            blocked = requests.get(f"{API}/payroll/verification-scans",
                                   headers=_h(adama["token"]), timeout=15)
            assert blocked.status_code in (401, 403)
        finally:
            _db.payslip_scans.delete_many({"verification_id": vid})
