"""iter50 — public careers listing + claim decision notifications regression."""
import os
import time

import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]
_tok = {}

HR = ("hradmin1@salonehcm.com", "Test@HRAdmin1")
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


class TestPublicCareersListing:
    def test_lists_only_open_future_vacancies_without_auth(self):
        h = _h(*HR)
        mk = lambda t, closing: requests.post(  # noqa: E731
            f"{API}/recruitment/vacancies", headers=h, timeout=15,
            json={"title": t, "department": "QA", "grade_level": "7",
                  "closing_date": closing, "description": "test"}).json()
        v_open = mk("Iter50 Open Role", "2031-01-31")
        v_closed = mk("Iter50 Closed Role", "2031-01-31")
        v_past = mk("Iter50 Past Role", "2031-01-15")
        ids = [v_open["id"], v_closed["id"], v_past["id"]]
        try:
            requests.put(f"{API}/recruitment/vacancies/{v_closed['id']}", headers=h,
                         json={"status": "closed"}, timeout=15)
            _db.job_vacancies.update_one({"id": v_past["id"]},
                                         {"$set": {"closing_date": "2020-01-01"}})
            rows = requests.get(f"{API}/careers", timeout=15)  # NO auth header
            assert rows.status_code == 200, rows.text
            tokens = {r["public_token"]: r for r in rows.json()}
            assert v_open["public_token"] in tokens
            assert v_closed["public_token"] not in tokens
            assert v_past["public_token"] not in tokens
            row = tokens[v_open["public_token"]]
            for field in ("title", "department", "grade_level", "closing_date", "company_name"):
                assert field in row, f"missing {field}"
            assert "id" not in row and "created_by" not in row  # no internal leakage
        finally:
            _db.job_vacancies.delete_many({"id": {"$in": ids}})


class TestClaimDecisionRegression:
    def test_submit_and_reject_with_note_still_work(self):
        r = requests.post(f"{API}/expenses", headers=_h(*EMP), timeout=15,
                          data={"description": "iter50 taxi", "amount_sle": "150",
                                "category": "transport"})
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        try:
            r2 = requests.put(f"{API}/expenses/{cid}/decision", headers=_h(*HR), timeout=15,
                              json={"status": "rejected", "note": "No receipt attached"})
            assert r2.status_code == 200, r2.text
            claim = _db.expense_claims.find_one({"id": cid})
            assert claim["status"] == "rejected"
            assert claim["decision_note"] == "No receipt attached"
        finally:
            _db.expense_claims.delete_many({"id": cid})
