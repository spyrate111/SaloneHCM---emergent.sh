"""Verify the dual-auth (cookie + Bearer) + CSRF implementation."""
import os
import requests

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"
GOV_EMAIL = "admin@gov.sl"
GOV_PASS = "GovAdmin@2026"


def _login() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS})
    assert r.status_code == 200, r.text
    return s


def test_login_sets_session_and_csrf_cookies():
    """Login response sets httpOnly access_token + non-httpOnly csrf cookies and returns csrf_token in JSON."""
    r = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body
    assert "csrf_token" in body and len(body["csrf_token"]) >= 30
    cookies_raw = r.raw.headers.getlist("Set-Cookie") if hasattr(r.raw.headers, "getlist") else [v for k, v in r.raw.headers.items() if k.lower() == "set-cookie"]
    names = {c.split("=")[0] for c in cookies_raw}
    assert "access_token" in names
    assert "salonehcm_csrf" in names
    access = next(c for c in cookies_raw if c.startswith("access_token="))
    assert "HttpOnly" in access, "access_token cookie must be HttpOnly"
    csrf = next(c for c in cookies_raw if c.startswith("salonehcm_csrf="))
    assert "HttpOnly" not in csrf, "csrf cookie must be readable by JS"


def test_cookie_auth_works_for_get():
    """A GET authenticated by cookie alone (no Authorization header) succeeds."""
    s = _login()
    s.headers.pop("Authorization", None)
    r = s.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == GOV_EMAIL


def test_csrf_blocks_state_change_when_cookie_authed():
    """Cookie-auth POST without X-CSRF-Token must return 403."""
    s = _login()
    s.headers.pop("Authorization", None)
    r = s.post(f"{API}/auth/logout")
    assert r.status_code == 403, f"expected 403 got {r.status_code}"
    assert "csrf" in r.text.lower()


def test_csrf_allows_state_change_when_header_matches_cookie():
    """Cookie-auth POST with matching X-CSRF-Token succeeds."""
    s = _login()
    s.headers.pop("Authorization", None)
    csrf = s.cookies.get("salonehcm_csrf")
    assert csrf, "csrf cookie not stored on session"
    r = s.post(f"{API}/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200, r.text


def test_bearer_header_bypasses_csrf():
    """API clients with Authorization: Bearer header skip CSRF — backwards compat for tests + CLIs."""
    login = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS})
    token = login.json()["token"]
    # Fresh client → no cookies.
    r = requests.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text


def test_logout_clears_both_cookies():
    s = _login()
    s.headers.pop("Authorization", None)
    csrf = s.cookies.get("salonehcm_csrf")
    r = s.post(f"{API}/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    cookies_raw = r.raw.headers.getlist("Set-Cookie") if hasattr(r.raw.headers, "getlist") else []
    # delete_cookie emits Set-Cookie with Max-Age=0 or expires in 1970
    deleted = [c for c in cookies_raw if "Max-Age=0" in c or "max-age=0" in c.lower() or "1970" in c]
    names = {c.split("=")[0] for c in deleted}
    assert "access_token" in names
    assert "salonehcm_csrf" in names


def test_mixed_auth_prefers_authorization_header():
    """When both cookie + Authorization header are present, the header wins (no CSRF needed)."""
    s = _login()
    token = s.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]
    # Cookie-auth would require CSRF; passing Authorization header should bypass that requirement.
    r = s.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
