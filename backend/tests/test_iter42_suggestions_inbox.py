"""iter42 — Suggested Dates Inbox: GET /leave/suggestions/mine and
POST /leave/suggestions/{sid}/accept (1-tap resubmit)."""
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
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
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
    """Seed approved leaves so `day` breaches the coverage threshold for Sia's
    branch, plus Sia's own pending request overlapping it."""
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
               "days": 1, "reason": "iter42 breach seed", "status": "approved",
               "created_at": datetime.now(timezone.utc).isoformat()}
        _db.leave_requests.insert_one(doc)
        ids.append(doc["id"])
    lv = {"id": str(uuid.uuid4()), "company_id": me["company_id"],
          "employee_id": me["id"], "employee_name": "Sia Kallon",
          "leave_type": "annual", "start_date": day, "end_date": day,
          "days": 1, "reason": "iter42 pending request", "status": "pending",
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


class TestSuggestionsInbox:
    def test_suggest_persists_and_appears_in_inbox(self, gov_admin, sia):
        day = _future(170)
        lid, ids = _stage_breach(day)
        try:
            r = requests.post(f"{API}/leave/{lid}/suggest-dates",
                              headers=_h(gov_admin["token"]), timeout=15)
            assert r.status_code == 200, r.text
            sugs = r.json()["suggestions"]
            assert len(sugs) >= 1
            # persisted doc
            doc = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            assert doc and doc["employee_name"] == "Sia Kallon"
            assert doc["original"]["start_date"] == day
            # employee inbox shows it
            r2 = requests.get(f"{API}/leave/suggestions/mine",
                              headers=_h(sia["token"]), timeout=15)
            assert r2.status_code == 200
            mine = [s for s in r2.json() if s["leave_id"] == lid]
            assert len(mine) == 1 and mine[0]["suggestions"] == sugs
        finally:
            _cleanup(lid, ids)

    def test_resuggest_supersedes_older(self, gov_admin, sia):
        day = _future(171)
        lid, ids = _stage_breach(day)
        try:
            for _ in range(2):
                assert requests.post(f"{API}/leave/{lid}/suggest-dates",
                                     headers=_h(gov_admin["token"]), timeout=15).status_code == 200
            open_docs = list(_db.leave_suggestions.find({"leave_id": lid, "status": "open"}))
            assert len(open_docs) == 1
            assert _db.leave_suggestions.count_documents(
                {"leave_id": lid, "status": "superseded"}) == 1
            r = requests.get(f"{API}/leave/suggestions/mine",
                             headers=_h(sia["token"]), timeout=15)
            assert len([s for s in r.json() if s["leave_id"] == lid]) == 1
        finally:
            _cleanup(lid, ids)

    def test_inbox_is_own_only(self, gov_admin, sia):
        day = _future(172)
        lid, ids = _stage_breach(day)
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            other = _login("joseph.williams@gov.sl", "Employee@2026")
            r = requests.get(f"{API}/leave/suggestions/mine",
                             headers=_h(other["token"]), timeout=15)
            assert all(s["leave_id"] != lid for s in r.json())
        finally:
            _cleanup(lid, ids)

    def test_accept_resubmits_and_withdraws_original(self, gov_admin, sia):
        day = _future(173)
        lid, ids = _stage_breach(day)
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            sug = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            choice = sug["suggestions"][0]
            r = requests.post(f"{API}/leave/suggestions/{sug['id']}/accept",
                              json={"start_date": choice["start_date"],
                                    "end_date": choice["end_date"]},
                              headers=_h(sia["token"]), timeout=15)
            assert r.status_code == 200, r.text
            new = r.json()
            assert new["status"] == "pending"
            assert new["start_date"] == choice["start_date"]
            assert new["end_date"] == choice["end_date"]
            ids.append(new["id"])
            # original withdrawn, suggestion closed
            assert _db.leave_requests.find_one({"id": lid})["status"] == "withdrawn"
            assert _db.leave_suggestions.find_one({"id": sug["id"]})["status"] == "accepted"
            # gone from inbox
            r2 = requests.get(f"{API}/leave/suggestions/mine",
                              headers=_h(sia["token"]), timeout=15)
            assert all(s["id"] != sug["id"] for s in r2.json())
            # audit trail
            log = _db.audit_logs.find_one({"action": "leave_suggestion_accepted",
                                           "meta.from_suggestion": sug["id"]})
            assert log
        finally:
            _cleanup(lid, ids)
            _db.audit_logs.delete_many({"action": "leave_suggestion_accepted"})

    def test_accept_rejects_range_not_suggested(self, gov_admin, sia):
        day = _future(174)
        lid, ids = _stage_breach(day)
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            sug = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            r = requests.post(f"{API}/leave/suggestions/{sug['id']}/accept",
                              json={"start_date": "2031-01-01", "end_date": "2031-01-01"},
                              headers=_h(sia["token"]), timeout=15)
            assert r.status_code == 422
        finally:
            _cleanup(lid, ids)

    def test_accept_blocked_for_other_employee(self, gov_admin, sia):
        day = _future(175)
        lid, ids = _stage_breach(day)
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            sug = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            other = _login("joseph.williams@gov.sl", "Employee@2026")
            choice = sug["suggestions"][0]
            r = requests.post(f"{API}/leave/suggestions/{sug['id']}/accept",
                              json={"start_date": choice["start_date"],
                                    "end_date": choice["end_date"]},
                              headers=_h(other["token"]), timeout=15)
            assert r.status_code == 403
            assert _db.leave_suggestions.find_one({"id": sug["id"]})["status"] == "open"
        finally:
            _cleanup(lid, ids)

    def test_accept_twice_fails(self, gov_admin, sia):
        day = _future(176)
        lid, ids = _stage_breach(day)
        try:
            requests.post(f"{API}/leave/{lid}/suggest-dates",
                          headers=_h(gov_admin["token"]), timeout=15)
            sug = _db.leave_suggestions.find_one({"leave_id": lid, "status": "open"})
            choice = sug["suggestions"][0]
            body = {"start_date": choice["start_date"], "end_date": choice["end_date"]}
            r1 = requests.post(f"{API}/leave/suggestions/{sug['id']}/accept",
                               json=body, headers=_h(sia["token"]), timeout=15)
            assert r1.status_code == 200
            ids.append(r1.json()["id"])
            r2 = requests.post(f"{API}/leave/suggestions/{sug['id']}/accept",
                               json=body, headers=_h(sia["token"]), timeout=15)
            assert r2.status_code == 404
        finally:
            _cleanup(lid, ids)
            _db.audit_logs.delete_many({"action": "leave_suggestion_accepted"})
