"""iter48 — Expense Claims + Recruitment/ATS."""
import io
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]
_tok = {}

PNG = (b"\x89PNG\r\n\x1a\n" + b"0" * 64)
PDF = b"%PDF-1.4 test cv bytes"


def _login(email, password):
    if email in _tok:
        return _tok[email]
    for _ in range(8):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
        if r.status_code != 429:
            break
        time.sleep(5)
    r.raise_for_status()
    _tok[email] = r.json()
    return _tok[email]


def _h(email, pw):
    return {"Authorization": f"Bearer {_login(email, pw)['token']}"}


EMP = ("employee1@salonehcm.com", "Test@Employee1")
EMP3 = ("employee3@salonehcm.com", "Test@Employee3")
AUD = ("auditor1@salonehcm.com", "Test@Auditor1")
PAY = ("payroll1@salonehcm.com", "Test@Payroll1")
HR = ("hradmin1@salonehcm.com", "Test@HRAdmin1")
MGR2 = ("manager2@salonehcm.com", "Test@Manager2")


def _submit_claim(creds, amount=150.0, with_receipt=False, desc="Taxi to NRA office"):
    files = {"receipt": ("r.png", io.BytesIO(PNG), "image/png")} if with_receipt else None
    r = requests.post(f"{API}/expenses", headers=_h(*creds), timeout=20,
                      data={"description": desc, "amount_sle": amount, "category": "transport"},
                      files=files)
    return r


class TestExpenseClaims:
    def test_submit_and_scoping(self):
        r = _submit_claim(EMP, 150.0, with_receipt=True)
        assert r.status_code == 200, r.text
        claim = r.json()
        assert claim["status"] == "pending" and claim["receipt"]["filename"] == "r.png"
        try:
            # owner sees it
            mine = requests.get(f"{API}/expenses", headers=_h(*EMP), timeout=15).json()
            assert any(c["id"] == claim["id"] for c in mine)
            me = _login(*EMP)
            assert all(c["employee_id"] == me["employee_id"] for c in mine)
            # another employee does NOT (different linked record)
            other = requests.get(f"{API}/expenses", headers=_h(*EMP3), timeout=15).json()
            assert all(c["id"] != claim["id"] for c in other)
            # hr + auditor see it
            for creds in (HR, AUD):
                allc = requests.get(f"{API}/expenses", headers=_h(*creds), timeout=15).json()
                assert any(c["id"] == claim["id"] for c in allc)
            # receipt downloadable by owner
            rr = requests.get(f"{API}/expenses/{claim['id']}/receipt", headers=_h(*EMP), timeout=15)
            assert rr.status_code == 200 and rr.content.startswith(b"\x89PNG")
        finally:
            _db.expense_claims.delete_many({"id": claim["id"]})

    def test_bad_category_and_amount(self):
        r = requests.post(f"{API}/expenses", headers=_h(*EMP), timeout=15,
                          data={"description": "x", "amount_sle": 10, "category": "jetski"})
        assert r.status_code == 422
        r2 = requests.post(f"{API}/expenses", headers=_h(*EMP), timeout=15,
                           data={"description": "x", "amount_sle": -5, "category": "meals"})
        assert r2.status_code == 422

    def test_decisions(self):
        claim = _submit_claim(EMP, 200.0).json()
        try:
            # owner cannot decide own
            r = requests.put(f"{API}/expenses/{claim['id']}/decision",
                             json={"status": "approved"}, headers=_h(*EMP), timeout=15)
            assert r.status_code == 403
            # auditor read-only
            r = requests.put(f"{API}/expenses/{claim['id']}/decision",
                             json={"status": "approved"}, headers=_h(*AUD), timeout=15)
            assert r.status_code == 403
            # unrelated employee cannot
            r = requests.put(f"{API}/expenses/{claim['id']}/decision",
                             json={"status": "approved"}, headers=_h(*EMP3), timeout=15)
            assert r.status_code == 403
            # manager of the employee CAN (temporarily wire manager_id)
            emp_eid = _login(*EMP)["employee_id"]
            mgr_eid = _login(*MGR2)["employee_id"]
            prev = _db.employees.find_one({"id": emp_eid})["manager_id"] if \
                "manager_id" in (_db.employees.find_one({"id": emp_eid}) or {}) else None
            _db.employees.update_one({"id": emp_eid}, {"$set": {"manager_id": mgr_eid}})
            try:
                r = requests.put(f"{API}/expenses/{claim['id']}/decision",
                                 json={"status": "approved", "note": "ok"},
                                 headers=_h(*MGR2), timeout=15)
                assert r.status_code == 200, r.text
            finally:
                _db.employees.update_one({"id": emp_eid}, {"$set": {"manager_id": prev}})
            # double decision 409
            r = requests.put(f"{API}/expenses/{claim['id']}/decision",
                             json={"status": "rejected"}, headers=_h(*HR), timeout=15)
            assert r.status_code == 409
        finally:
            _db.expense_claims.delete_many({"id": claim["id"]})

    def test_payroll_reimbursement_flow(self):
        claim = _submit_claim(EMP, 333.33, desc="iter48 reimb").json()
        rid = None
        try:
            requests.put(f"{API}/expenses/{claim['id']}/decision",
                         json={"status": "approved"}, headers=_h(*HR), timeout=15)
            # payroll sees pending reimbursements summary
            s = requests.get(f"{API}/expenses/pending-reimbursements",
                             headers=_h(*PAY), timeout=15).json()
            assert s["count"] >= 1 and s["total"] >= 333.33
            # non-payroll blocked
            assert requests.get(f"{API}/expenses/pending-reimbursements",
                                headers=_h(*HR), timeout=15).status_code == 403
            # run payroll → reimbursement line on slip, claim marked reimbursed
            r = requests.post(f"{API}/payroll/run", headers=_h(*PAY), timeout=60,
                              json={"period_year": 2030, "period_month": 12})
            assert r.status_code == 200, r.text
            run = r.json()
            rid = run["id"]
            emp_eid = _login(*EMP)["employee_id"]
            slip = next(s2 for s2 in run["slips"] if s2["employee_id"] == emp_eid)
            assert slip["reimbursement"] == 333.33
            assert run["totals"]["reimbursements"] >= 333.33
            doc = _db.expense_claims.find_one({"id": claim["id"]})
            assert doc["status"] == "reimbursed" and doc["payroll_run_id"] == rid
        finally:
            _db.expense_claims.delete_many({"id": claim["id"]})
            if rid:
                _db.payroll_runs.delete_many({"id": rid})
                _db.loan_deductions.delete_many({"run_id": rid})
                _db.audit_logs.delete_many({"resource": f"payroll_runs/{rid}"})


class TestRecruitment:
    @pytest.fixture(scope="class")
    def vacancy(self):
        r = requests.post(f"{API}/recruitment/vacancies", headers=_h(*HR), timeout=15,
                          json={"title": "Iter48 Accountant", "department": "Finance",
                                "grade_level": "7", "closing_date": "2031-01-31",
                                "description": "Keep the books."})
        assert r.status_code == 200, r.text
        v = r.json()
        yield v
        _db.job_vacancies.delete_many({"id": v["id"]})
        _db.job_applications.delete_many({"vacancy_id": v["id"]})
        _db.employees.delete_many({"hired_from_application": {"$exists": True},
                                   "email": "jane.iter48@mail.com"})
        _db.audit_logs.delete_many({"resource": {"$regex": "job_"}})

    def test_rbac_on_vacancies(self, vacancy):
        assert requests.get(f"{API}/recruitment/vacancies",
                            headers=_h(*EMP), timeout=15).status_code == 403
        assert requests.post(f"{API}/recruitment/vacancies", headers=_h(*AUD), timeout=15,
                             json={"title": "x", "department": "x",
                                   "closing_date": "2031-01-01"}).status_code == 403
        rows = requests.get(f"{API}/recruitment/vacancies", headers=_h(*HR), timeout=15).json()
        assert any(x["id"] == vacancy["id"] for x in rows)

    def test_public_view_and_apply(self, vacancy):
        tok = vacancy["public_token"]
        r = requests.get(f"{API}/careers/{tok}", timeout=15)  # NO auth
        assert r.status_code == 200
        assert r.json()["accepting"] is True and r.json()["title"] == "Iter48 Accountant"
        r2 = requests.post(f"{API}/careers/{tok}/apply", timeout=20,
                           data={"name": "Jane Iter48", "email": "jane.iter48@mail.com",
                                 "phone": "+23276000000", "cover_note": "I love numbers."},
                           files={"cv": ("cv.pdf", io.BytesIO(PDF), "application/pdf")})
        assert r2.status_code == 200, r2.text
        # duplicate application rejected
        r3 = requests.post(f"{API}/careers/{tok}/apply", timeout=20,
                           data={"name": "Jane Iter48", "email": "jane.iter48@mail.com"},
                           files={"cv": ("cv.pdf", io.BytesIO(PDF), "application/pdf")})
        assert r3.status_code == 409
        # bad mime rejected
        r4 = requests.post(f"{API}/careers/{tok}/apply", timeout=20,
                           data={"name": "Evil", "email": "evil@mail.com"},
                           files={"cv": ("x.exe", io.BytesIO(b"MZ"), "application/octet-stream")})
        assert r4.status_code == 415

    def test_closed_vacancy_rejects(self, vacancy):
        requests.put(f"{API}/recruitment/vacancies/{vacancy['id']}",
                     json={"status": "closed"}, headers=_h(*HR), timeout=15)
        r = requests.post(f"{API}/careers/{vacancy['public_token']}/apply", timeout=15,
                          data={"name": "Late", "email": "late@mail.com"},
                          files={"cv": ("cv.pdf", io.BytesIO(PDF), "application/pdf")})
        assert r.status_code == 410
        requests.put(f"{API}/recruitment/vacancies/{vacancy['id']}",
                     json={"status": "open"}, headers=_h(*HR), timeout=15)

    def test_stages_and_hire(self, vacancy):
        apps = requests.get(f"{API}/recruitment/vacancies/{vacancy['id']}/applications",
                            headers=_h(*HR), timeout=15).json()
        aid = next(a["id"] for a in apps if a["email"] == "jane.iter48@mail.com")
        # invalid stage
        assert requests.patch(f"{API}/recruitment/applications/{aid}/stage",
                              json={"stage": "ghosted"}, headers=_h(*HR), timeout=15).status_code == 422
        for stage in ("shortlisted", "interview", "offer"):
            r = requests.patch(f"{API}/recruitment/applications/{aid}/stage",
                               json={"stage": stage}, headers=_h(*HR), timeout=15)
            assert r.status_code == 200 and r.json()["prompt_create_employee"] is False
        r = requests.patch(f"{API}/recruitment/applications/{aid}/stage",
                           json={"stage": "hired"}, headers=_h(*HR), timeout=15)
        assert r.json()["prompt_create_employee"] is True
        # CV downloadable
        cv = requests.get(f"{API}/recruitment/applications/{aid}/cv", headers=_h(*HR), timeout=15)
        assert cv.status_code == 200 and cv.content.startswith(b"%PDF")
        # create employee from application
        r = requests.post(f"{API}/recruitment/applications/{aid}/create-employee",
                          headers=_h(*HR), timeout=15,
                          json={"job_title": "Accountant", "department": "Finance",
                                "basic_salary_sle": 9000, "hire_date": "2031-02-01"})
        assert r.status_code == 200, r.text
        emp = r.json()
        try:
            assert emp["first_name"] == "Jane" and emp["last_name"] == "Iter48"
            assert emp["email"] == "jane.iter48@mail.com"
            app_doc = _db.job_applications.find_one({"id": aid})
            assert app_doc["hired_employee_id"] == emp["id"]
            # second create blocked
            r2 = requests.post(f"{API}/recruitment/applications/{aid}/create-employee",
                               headers=_h(*HR), timeout=15,
                               json={"job_title": "x", "department": "x",
                                     "basic_salary_sle": 1, "hire_date": "2031-02-01"})
            assert r2.status_code == 409
        finally:
            _db.employees.delete_many({"id": emp["id"]})
            _db.audit_logs.delete_many({"resource": f"employees/{emp['id']}"})
