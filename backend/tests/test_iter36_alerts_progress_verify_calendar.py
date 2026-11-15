"""iter36 — Out-of-zone alerts, training progress, payslip QR verify, leave calendar.

Verifies:
- Out-of-zone punch stores in_zone=False and logs an ooz_alert (sup push+sms attempt, admin push)
- In-zone punch does NOT create an alert
- Daily digest run-now is idempotent per company per day
- Training progress: complete/me/team + RBAC (plain employee 403) + branch filter
- Payslip PDF carries a QR verification block; public endpoint confirms authenticity
- Leave calendar: admin sees month rows; month validation; plain employee (no reports) 403
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


@pytest.fixture(scope="module")
def plain_employee(gov_admin):
    """A gov employee who is neither admin nor a branch supervisor."""
    sup_ids = {b.get("supervisor_user_id")
               for b in _db.branches.find({"company_id": gov_admin["company_id"]})}
    cand = _db.users.find_one({
        "company_id": gov_admin["company_id"], "role": "employee",
        "id": {"$nin": list(filter(None, sup_ids))},
        "employee_id": {"$ne": None},
    })
    if not cand:
        pytest.skip("no plain employee on gov tenant")
    return _login(cand["email"], "Employee@2026")


class TestOutOfZoneAlerts:
    def test_ooz_punch_logs_alert(self, gov_admin, adama):
        emp = _db.employees.find_one({"id": adama["employee_id"]})
        branch = _db.branches.find_one({"id": emp["branch_id"]})
        created = []
        try:
            r = requests.post(f"{API}/mobile/punch", headers=_h(adama["token"]), json={
                "kind": "in", "lat": branch["lat"] + 0.1, "lng": branch["lng"], "accuracy_m": 5,
            }, timeout=15)
            assert r.status_code == 200, r.text
            doc = r.json()
            created.append(doc["id"])
            assert doc["in_zone"] is False
            # alert fires as a background task — poll briefly
            alert = None
            for _ in range(20):
                alert = _db.ooz_alerts.find_one({"punch_id": doc["id"]})
                if alert:
                    break
                time.sleep(0.3)
            assert alert, "ooz_alert not logged"
            assert alert["employee_name"] == doc["employee_name"]
            assert alert["distance_from_branch_m"] > 1000
            ch = alert["channels"]
            assert ch["supervisor_push"] is not None
            assert ch["supervisor_sms"] is not None
            assert isinstance(ch["admin_push"], list)
            # admin endpoint lists it
            lst = requests.get(f"{API}/mobile/ooz-alerts",
                               headers=_h(gov_admin["token"]), timeout=15).json()
            assert any(a["punch_id"] == doc["id"] for a in lst)
        finally:
            _db.attendance.delete_many({"id": {"$in": created}})
            _db.ooz_alerts.delete_many({"punch_id": {"$in": created}})

    def test_in_zone_punch_no_alert(self, adama):
        emp = _db.employees.find_one({"id": adama["employee_id"]})
        branch = _db.branches.find_one({"id": emp["branch_id"]})
        r = requests.post(f"{API}/mobile/punch", headers=_h(adama["token"]), json={
            "kind": "out", "lat": branch["lat"], "lng": branch["lng"], "accuracy_m": 5,
        }, timeout=15)
        assert r.status_code == 200
        doc = r.json()
        try:
            assert doc["in_zone"] is True
            time.sleep(1.5)
            assert _db.ooz_alerts.find_one({"punch_id": doc["id"]}) is None
        finally:
            _db.attendance.delete_many({"id": doc["id"]})

    def test_ooz_endpoints_admin_only(self, adama):
        # adama is a supervisor but NOT an admin
        r = requests.get(f"{API}/mobile/ooz-alerts", headers=_h(adama["token"]), timeout=15)
        assert r.status_code == 403
        r2 = requests.post(f"{API}/mobile/ooz-digest/run-now", headers=_h(adama["token"]), timeout=15)
        assert r2.status_code == 403

    def test_digest_idempotent(self, gov_admin):
        cid = gov_admin["company_id"]
        _db.ooz_digests.delete_many({"company_id": cid, "date": _today()})
        try:
            r1 = requests.post(f"{API}/mobile/ooz-digest/run-now",
                               headers=_h(gov_admin["token"]), timeout=20).json()
            r2 = requests.post(f"{API}/mobile/ooz-digest/run-now",
                               headers=_h(gov_admin["token"]), timeout=20).json()
            if "alerts" in r1:  # there were alerts today → second call must be skipped
                assert r2.get("skipped") == "already sent"
            else:  # no alerts today → both skipped, no digest row
                assert r1.get("skipped") == "no out-of-zone punches"
        finally:
            _db.ooz_digests.delete_many({"company_id": cid, "date": _today()})


class TestTrainingProgress:
    def test_complete_me_and_team(self, gov_admin, adama):
        team0 = requests.get(f"{API}/training-progress/team",
                             headers=_h(gov_admin["token"]), timeout=15).json()
        assert team0["total"] >= 5
        slug = team0["videos"][0]["base_slug"]
        try:
            r = requests.post(f"{API}/training-progress/complete", headers=_h(adama["token"]),
                              json={"base_slug": slug, "lang": "krio"}, timeout=15)
            assert r.status_code == 200
            # idempotent upsert
            requests.post(f"{API}/training-progress/complete", headers=_h(adama["token"]),
                          json={"base_slug": slug}, timeout=15)
            me = requests.get(f"{API}/training-progress/me",
                              headers=_h(adama["token"]), timeout=15).json()
            assert slug in me["completed"] and me["completed_count"] >= 1
            team = requests.get(f"{API}/training-progress/team",
                                headers=_h(gov_admin["token"]), timeout=15).json()
            row = next(r for r in team["rows"] if r["user_id"] == adama["id"])
            assert slug in row["completed"]
        finally:
            _db.training_progress.delete_many({"user_id": adama["id"]})

    def test_unknown_slug_404(self, adama):
        r = requests.post(f"{API}/training-progress/complete", headers=_h(adama["token"]),
                          json={"base_slug": "not-a-video"}, timeout=15)
        assert r.status_code == 404

    def test_team_rbac_and_branch_filter(self, gov_admin, adama, plain_employee):
        r = requests.get(f"{API}/training-progress/team",
                         headers=_h(plain_employee["token"]), timeout=15)
        assert r.status_code == 403
        # supervisor scope = own branches only
        own = {b["id"] for b in _db.branches.find({"supervisor_user_id": adama["id"]})}
        sup = requests.get(f"{API}/training-progress/team",
                           headers=_h(adama["token"]), timeout=15).json()
        assert all((r["branch_id"] in own) for r in sup["rows"])
        # admin branch filter
        bid = next(iter(own))
        filt = requests.get(f"{API}/training-progress/team", params={"branch_id": bid},
                            headers=_h(gov_admin["token"]), timeout=15).json()
        assert all(r["branch_id"] == bid for r in filt["rows"])


class TestPayslipVerify:
    def test_pdf_has_qr_and_public_verify(self):
        emp = _login("aminata.kamara@salonehcm.sl", "Employee@2026")
        slips = requests.get(f"{API}/payroll/my-payslips", headers=_h(emp["token"]), timeout=15).json()
        if not slips:
            pytest.skip("no payslips on demo tenant")
        row = slips[0]
        pdf = requests.get(f"{API}/payroll/runs/{row['run_id']}/payslip/{row['slip']['employee_id']}.pdf",
                           headers=_h(emp["token"]), timeout=30)
        assert pdf.status_code == 200
        from pypdf import PdfReader
        import io as _io, re
        text = PdfReader(_io.BytesIO(pdf.content)).pages[0].extract_text()
        assert "Bank verification" in text and "Verification ID" in text
        vid = re.search(r"verify-payslip/([a-f0-9-]{36})", text).group(1)
        v = requests.get(f"{API}/public/payslip/{vid}", timeout=15).json()
        assert v["valid"] is True
        assert v["employee_name"] == row["slip"]["employee_name"]
        assert v["period"] == row["period"]
        assert abs(v["net"] - row["slip"]["net"]) < 0.01
        # stable ID: second download reuses the same verification record
        pdf2 = requests.get(f"{API}/payroll/runs/{row['run_id']}/payslip/{row['slip']['employee_id']}.pdf",
                            headers=_h(emp["token"]), timeout=30)
        text2 = PdfReader(_io.BytesIO(pdf2.content)).pages[0].extract_text()
        assert vid in text2

    def test_bogus_vid_invalid(self):
        v = requests.get(f"{API}/public/payslip/bogus-000", timeout=15).json()
        assert v["valid"] is False


class TestLeaveCalendar:
    def test_admin_month_scope(self, gov_admin):
        month = _today()[:7]
        # seed one approved leave overlapping this month
        emp = _db.employees.find_one({"company_id": gov_admin["company_id"]})
        lid = None
        try:
            r = requests.post(f"{API}/leave", headers=_h(gov_admin["token"]), json={
                "employee_id": emp["id"], "leave_type": "annual",
                "start_date": f"{month}-10", "end_date": f"{month}-12", "reason": "iter36 test",
            }, timeout=15)
            assert r.status_code == 200, r.text
            lid = r.json()["id"]
            cal = requests.get(f"{API}/leave/calendar", params={"month": month},
                               headers=_h(gov_admin["token"]), timeout=15).json()
            assert cal["month"] == month
            assert any(l["id"] == lid for l in cal["leaves"])
            # a different month excludes it
            other = requests.get(f"{API}/leave/calendar", params={"month": "2020-01"},
                                 headers=_h(gov_admin["token"]), timeout=15).json()
            assert not any(l["id"] == lid for l in other["leaves"])
        finally:
            if lid:
                _db.leave_requests.delete_many({"id": lid})

    def test_bad_month_422(self, gov_admin):
        r = requests.get(f"{API}/leave/calendar", params={"month": "garbage"},
                         headers=_h(gov_admin["token"]), timeout=15)
        assert r.status_code == 422

    def test_plain_employee_403(self, plain_employee):
        # only if they truly have no direct reports
        eid = plain_employee.get("employee_id")
        if eid and _db.employees.count_documents({"manager_id": eid}) > 0:
            pytest.skip("candidate manages reports")
        r = requests.get(f"{API}/leave/calendar", headers=_h(plain_employee["token"]), timeout=15)
        assert r.status_code == 403
