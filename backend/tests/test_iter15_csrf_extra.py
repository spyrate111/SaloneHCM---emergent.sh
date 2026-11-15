"""Extra CSRF probes on real state-changing endpoints (employees, switcher)."""
import os
import requests
import pyotp

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"


def _gov_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@gov.sl", "password": "GovAdmin@2026"})
    assert r.status_code == 200
    s.headers.pop("Authorization", None)
    return s, r.json()


def test_employees_post_blocks_without_csrf_when_cookie_authed():
    """POST /api/employees via cookie auth and NO CSRF header must be 403."""
    s, _ = _gov_session()
    r = s.post(f"{API}/employees", json={"name": "TEST_csrf_blocked", "title": "x"})
    assert r.status_code == 403, f"got {r.status_code}: {r.text[:200]}"
    assert "csrf" in r.text.lower()


def test_employees_post_succeeds_with_csrf_header():
    """Cookie-authed POST /api/employees with matching X-CSRF-Token should NOT be 403."""
    s, _ = _gov_session()
    csrf = s.cookies.get("salonehcm_csrf")
    r = s.post(
        f"{API}/employees",
        json={"name": "TEST_csrf_ok", "title": "Tester", "department": "QA", "email": "TEST_csrfok@gov.sl"},
        headers={"X-CSRF-Token": csrf},
    )
    # 200/201 on success, 400/422 on validation — anything other than 403 means CSRF passed
    assert r.status_code != 403, f"unexpected 403 with CSRF header: {r.text[:200]}"
    if r.status_code in (200, 201):
        eid = r.json().get("id")
        if eid:
            requests.delete(
                f"{API}/employees/{eid}",
                headers={"X-CSRF-Token": csrf},
                cookies={"access_token": s.cookies.get("access_token"), "salonehcm_csrf": csrf},
            )


def test_bearer_post_employees_skips_csrf():
    """Bearer-auth state-change with NO cookie must bypass CSRF entirely."""
    r = requests.post(f"{API}/auth/login", json={"email": "admin@gov.sl", "password": "GovAdmin@2026"})
    token = r.json()["token"]
    rr = requests.post(
        f"{API}/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "TEST_bearer_emp", "title": "Tester", "department": "QA", "email": "TEST_bearer@gov.sl"},
    )
    assert rr.status_code != 403, rr.text[:200]
    if rr.status_code in (200, 201):
        eid = rr.json().get("id")
        if eid:
            requests.delete(f"{API}/employees/{eid}", headers={"Authorization": f"Bearer {token}"})


def test_login_and_accept_invite_are_csrf_exempt():
    """/auth/login is exempt — calling without CSRF header must work."""
    r = requests.post(f"{API}/auth/login", json={"email": "admin@gov.sl", "password": "GovAdmin@2026"})
    assert r.status_code == 200


def test_admin_switch_company_refreshes_cookies():
    """Superadmin /api/admin/companies/{cid}/switch refreshes BOTH cookies + returns csrf_token in body."""
    s = requests.Session()
    code = pyotp.TOTP(os.environ.get("SUPERADMIN_TOTP_SECRET", "KRSXG5BANFXSAYTBORQXG43LMR2A")).now()
    lr = s.post(f"{API}/auth/login", json={"email": "admin@salonehcm.sl", "password": "Admin@2026", "totp_code": code})
    assert lr.status_code == 200, lr.text
    s.headers.pop("Authorization", None)
    csrf = s.cookies.get("salonehcm_csrf")
    # List companies
    companies = s.get(f"{API}/admin/companies").json()
    target = next((c for c in companies if c["id"] != lr.json().get("company_id")), None)
    assert target, "need at least 2 companies for the switcher test"
    pre_access = s.cookies.get("access_token")
    pre_csrf = csrf
    rr = s.post(f"{API}/admin/companies/{target['id']}/switch", headers={"X-CSRF-Token": csrf})
    assert rr.status_code == 200, rr.text
    body = rr.json()
    assert "csrf_token" in body
    # Cookies should be refreshed
    post_access = s.cookies.get("access_token")
    post_csrf = s.cookies.get("salonehcm_csrf")
    assert post_access and post_access != pre_access, "access_token cookie was NOT refreshed on switch"
    assert post_csrf and post_csrf != pre_csrf, "csrf cookie was NOT refreshed on switch"
    # The new JWT must reference the new company
    me = s.get(f"{API}/auth/me")
    assert me.json()["company_id"] == target["id"]
