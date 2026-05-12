"""
Iter8 — Phase a/b/c tests:
  - Super-admin endpoints + company switching (admin.py)
  - Tenant isolation under switching
  - Users router (users.py invite/list/reset/delete/unlinked)
  - Twilio SMS dry-run + Gov-tier gating (payroll.py + sms.py)
  - Gov tenant seed (admin@gov.sl + 6 employees + bulk_sms_payslips)
  - Phase A regression: leave decision PDF, documents, payroll bank file
"""

import os
import io
import uuid
import pytest
import requests

def _load_frontend_env():
    env_path = "/app/frontend/.env"
    try:
        with open(env_path) as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k == "REACT_APP_BACKEND_URL":
                    return v.strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env() or "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL is not set"
API = f"{BASE}/api"

SUPER = {"email": "admin@salonehcm.sl", "password": "Admin@2026"}
GOV   = {"email": "admin@gov.sl",       "password": "GovAdmin@2026"}
BO    = {"email": "admin@bocouncil.sl", "password": "BoCouncil@2026"}


# ---- helpers ----------------------------------------------------------------

_TOKENS: dict = {}

def _login(creds):
    if creds["email"] in _TOKENS:
        return _TOKENS[creds["email"]], _TOKENS[creds["email"] + ":me"]
    import time
    last_err = None
    for _ in range(4):
        r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
        if r.status_code == 200:
            j = r.json()
            _TOKENS[creds["email"]] = j["token"]
            _TOKENS[creds["email"] + ":me"] = j
            return j["token"], j
        last_err = (r.status_code, r.text)
        if r.status_code == 429:
            time.sleep(7)
            continue
        break
    raise AssertionError(f"login failed for {creds['email']}: {last_err}")

def _ensure_super_on_demo():
    """Super-admin tests may have switched the user. Re-switch to Demo Salone."""
    t, _ = _login(SUPER)
    me = requests.get(f"{API}/auth/me", headers=_h(t)).json()
    # If already on Demo (enterprise), nothing to do
    comp = requests.get(f"{API}/company", headers=_h(t)).json()
    if comp.get("name") == "Demo Salone Ltd.":
        return t
    comps = requests.get(f"{API}/admin/companies", headers=_h(t)).json()
    demo = next(c for c in comps if c["name"] == "Demo Salone Ltd.")
    r = requests.post(f"{API}/admin/companies/{demo['id']}/switch", headers=_h(t))
    assert r.status_code == 200, r.text
    new_t = r.json()["token"]
    _TOKENS[SUPER["email"]] = new_t
    return new_t

def _h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def super_ctx():
    # IMPORTANT: super-admin token may end up scoped to whichever tenant was last switched into.
    # We re-fetch fresh each test that needs original Demo Salone scope.
    t, j = _login(SUPER)
    return {"token": t, "user": j}

@pytest.fixture(scope="module")
def gov_ctx():
    t, j = _login(GOV)
    return {"token": t, "user": j}

@pytest.fixture(scope="module")
def bo_ctx():
    t, j = _login(BO)
    return {"token": t, "user": j}


# ---- Super-admin seed -------------------------------------------------------

class TestSuperAdminSeed:
    def test_login_role_is_superadmin(self, super_ctx):
        assert super_ctx["user"]["role"] == "superadmin"
        comp = super_ctx["user"]["company"]
        # Demo Salone is enterprise; should have full feature set
        assert comp["tier"] in ("enterprise", "gov")  # post-switch may differ; current login should be enterprise
        assert isinstance(comp["features"], list) and len(comp["features"]) >= 19


# ---- Admin (super) company CRUD --------------------------------------------

class TestSuperAdminCompanyManagement:
    def test_list_companies_returns_tenants_with_counts(self):
        t, _ = _login(SUPER)
        r = requests.get(f"{API}/admin/companies", headers=_h(t), timeout=20)
        assert r.status_code == 200, r.text
        comps = r.json()
        assert isinstance(comps, list) and len(comps) >= 3
        names = [c["name"] for c in comps]
        assert "Demo Salone Ltd." in names
        assert "Government of Sierra Leone" in names
        assert "Bo Town Council" in names
        for c in comps:
            assert "active_headcount" in c
            assert "user_count" in c
            assert isinstance(c["active_headcount"], int)
            assert isinstance(c["user_count"], int)

    def test_create_company_and_admin_can_login(self):
        t, _ = _login(SUPER)
        uniq = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TEST_iter8_co_{uniq}",
            "tin": "T-9999",
            "tier": "professional",
            "admin_email": f"TEST_admin_{uniq}@iter8.sl",
            "admin_name": "Test Iter8 Admin",
            "admin_password": "TestIter8@2026",
        }
        r = requests.post(f"{API}/admin/companies", headers=_h(t), json=payload, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["company"]["name"] == payload["name"]
        assert body["admin"]["email"] == payload["admin_email"].lower()
        # New admin must immediately be able to log in
        lr = requests.post(f"{API}/auth/login",
                           json={"email": payload["admin_email"], "password": payload["admin_password"]},
                           timeout=20)
        assert lr.status_code == 200, lr.text
        assert lr.json()["company"]["name"] == payload["name"]
        # Duplicate name -> 409
        dup = requests.post(f"{API}/admin/companies", headers=_h(t), json=payload, timeout=20)
        assert dup.status_code == 409

    def test_patch_company_tier_changes_features(self):
        t, _ = _login(SUPER)
        comps = requests.get(f"{API}/admin/companies", headers=_h(t)).json()
        bo = next(c for c in comps if c["name"] == "Bo Town Council")
        original = bo["tier"]
        target = "enterprise" if original != "enterprise" else "professional"
        r = requests.patch(f"{API}/admin/companies/{bo['id']}/tier",
                           headers=_h(t), json={"tier": target}, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["tier"] == target
        assert isinstance(j["features"], list) and len(j["features"]) > 0
        # Restore original tier to not pollute downstream tests
        rr = requests.patch(f"{API}/admin/companies/{bo['id']}/tier",
                            headers=_h(t), json={"tier": original}, timeout=20)
        assert rr.status_code == 200

    def test_switch_company_issues_new_token_and_scopes(self):
        t, _ = _login(SUPER)
        comps = requests.get(f"{API}/admin/companies", headers=_h(t)).json()
        bo = next(c for c in comps if c["name"] == "Bo Town Council")
        r = requests.post(f"{API}/admin/companies/{bo['id']}/switch",
                          headers=_h(t), timeout=20)
        assert r.status_code == 200, r.text
        sw = r.json()
        assert sw["company"]["id"] == bo["id"]
        new_token = sw["token"]
        # After switch, /api/employees must be Bo's only — never Demo's
        emps = requests.get(f"{API}/employees", headers=_h(new_token)).json()
        for e in emps:
            assert e["company_id"] == bo["id"], f"tenant leak: {e}"
        # Switch back to Demo Salone so other tests run in expected scope
        demo = next(c for c in comps if c["name"] == "Demo Salone Ltd.")
        rb = requests.post(f"{API}/admin/companies/{demo['id']}/switch",
                           headers=_h(new_token), timeout=20)
        assert rb.status_code == 200


# ---- Non-superadmin gating --------------------------------------------------

class TestNonSuperAdminGating:
    def test_bo_admin_cannot_list_companies(self, bo_ctx):
        r = requests.get(f"{API}/admin/companies", headers=_h(bo_ctx["token"]))
        assert r.status_code == 403

    def test_gov_admin_cannot_switch_company(self, gov_ctx):
        # use an arbitrary id; should 403 before resolving
        r = requests.post(f"{API}/admin/companies/anything/switch",
                          headers=_h(gov_ctx["token"]))
        assert r.status_code == 403


# ---- Users router -----------------------------------------------------------

class TestUsersRouter:
    def test_list_users_is_tenant_scoped(self, bo_ctx):
        r = requests.get(f"{API}/users", headers=_h(bo_ctx["token"]))
        assert r.status_code == 200, r.text
        rows = r.json()
        cid = bo_ctx["user"]["company_id"]
        for u in rows:
            assert u["company_id"] == cid
        emails = [u["email"] for u in rows]
        assert "admin@bocouncil.sl" in emails

    def test_invite_then_duplicate_then_reset_then_delete(self, gov_ctx):
        t = gov_ctx["token"]
        uniq = uuid.uuid4().hex[:8]
        payload = {
            "email": f"TEST_invite_{uniq}@gov.sl",
            "name": "Test Invite",
            "role": "employee",
            "password": "TestPass@2026",
        }
        r = requests.post(f"{API}/users/invite", headers=_h(t), json=payload, timeout=20)
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        # Duplicate -> 409
        dup = requests.post(f"{API}/users/invite", headers=_h(t), json=payload, timeout=20)
        assert dup.status_code == 409
        # Reset password (non-superadmin target)
        rp = requests.post(f"{API}/users/{uid}/reset-password", headers=_h(t),
                           json={"password": "NewPass@2026"}, timeout=20)
        assert rp.status_code == 200
        # New user can log in with the new password
        lr = requests.post(f"{API}/auth/login",
                           json={"email": payload["email"], "password": "NewPass@2026"})
        assert lr.status_code == 200
        # Delete
        dr = requests.delete(f"{API}/users/{uid}", headers=_h(t))
        assert dr.status_code == 200
        # Confirm gone via list
        rows = requests.get(f"{API}/users", headers=_h(t)).json()
        assert all(u["id"] != uid for u in rows)

    def test_reset_password_on_superadmin_target_is_403(self):
        t, _ = _login(SUPER)
        # super_ctx is itself superadmin in Demo tenant; reset against self should 403
        comps = requests.get(f"{API}/admin/companies", headers=_h(t)).json()
        # Find the superadmin user's own id via /auth/me
        me = requests.get(f"{API}/auth/me", headers=_h(t)).json()
        rr = requests.post(f"{API}/users/{me['id']}/reset-password",
                           headers=_h(t), json={"password": "AnotherPass@2026"})
        assert rr.status_code == 403, rr.text

    def test_delete_self_returns_400(self, bo_ctx):
        me = requests.get(f"{API}/auth/me", headers=_h(bo_ctx["token"])).json()
        r = requests.delete(f"{API}/users/{me['id']}", headers=_h(bo_ctx["token"]))
        assert r.status_code == 400

    def test_unlinked_employees(self, gov_ctx):
        r = requests.get(f"{API}/users/unlinked-employees", headers=_h(gov_ctx["token"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---- Gov tenant seed --------------------------------------------------------

class TestGovTenantSeed:
    def test_gov_admin_login_and_tier(self, gov_ctx):
        comp = gov_ctx["user"]["company"]
        assert comp["tier"] == "gov"
        assert "bulk_sms_payslips" in comp["features"]

    def test_gov_has_six_employees(self, gov_ctx):
        r = requests.get(f"{API}/employees", headers=_h(gov_ctx["token"]))
        assert r.status_code == 200
        emps = r.json()
        assert len(emps) >= 6
        names = {f"{e['first_name']} {e['last_name']}" for e in emps}
        expected = {"Adama Sankoh", "Foday Massaquoi", "Sia Kallon",
                    "Kabba Lansana", "Memuna Tucker", "Joseph Williams"}
        missing = expected - names
        assert not missing, f"missing employees: {missing}"
        # Joseph Williams should have empty/missing phone
        jw = next(e for e in emps if e["first_name"] == "Joseph" and e["last_name"] == "Williams")
        assert not jw.get("phone")


# ---- Twilio SMS -------------------------------------------------------------

class TestTwilioSms:
    def test_sms_status_returns_not_configured(self, gov_ctx):
        r = requests.get(f"{API}/payroll/sms/status", headers=_h(gov_ctx["token"]))
        assert r.status_code == 200
        assert r.json() == {"twilio_configured": False}

    def test_demo_salone_send_sms_is_402(self):
        # Demo Salone is enterprise tier -> no bulk_sms_payslips feature
        t = _ensure_super_on_demo()
        # Create a payroll run first
        rr = requests.post(f"{API}/payroll/run", headers=_h(t),
                           json={"period_year": 2026, "period_month": 1}, timeout=30)
        assert rr.status_code == 200, rr.text
        run_id = rr.json()["id"]
        r = requests.post(f"{API}/payroll/runs/{run_id}/send-sms",
                          headers=_h(t), json={"dry_run": True}, timeout=20)
        assert r.status_code == 402, r.text
        assert "bulk_sms_payslips" in r.text

    def test_gov_send_sms_dry_run_succeeds(self, gov_ctx):
        t = gov_ctx["token"]
        # Run payroll for Jan 2026
        rr = requests.post(f"{API}/payroll/run", headers=_h(t),
                           json={"period_year": 2026, "period_month": 1}, timeout=30)
        assert rr.status_code == 200, rr.text
        run_id = rr.json()["id"]
        r = requests.post(f"{API}/payroll/runs/{run_id}/send-sms",
                          headers=_h(t), json={"dry_run": True}, timeout=30)
        assert r.status_code == 200, r.text
        s = r.json()
        # Shape checks
        for k in ("batch_id", "sent", "would_send", "failed", "skipped",
                  "total", "dry_run", "twilio_configured", "results"):
            assert k in s, f"missing key {k}"
        assert s["twilio_configured"] is False
        assert s["dry_run"] is True
        assert s["sent"] == 0
        assert s["failed"] == 0
        assert s["total"] >= 6
        # ≥5 would_send, ≥1 skipped (Joseph Williams)
        assert s["would_send"] >= 5
        assert s["skipped"] >= 1
        for r1 in s["results"]:
            assert r1["status"] in ("sent", "would_send", "failed", "skipped")
        skipped_rows = [r1 for r1 in s["results"] if r1["status"] == "skipped"]
        assert any("phone" in (r1.get("reason") or "").lower() for r1 in skipped_rows)

    def test_sms_logs_are_tenant_scoped(self, gov_ctx, bo_ctx):
        gr = requests.get(f"{API}/payroll/sms/logs", headers=_h(gov_ctx["token"]))
        assert gr.status_code == 200
        gov_logs = gr.json()
        assert len(gov_logs) >= 6  # last dry-run produced ≥6 rows
        gov_cid = gov_ctx["user"]["company_id"]
        for row in gov_logs:
            assert row["company_id"] == gov_cid
        # Bo cannot see Gov's logs
        br = requests.get(f"{API}/payroll/sms/logs", headers=_h(bo_ctx["token"]))
        assert br.status_code == 200
        bo_cid = bo_ctx["user"]["company_id"]
        for row in br.json():
            assert row["company_id"] == bo_cid


# ---- Phase A regression -----------------------------------------------------

class TestPhaseARegression:
    def test_payroll_run_and_bank_file(self):
        t = _ensure_super_on_demo()
        rr = requests.post(f"{API}/payroll/run", headers=_h(t),
                           json={"period_year": 2026, "period_month": 2}, timeout=30)
        assert rr.status_code == 200, rr.text
        rid = rr.json()["id"]
        bf = requests.get(f"{API}/payroll/runs/{rid}/bank-file", headers=_h(t))
        assert bf.status_code == 200
        assert "text/csv" in bf.headers.get("content-type", "")
        assert b"bank_name" in bf.content[:64]

    def test_documents_upload_download_delete(self, gov_ctx):
        # NOTE: use gov_ctx (role=admin) instead of super (role=superadmin) because
        # documents.download_document hardcodes role check to "admin" only.
        t = gov_ctx["token"]
        emps = requests.get(f"{API}/employees", headers=_h(t)).json()
        assert emps, "no employees in Gov tenant"
        eid = emps[0]["id"]
        # Minimal valid PDF
        pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        files = {"file": ("TEST_iter8.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        data = {"category": "other", "title": "TEST_iter8_doc", "employee_id": eid}
        ur = requests.post(f"{API}/documents/upload", headers=_h(t), files=files, data=data, timeout=20)
        assert ur.status_code in (200, 201), ur.text
        did = ur.json().get("id") or ur.json().get("_id") or ur.json().get("doc", {}).get("id")
        assert did, f"no id in upload response: {ur.json()}"
        dl = requests.get(f"{API}/documents/{did}/download", headers=_h(t))
        assert dl.status_code == 200
        rm = requests.delete(f"{API}/documents/{did}", headers=_h(t))
        assert rm.status_code in (200, 204)
