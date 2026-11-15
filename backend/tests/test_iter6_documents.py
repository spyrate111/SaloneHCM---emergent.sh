"""Iter6 — Document Vault, Manager Leave Approval, Decision Brief PDF."""
import os
import io
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://salonepaycms.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@salonehcm.sl", "password": "Admin@2026"}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(**ADMIN)


@pytest.fixture(scope="module")
def employees(admin_token):
    r = requests.get(f"{API}/employees", headers=_h(admin_token), timeout=30)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def manager_pair(employees):
    """Find employee with manager_id, and the manager record. Return (manager_emp, report_emp)."""
    by_id = {e["id"]: e for e in employees}
    for emp in employees:
        mid = emp.get("manager_id")
        if mid and mid in by_id:
            return by_id[mid], emp
    pytest.skip("No manager pair found in seed data")


@pytest.fixture(scope="module")
def unrelated_emp(employees, manager_pair):
    mgr, rep = manager_pair
    for e in employees:
        if (e["id"] not in (mgr["id"], rep["id"])
                and e.get("status") == "active"
                and (e.get("email") or "").endswith("@salonehcm.sl")):
            return e
    pytest.skip("No unrelated employee found")


# ---------- Manager Leave Approval ----------
class TestManagerLeaveApproval:
    def test_manager_can_approve_report_leave(self, admin_token, manager_pair):
        mgr, rep = manager_pair
        # Create a leave for the report as admin (admin can specify employee_id)
        r = requests.post(f"{API}/leave", headers=_h(admin_token), json={
            "employee_id": rep["id"],
            "leave_type": "annual",
            "start_date": "2026-03-01",
            "end_date": "2026-03-03",
            "reason": "TEST_manager_approve"
        }, timeout=30)
        assert r.status_code == 200, r.text
        lid = r.json()["id"]

        # Login as manager
        mgr_email = mgr.get("email") or f"{mgr['first_name'].lower()}.{mgr['last_name'].lower()}@salonehcm.sl"
        mtok = _login(mgr_email, "Employee@2026")

        # Manager approves
        r2 = requests.put(f"{API}/leave/{lid}/decision", headers=_h(mtok),
                          json={"status": "approved"}, timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("status") == "approved"

        # Verify audit log
        ar = requests.get(f"{API}/audit", headers=_h(admin_token), timeout=30)
        assert ar.status_code == 200
        actions = [a.get("action") for a in ar.json()]
        assert "manager_leave_approved" in actions

    def test_unrelated_employee_403(self, admin_token, manager_pair, unrelated_emp):
        _mgr, rep = manager_pair
        r = requests.post(f"{API}/leave", headers=_h(admin_token), json={
            "employee_id": rep["id"], "leave_type": "annual",
            "start_date": "2026-04-01", "end_date": "2026-04-02",
            "reason": "TEST_unrelated"
        }, timeout=30)
        lid = r.json()["id"]

        un_email = unrelated_emp.get("email") or f"{unrelated_emp['first_name'].lower()}.{unrelated_emp['last_name'].lower()}@salonehcm.sl"
        utok = _login(un_email, "Employee@2026")
        r2 = requests.put(f"{API}/leave/{lid}/decision", headers=_h(utok),
                          json={"status": "approved"}, timeout=30)
        assert r2.status_code == 403, r2.text

    def test_admin_can_always_approve(self, admin_token, manager_pair):
        _mgr, rep = manager_pair
        r = requests.post(f"{API}/leave", headers=_h(admin_token), json={
            "employee_id": rep["id"], "leave_type": "sick",
            "start_date": "2026-05-01", "end_date": "2026-05-02",
            "reason": "TEST_admin_decide"
        }, timeout=30)
        lid = r.json()["id"]
        r2 = requests.put(f"{API}/leave/{lid}/decision", headers=_h(admin_token),
                          json={"status": "rejected"}, timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("status") == "rejected"


# ---------- Decision Brief PDF ----------
class TestDecisionBriefPDF:
    @pytest.fixture(scope="class")
    def two_scenarios(self, admin_token):
        sids = []
        for i, pct in enumerate([5, 10]):
            r = requests.post(f"{API}/payroll/scenarios", headers=_h(admin_token), json={
                "title": f"TEST_brief_{i}_{uuid.uuid4().hex[:6]}",
                "description": "test",
                "rules": [{"target": "all", "basic_pct_change": pct}],
            }, timeout=30)
            assert r.status_code == 200, r.text
            sids.append(r.json()["id"])
        yield sids
        for sid in sids:
            requests.delete(f"{API}/payroll/scenarios/{sid}", headers=_h(admin_token), timeout=30)

    def test_pdf_returned(self, admin_token, two_scenarios):
        r = requests.post(f"{API}/payroll/scenarios/compare/pdf", headers=_h(admin_token),
                          json={"scenario_ids": two_scenarios}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        assert len(r.content) > 1000
        assert r.content.startswith(b"%PDF")

    def test_pdf_requires_at_least_2(self, admin_token, two_scenarios):
        r = requests.post(f"{API}/payroll/scenarios/compare/pdf", headers=_h(admin_token),
                          json={"scenario_ids": [two_scenarios[0]]}, timeout=60)
        # Pydantic min_length=2 -> 422
        assert r.status_code in (400, 422), r.text


# ---------- Document Vault ----------
PDF_BYTES = (
    b"%PDF-1.4\n%TEST\n1 0 obj<</Type/Catalog>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


class TestDocumentVault:
    @pytest.fixture(scope="class")
    def emp_token(self):
        return _login("aminata.kamara@salonehcm.sl", "Employee@2026")

    @pytest.fixture(scope="class")
    def aminata(self, admin_token):
        r = requests.get(f"{API}/employees", headers=_h(admin_token), timeout=30)
        for e in r.json():
            if e.get("email", "").startswith("aminata.kamara"):
                return e
        pytest.skip("Aminata not seeded")

    @pytest.fixture(scope="class")
    def other_emp(self, admin_token, aminata):
        r = requests.get(f"{API}/employees", headers=_h(admin_token), timeout=30)
        for e in r.json():
            if e["id"] != aminata["id"] and e.get("status") == "active":
                return e
        pytest.skip("No other employee")

    @pytest.fixture(scope="class")
    def uploaded_doc(self, admin_token, aminata):
        files = {"file": ("test.pdf", PDF_BYTES, "application/pdf")}
        data = {"employee_id": aminata["id"], "category": "contract", "description": "TEST_doc"}
        r = requests.post(f"{API}/documents/upload", headers=_h(admin_token),
                          files=files, data=data, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["employee_id"] == aminata["id"]
        assert j["category"] == "contract"
        assert "id" in j
        assert j["size"] == len(PDF_BYTES)
        yield j
        requests.delete(f"{API}/documents/{j['id']}", headers=_h(admin_token), timeout=30)

    def test_upload_admin_pdf_ok(self, uploaded_doc):
        assert uploaded_doc["id"]

    def test_upload_rejects_text(self, admin_token, aminata):
        files = {"file": ("a.txt", b"hello", "text/plain")}
        data = {"employee_id": aminata["id"], "category": "contract"}
        r = requests.post(f"{API}/documents/upload", headers=_h(admin_token),
                          files=files, data=data, timeout=30)
        assert r.status_code == 415, r.text

    def test_upload_rejects_oversize(self, admin_token, aminata):
        big = b"%PDF-1.4\n" + b"A" * (11 * 1024 * 1024)
        files = {"file": ("big.pdf", big, "application/pdf")}
        data = {"employee_id": aminata["id"], "category": "contract"}
        r = requests.post(f"{API}/documents/upload", headers=_h(admin_token),
                          files=files, data=data, timeout=60)
        assert r.status_code == 413, r.text

    def test_upload_non_admin_403(self, emp_token, aminata):
        files = {"file": ("x.pdf", PDF_BYTES, "application/pdf")}
        data = {"employee_id": aminata["id"], "category": "contract"}
        r = requests.post(f"{API}/documents/upload", headers=_h(emp_token),
                          files=files, data=data, timeout=30)
        assert r.status_code == 403, r.text

    def test_list_admin_all(self, admin_token, uploaded_doc):
        r = requests.get(f"{API}/documents", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        ids = [d["id"] for d in r.json()]
        assert uploaded_doc["id"] in ids

    def test_list_filter_by_employee_and_category(self, admin_token, uploaded_doc, aminata):
        r = requests.get(f"{API}/documents",
                         headers=_h(admin_token),
                         params={"employee_id": aminata["id"], "category": "contract"},
                         timeout=30)
        assert r.status_code == 200
        for d in r.json():
            assert d["employee_id"] == aminata["id"]
            assert d["category"] == "contract"

    def test_list_employee_sees_only_own(self, emp_token, aminata, uploaded_doc):
        r = requests.get(f"{API}/documents", headers=_h(emp_token), timeout=30)
        assert r.status_code == 200
        for d in r.json():
            assert d["employee_id"] == aminata["id"]

    def test_employee_docs_other_403(self, emp_token, other_emp):
        r = requests.get(f"{API}/documents/employee/{other_emp['id']}",
                         headers=_h(emp_token), timeout=30)
        assert r.status_code == 403

    def test_download_byte_perfect(self, admin_token, uploaded_doc):
        r = requests.get(f"{API}/documents/{uploaded_doc['id']}/download",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        assert r.content == PDF_BYTES
        assert r.headers.get("content-type", "").startswith("application/pdf")

    def test_download_employee_own_ok(self, emp_token, uploaded_doc):
        r = requests.get(f"{API}/documents/{uploaded_doc['id']}/download",
                         headers=_h(emp_token), timeout=30)
        assert r.status_code == 200
        assert r.content == PDF_BYTES

    def test_download_employee_other_403(self, admin_token, other_emp):
        # Upload a doc for other_emp; try to download as Aminata
        files = {"file": ("o.pdf", PDF_BYTES, "application/pdf")}
        data = {"employee_id": other_emp["id"], "category": "contract"}
        up = requests.post(f"{API}/documents/upload", headers=_h(admin_token),
                           files=files, data=data, timeout=30)
        assert up.status_code == 200
        did = up.json()["id"]
        emp_tok = _login("aminata.kamara@salonehcm.sl", "Employee@2026")
        r = requests.get(f"{API}/documents/{did}/download",
                         headers=_h(emp_tok), timeout=30)
        assert r.status_code == 403
        requests.delete(f"{API}/documents/{did}", headers=_h(admin_token), timeout=30)

    def test_stats_summary(self, admin_token, uploaded_doc):
        r = requests.get(f"{API}/documents/stats/summary",
                         headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        j = r.json()
        assert "total" in j and "by_category" in j
        assert j["total"] >= 1
        cats = [c["category"] for c in j["by_category"]]
        assert "contract" in cats

    def test_soft_delete_then_404(self, admin_token, aminata):
        files = {"file": ("d.pdf", PDF_BYTES, "application/pdf")}
        data = {"employee_id": aminata["id"], "category": "other"}
        up = requests.post(f"{API}/documents/upload", headers=_h(admin_token),
                           files=files, data=data, timeout=30)
        did = up.json()["id"]
        d = requests.delete(f"{API}/documents/{did}", headers=_h(admin_token), timeout=30)
        assert d.status_code == 200
        # list excludes
        lst = requests.get(f"{API}/documents", headers=_h(admin_token), timeout=30)
        assert did not in [x["id"] for x in lst.json()]
        # download 404
        dl = requests.get(f"{API}/documents/{did}/download", headers=_h(admin_token), timeout=30)
        assert dl.status_code == 404

    def test_delete_non_admin_403(self, emp_token, uploaded_doc):
        r = requests.delete(f"{API}/documents/{uploaded_doc['id']}",
                            headers=_h(emp_token), timeout=30)
        assert r.status_code == 403
