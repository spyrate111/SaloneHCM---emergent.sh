"""iter32 — Centralized Payroll Voucher Repository (branches + workflow + anti-fraud rails)."""
import os
import random

import pytest
import requests

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
GOV_EMAIL, GOV_PASS = "admin@gov.sl", "GovAdmin@2026"
SUP_EMAIL, SUP_PASS = "adama.sankoh@gov.sl", "Employee@2026"      # branch supervisor + mof_approver
FIN_EMAIL, FIN_PASS = "memuna.tucker@gov.sl", "Employee@2026"     # finance_officer (employee role)
EMP_EMAIL, EMP_PASS = "joseph.williams@gov.sl", "Employee@2026"   # plain employee


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _rand_period():
    return f"20{random.randint(40, 99)}-{random.randint(1, 12):02d}"


@pytest.fixture(scope="module")
def gov_token():
    return _login(GOV_EMAIL, GOV_PASS)


@pytest.fixture(scope="module")
def sup_token():
    return _login(SUP_EMAIL, SUP_PASS)


@pytest.fixture(scope="module")
def fin_token():
    return _login(FIN_EMAIL, FIN_PASS)


@pytest.fixture(scope="module")
def mof_branch(gov_token):
    branches = requests.get(f"{API}/branches", headers=_h(gov_token), timeout=15).json()
    return next(b for b in branches if b["code"] == "MOF-HQ")


@pytest.fixture(scope="module")
def mof_employee(gov_token, mof_branch):
    emps = requests.get(f"{API}/branches/{mof_branch['id']}/employees",
                        headers=_h(gov_token), timeout=15).json()
    return next(e for e in emps if e.get("branch_id") == mof_branch["id"])


def _make_voucher(token, branch, emp, period=None, gross=5000):
    r = requests.post(f"{API}/vouchers", headers=_h(token), json={
        "branch_id": branch["id"], "period": period or _rand_period(),
        "line_items": [{"employee_id": emp["id"], "gross": gross, "paye": 700, "nassit_employee": 250}],
    }, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


class TestBranches:
    def test_seeded_branches_exist_with_supervisor(self, gov_token):
        rows = requests.get(f"{API}/branches", headers=_h(gov_token), timeout=15).json()
        codes = {b["code"] for b in rows}
        assert {"MOF-HQ", "MOH-FT", "MOL-FT"} <= codes
        mof = next(b for b in rows if b["code"] == "MOF-HQ")
        assert mof["supervisor_email"] == SUP_EMAIL
        assert mof["employee_count"] >= 1

    def test_branch_crud_and_duplicate_code(self, gov_token):
        code = f"TST-{random.randint(100, 999)}"
        r = requests.post(f"{API}/branches", headers=_h(gov_token),
                          json={"name": "Iter32 Test Branch", "code": code, "region": "Kenema"}, timeout=15)
        assert r.status_code == 200, r.text
        bid = r.json()["id"]
        dup = requests.post(f"{API}/branches", headers=_h(gov_token),
                            json={"name": "Dup", "code": code}, timeout=15)
        assert dup.status_code == 409
        patch = requests.patch(f"{API}/branches/{bid}", headers=_h(gov_token),
                               json={"region": "Bo"}, timeout=15)
        assert patch.status_code == 200 and patch.json()["region"] == "Bo"
        assert requests.delete(f"{API}/branches/{bid}", headers=_h(gov_token), timeout=15).status_code == 200

    def test_lite_tier_402(self):
        # Bo Council is professional tier — payroll_vouchers is enterprise+gov only
        try:
            t = _login("admin@bocouncil.sl", "BoCouncil@2026")
        except Exception:
            pytest.skip("Bo Council tenant not present")
        r = requests.get(f"{API}/branches", headers=_h(t), timeout=15)
        assert r.status_code == 402


class TestVoucherWorkflow:
    def test_full_chain_four_eyes(self, gov_token, sup_token, fin_token, mof_branch, mof_employee):
        v = _make_voucher(gov_token, mof_branch, mof_employee)
        vid = v["id"]
        assert v["status"] == "draft"
        assert v["voucher_ref"].startswith("PV-")
        assert v["totals"]["net"] == 4050.0

        # submit → supervisor stage (admin isn't the supervisor)
        r = requests.post(f"{API}/vouchers/{vid}/submit", headers=_h(gov_token), json={}, timeout=15)
        assert r.json()["status"] == "pending_supervisor"

        # immutable while in-flight
        patch = requests.patch(f"{API}/vouchers/{vid}", headers=_h(gov_token),
                               json={"line_items": [{"employee_id": mof_employee["id"], "gross": 9999}]}, timeout=15)
        assert patch.status_code == 409

        # supervisor approves → submitted
        r = requests.post(f"{API}/vouchers/{vid}/supervisor-approve", headers=_h(sup_token), json={}, timeout=15)
        assert r.json()["status"] == "submitted"

        # finance review + approve (memuna is not the creator)
        assert requests.post(f"{API}/vouchers/{vid}/start-review", headers=_h(fin_token),
                             json={}, timeout=15).json()["status"] == "under_review"
        assert requests.post(f"{API}/vouchers/{vid}/approve", headers=_h(fin_token),
                             json={}, timeout=15).json()["status"] == "approved"

        # dual control: creator (gov admin) cannot authorize
        r = requests.post(f"{API}/vouchers/{vid}/authorize", headers=_h(gov_token), json={}, timeout=15)
        assert r.status_code == 403
        # approver (memuna) cannot authorize either
        r = requests.post(f"{API}/vouchers/{vid}/authorize", headers=_h(fin_token), json={}, timeout=15)
        assert r.status_code == 403
        # adama (mof_approver, neither creator nor approver) authorizes
        r = requests.post(f"{API}/vouchers/{vid}/authorize", headers=_h(sup_token), json={}, timeout=15)
        assert r.json()["status"] == "payment_authorized"

        detail = requests.get(f"{API}/vouchers/{vid}", headers=_h(gov_token), timeout=15).json()
        actions = [x["action"] for x in detail["status_history"]]
        assert actions == ["created", "submit", "supervisor_approve", "start_review", "approve", "authorize"]
        # terminal — no return possible
        r = requests.post(f"{API}/vouchers/{vid}/return", headers=_h(fin_token),
                          json={"reason": "attempt to reopen authorized voucher"}, timeout=15)
        assert r.status_code == 409

    def test_self_approval_blocked(self, fin_token, gov_token, sup_token, mof_branch, mof_employee):
        v = _make_voucher(fin_token, mof_branch, mof_employee)
        vid = v["id"]
        requests.post(f"{API}/vouchers/{vid}/submit", headers=_h(fin_token), json={}, timeout=15)
        requests.post(f"{API}/vouchers/{vid}/supervisor-approve", headers=_h(sup_token), json={}, timeout=15)
        requests.post(f"{API}/vouchers/{vid}/start-review", headers=_h(fin_token), json={}, timeout=15)
        # memuna created it — she cannot approve her own voucher
        r = requests.post(f"{API}/vouchers/{vid}/approve", headers=_h(fin_token), json={}, timeout=15)
        assert r.status_code == 403
        # gov admin can
        r = requests.post(f"{API}/vouchers/{vid}/approve", headers=_h(gov_token), json={}, timeout=15)
        assert r.json()["status"] == "approved"

    def test_return_for_correction_cycle(self, gov_token, sup_token, fin_token, mof_branch, mof_employee):
        v = _make_voucher(gov_token, mof_branch, mof_employee)
        vid = v["id"]
        requests.post(f"{API}/vouchers/{vid}/submit", headers=_h(gov_token), json={}, timeout=15)
        requests.post(f"{API}/vouchers/{vid}/supervisor-approve", headers=_h(sup_token), json={}, timeout=15)
        # reason too short
        r = requests.post(f"{API}/vouchers/{vid}/return", headers=_h(fin_token),
                          json={"reason": "short"}, timeout=15)
        assert r.status_code == 422
        r = requests.post(f"{API}/vouchers/{vid}/return", headers=_h(fin_token),
                          json={"reason": "Gross does not match establishment register"}, timeout=15)
        assert r.json()["status"] == "returned"
        # editable again
        patch = requests.patch(f"{API}/vouchers/{vid}", headers=_h(gov_token),
                               json={"line_items": [{"employee_id": mof_employee["id"], "gross": 5100}]}, timeout=15)
        assert patch.status_code == 200
        # resubmit bumps revision
        requests.post(f"{API}/vouchers/{vid}/submit", headers=_h(gov_token), json={}, timeout=15)
        detail = requests.get(f"{API}/vouchers/{vid}", headers=_h(gov_token), timeout=15).json()
        assert detail["revision"] == 2
        assert detail["returned_reason"]

    def test_duplicate_and_double_pay_guards(self, gov_token, mof_branch, mof_employee):
        period = _rand_period()
        v = _make_voucher(gov_token, mof_branch, mof_employee, period=period)
        # same branch + period → 409
        dup = requests.post(f"{API}/vouchers", headers=_h(gov_token), json={
            "branch_id": mof_branch["id"], "period": period,
            "line_items": [{"employee_id": mof_employee["id"], "gross": 100}]}, timeout=15)
        assert dup.status_code == 409
        # duplicate employee inside one voucher → 422
        r = requests.post(f"{API}/vouchers", headers=_h(gov_token), json={
            "branch_id": mof_branch["id"], "period": _rand_period(),
            "line_items": [{"employee_id": mof_employee["id"], "gross": 100},
                           {"employee_id": mof_employee["id"], "gross": 200}]}, timeout=15)
        assert r.status_code == 422
        # cleanup draft
        requests.delete(f"{API}/vouchers/{v['id']}", headers=_h(gov_token), timeout=15)

    def test_draft_delete_only(self, gov_token, mof_branch, mof_employee):
        v = _make_voucher(gov_token, mof_branch, mof_employee)
        requests.post(f"{API}/vouchers/{v['id']}/submit", headers=_h(gov_token), json={}, timeout=15)
        r = requests.delete(f"{API}/vouchers/{v['id']}", headers=_h(gov_token), timeout=15)
        assert r.status_code == 409  # submitted vouchers are permanent records

    def test_generate_from_run_and_skip_existing(self, gov_token):
        runs = requests.get(f"{API}/payroll/runs", headers=_h(gov_token), timeout=15).json()
        if not runs:
            pytest.skip("no payroll runs on gov tenant")
        rid = runs[0]["id"]
        r = requests.post(f"{API}/vouchers/generate-from-run/{rid}", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["created"] or d["skipped_existing"]
        # second call skips everything just created
        r2 = requests.post(f"{API}/vouchers/generate-from-run/{rid}", headers=_h(gov_token), timeout=15).json()
        assert len(r2["created"]) == 0
        for c in d["created"]:
            requests.delete(f"{API}/vouchers/{c['id']}", headers=_h(gov_token), timeout=15)

    def test_plain_employee_sees_nothing(self):
        t = _login(EMP_EMAIL, EMP_PASS)
        rows = requests.get(f"{API}/vouchers", headers=_h(t), timeout=15).json()
        assert rows == []
        # and cannot create for a branch they don't supervise
        gov_t = _login(GOV_EMAIL, GOV_PASS)
        branches = requests.get(f"{API}/branches", headers=_h(gov_t), timeout=15).json()
        mof = next(b for b in branches if b["code"] == "MOF-HQ")
        emps = requests.get(f"{API}/branches/{mof['id']}/employees", headers=_h(gov_t), timeout=15).json()
        r = requests.post(f"{API}/vouchers", headers=_h(t), json={
            "branch_id": mof["id"], "period": _rand_period(),
            "line_items": [{"employee_id": emps[0]["id"], "gross": 100}]}, timeout=15)
        assert r.status_code == 403

    def test_audit_trail_endpoint(self, gov_token, mof_branch, mof_employee):
        v = _make_voucher(gov_token, mof_branch, mof_employee)
        logs = requests.get(f"{API}/vouchers/{v['id']}/audit", headers=_h(gov_token), timeout=15).json()
        assert any(log["action"] == "voucher_create" for log in logs)
        requests.delete(f"{API}/vouchers/{v['id']}", headers=_h(gov_token), timeout=15)


class TestUserFlags:
    def test_finance_officer_flag_toggle(self, gov_token):
        users = requests.get(f"{API}/users", headers=_h(gov_token), timeout=15).json()
        target = next(u for u in users if u["email"] == EMP_EMAIL)
        r = requests.patch(f"{API}/users/{target['id']}/flags", headers=_h(gov_token),
                           json={"finance_officer": True}, timeout=15)
        assert r.status_code == 200 and r.json()["finance_officer"] is True
        # revert
        r = requests.patch(f"{API}/users/{target['id']}/flags", headers=_h(gov_token),
                           json={"finance_officer": False}, timeout=15)
        assert r.status_code == 200

    def test_login_exposes_finance_officer(self):
        r = requests.post(f"{API}/auth/login", json={"email": FIN_EMAIL, "password": FIN_PASS}, timeout=15)
        assert r.json()["finance_officer"] is True
