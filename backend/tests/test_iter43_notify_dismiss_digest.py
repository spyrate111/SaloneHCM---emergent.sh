"""iter43 — Approver notify on suggestion accept, suggestion dismiss,
and extended digest preview (ooz punches + training nudges)."""
import os
import math
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]


def _login(email, password):
    import time
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
def gov_admin():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def sia():
    return _login("sia.kallon@gov.sl", "Employee@2026")


def _future(offset):
    return (datetime.now(timezone.utc) + timedelta(days=offset)).strftime("%Y-%m-%d")


def _stage_breach(day):
    sia_user = _db.users.find_one({"email": "sia.kallon@gov.sl"})
    me = _db.employees.find_one({"id": sia_user["employee_id"]})
    staff = list(_db.employees.find({
        "branch_id": me["branch_id"], "status": "active",
        "company_id": me["company_id"], "id": {"$ne": me["id"]}}))
    threshold = max(2, math.ceil(0.2 * (len(staff) + 1)))
    ids = []
    for c in staff[:threshold - 1]:
        doc = {"id": str(uuid.uuid4()), "company_id": me["company_id"],
               "employee_id": c["id"],
               "employee_name": f'{c["first_name"]} {c["last_name"]}',
               "leave_type": "annual", "start_date": day, "end_date": day,
               "days": 1, "reason": "iter43 breach seed", "status": "approved",
               "created_at": datetime.now(timezone.utc).isoformat()}
        _db.leave_requests.insert_one(doc)
        ids.append(doc["id"])
    lv = {"id": str(uuid.uuid4()), "company_id": me["company_id"],
          "employee_id": me["id"], "employee_name": "Sia Kallon",
          "leave_type": "annual", "start_date": day, "end_date": day,
          "days": 1, "reason": "iter43 pending request", "status": "pending",
          "created_at": datetime.now(timezone.utc).isoformat()}
    _db.leave_requests.insert_one(lv)
    ids.append(lv["id"])
    return lv["id"], ids


def _cleanup(lid, ids):
    _db.leave_requests.delete_many({"id": {"$in": ids}})
    _db.leave_requests.delete_many({"reason": "Re-submitted with approver-suggested dates",
                                    "employee_name": "Sia Kallon"})
    _db.leave_suggestions.delete_many({"leave_id": lid})
    _db.audit_logs.delete_many({"resource": f"leave_requests/{lid}"})


class TestApproverNotify:
    def test_suggested_by_user_id_persisted(self, gov_admin, sia):
        day = _future(180)
        lid, ids = _stage_breach(day)
        try:
            r = requests.post(f"{API}/leave/{lid}/suggest-dates",
                              headers=_h(gov_admin["token"]), timeout=15)
            assert r.status_code == 200, r.text
            doc = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            admin_user = _db.users.find_one({"email": "admin@gov.sl"})
            assert doc["suggested_by_user_id"] == admin_user["id"]
        finally:
            _cleanup(lid, ids)

    def test_accept_pushes_to_approver(self, gov_admin, sia):
        day = _future(181)
        lid, ids = _stage_breach(day)
        admin_user = _db.users.find_one({"email": "admin@gov.sl"})
        sub_id = str(uuid.uuid4())
        _db.push_subscriptions.insert_one({
            "id": sub_id, "user_id": admin_user["id"],
            "endpoint": "https://updates.push.example.invalid/wpush/iter43",
            "keys": {"p256dh": "BPfake" + "A" * 80, "auth": "fakeauth1234"},
        })
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            sug = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            choice = sug["suggestions"][0]
            r = requests.post(f"{API}/leave/suggestions/{sug['id']}/accept",
                              json={"start_date": choice["start_date"],
                                    "end_date": choice["end_date"]},
                              headers=_h(sia["token"]), timeout=20)
            assert r.status_code == 200, r.text
            new = r.json()
            assert "push" in new
            ids.append(new["id"])
            log = _db.push_logs.find_one({"user_id": admin_user["id"],
                                          "payload.kind": "leave_suggestion_accepted"})
            assert log, "push_logs should record the approver notification"
            assert "Sia Kallon" in log["payload"]["body"]
            assert log["payload"]["url"] == f"/m/leave?focus={new['id']}"
        finally:
            _db.push_subscriptions.delete_many({"id": sub_id})
            _db.push_logs.delete_many({"payload.kind": "leave_suggestion_accepted"})
            _cleanup(lid, ids)
            _db.audit_logs.delete_many({"action": "leave_suggestion_accepted"})

    def test_accept_without_approver_id_skips_push(self, sia):
        day = _future(182)
        sia_user = _db.users.find_one({"email": "sia.kallon@gov.sl"})
        me = _db.employees.find_one({"id": sia_user["employee_id"]})
        lid = str(uuid.uuid4())
        _db.leave_requests.insert_one({
            "id": lid, "company_id": me["company_id"], "employee_id": me["id"],
            "employee_name": "Sia Kallon", "leave_type": "annual",
            "start_date": day, "end_date": day, "days": 1,
            "reason": "iter43 legacy", "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()})
        sid = str(uuid.uuid4())
        alt = _future(183)
        _db.leave_suggestions.insert_one({
            "id": sid, "leave_id": lid, "company_id": me["company_id"],
            "employee_id": me["id"], "employee_name": "Sia Kallon",
            "leave_type": "annual",
            "original": {"start_date": day, "end_date": day},
            "suggestions": [{"start_date": alt, "end_date": alt}],
            "suggested_by": "Legacy Approver", "status": "open",
            "created_at": datetime.now(timezone.utc).isoformat()})
        try:
            r = requests.post(f"{API}/leave/suggestions/{sid}/accept",
                              json={"start_date": alt, "end_date": alt},
                              headers=_h(sia["token"]), timeout=15)
            assert r.status_code == 200, r.text
            assert r.json()["push"]["skipped"] == "no_approver"
        finally:
            _cleanup(lid, [lid, r.json().get("id", "")])
            _db.audit_logs.delete_many({"action": "leave_suggestion_accepted"})


class TestSuggestionDismiss:
    def test_dismiss_removes_from_inbox_keeps_original(self, gov_admin, sia):
        day = _future(184)
        lid, ids = _stage_breach(day)
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            sug = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            r = requests.post(f"{API}/leave/suggestions/{sug['id']}/dismiss",
                              headers=_h(sia["token"]), timeout=15)
            assert r.status_code == 200 and r.json()["ok"] is True
            assert _db.leave_suggestions.find_one({"id": sug["id"]})["status"] == "dismissed"
            # gone from inbox
            r2 = requests.get(f"{API}/leave/suggestions/mine",
                              headers=_h(sia["token"]), timeout=15)
            assert all(s["id"] != sug["id"] for s in r2.json())
            # original stays pending
            assert _db.leave_requests.find_one({"id": lid})["status"] == "pending"
            # audited
            assert _db.audit_logs.find_one({"action": "leave_suggestion_dismissed",
                                            "resource": f"leave_suggestions/{sug['id']}"})
            _db.audit_logs.delete_many({"resource": f"leave_suggestions/{sug['id']}"})
        finally:
            _cleanup(lid, ids)

    def test_dismiss_wrong_employee_403(self, gov_admin, sia):
        day = _future(185)
        lid, ids = _stage_breach(day)
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            sug = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            other = _login("joseph.williams@gov.sl", "Employee@2026")
            r = requests.post(f"{API}/leave/suggestions/{sug['id']}/dismiss",
                              headers=_h(other["token"]), timeout=15)
            assert r.status_code == 403
            assert _db.leave_suggestions.find_one({"id": sug["id"]})["status"] == "open"
        finally:
            _cleanup(lid, ids)

    def test_dismiss_twice_404_and_accept_after_dismiss_404(self, gov_admin, sia):
        day = _future(186)
        lid, ids = _stage_breach(day)
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            sug = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            assert requests.post(f"{API}/leave/suggestions/{sug['id']}/dismiss",
                                 headers=_h(sia["token"]), timeout=15).status_code == 200
            assert requests.post(f"{API}/leave/suggestions/{sug['id']}/dismiss",
                                 headers=_h(sia["token"]), timeout=15).status_code == 404
            choice = sug["suggestions"][0]
            r = requests.post(f"{API}/leave/suggestions/{sug['id']}/accept",
                              json={"start_date": choice["start_date"],
                                    "end_date": choice["end_date"]},
                              headers=_h(sia["token"]), timeout=15)
            assert r.status_code == 404
            _db.audit_logs.delete_many({"resource": f"leave_suggestions/{sug['id']}"})
        finally:
            _cleanup(lid, ids)


class TestDigestPreviewExtended:
    def _seed(self, cid):
        now = datetime.now(timezone.utc).isoformat()
        ooz_id, tr_id, scan_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        _db.ooz_alerts.insert_one({
            "id": ooz_id, "company_id": cid, "employee_name": "Iter43 Ooz",
            "branch_name": "MOF-HQ", "kind": "in", "distance_from_branch_m": 812.0,
            "clocked_at": now, "date": now[:10], "created_at": now})
        _db.training_reminders.insert_one({
            "id": tr_id, "user_id": "iter43-fake", "company_id": cid,
            "week": "iter43", "lang": "en", "remaining": 3, "push_sent": 1,
            "created_at": now})
        _db.payslip_scan_alerts.insert_one({
            "id": scan_id, "company_id": cid, "verification_id": "iter43-ver",
            "employee_name": "Iter43 Scan", "period": "2026-08", "scan_count": 7,
            "created_at": now})
        return ooz_id, tr_id, scan_id

    def _clean(self, ooz_id, tr_id, scan_id):
        _db.ooz_alerts.delete_many({"id": ooz_id})
        _db.training_reminders.delete_many({"id": tr_id})
        _db.payslip_scan_alerts.delete_many({"id": scan_id})

    def test_preview_includes_scans_ooz_and_nudges(self, gov_admin):
        seeded = self._seed(gov_admin["company_id"])
        try:
            r = requests.get(f"{API}/users/me/digest-preview",
                             headers=_h(gov_admin["token"]), timeout=15)
            assert r.status_code == 200, r.text
            body = r.json()
            assert any(a["employee_name"] == "Iter43 Scan" for a in body["scan_alerts"])
            assert any(o["employee_name"] == "Iter43 Ooz" for o in body["ooz_punches"])
            assert body["training_nudges_sent"] >= 1
            assert "since" in body
        finally:
            self._clean(*seeded)

    def test_preview_admin_only(self, sia):
        r = requests.get(f"{API}/users/me/digest-preview",
                         headers=_h(sia["token"]), timeout=15)
        assert r.status_code == 403

    def test_preview_tenant_scoped(self, gov_admin):
        """Alerts seeded on another tenant must not leak into gov preview."""
        other = _db.companies.find_one({"id": {"$ne": gov_admin["company_id"]}})
        now = datetime.now(timezone.utc).isoformat()
        oid = str(uuid.uuid4())
        _db.ooz_alerts.insert_one({
            "id": oid, "company_id": other["id"], "employee_name": "Iter43 Foreign",
            "branch_name": "X", "kind": "in", "distance_from_branch_m": 1.0,
            "clocked_at": now, "date": now[:10], "created_at": now})
        try:
            r = requests.get(f"{API}/users/me/digest-preview",
                             headers=_h(gov_admin["token"]), timeout=15)
            assert all(o["employee_name"] != "Iter43 Foreign" for o in r.json()["ooz_punches"])
        finally:
            _db.ooz_alerts.delete_many({"id": oid})
