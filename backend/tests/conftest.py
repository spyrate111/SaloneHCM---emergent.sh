"""Shared pytest helpers — auto-injects TOTP code for the seed superadmin so
the existing test suites keep working under strict 2FA enforcement."""
import os
import pyotp
import pytest
import requests

# Read the same secret used by the seeder. Falls back to the known dev-only
# default so contributor laptops Just Work without extra env setup; production
# CI must inject its own SUPERADMIN_TOTP_SECRET.
SUPERADMIN_TOTP_SECRET = os.environ.get(
    "SUPERADMIN_TOTP_SECRET",
    "KRSXG5BANFXSAYTBORQXG43LMR2A",
)
SUPERADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@salonehcm.sl").lower()


def totp_now() -> str:
    return pyotp.TOTP(SUPERADMIN_TOTP_SECRET).now()


_orig_post = requests.post


def _patched_post(url, *args, **kwargs):
    """Auto-inject totp_code when logging in as the seed superadmin."""
    try:
        if isinstance(url, str) and url.endswith("/auth/login"):
            json_body = kwargs.get("json")
            if isinstance(json_body, dict) and (json_body.get("email", "").lower() == SUPERADMIN_EMAIL) and "totp_code" not in json_body:
                json_body = {**json_body, "totp_code": totp_now()}
                kwargs["json"] = json_body
    except Exception:
        pass
    return _orig_post(url, *args, **kwargs)


# Install once for the whole pytest session
requests.post = _patched_post


# ---- Restore superadmin to Demo Salone tenant before tests run ----
# The /admin/companies/{cid}/switch endpoint mutates the superadmin's company_id,
# which can leak between test sessions. Legacy tests (iter5..iter9, salonehcm)
# assume the superadmin is on Demo Salone, so we restore that pin once at module
# import time before any test fixture runs.
def _restore_superadmin_tenant() -> None:
    """Restore the canonical superadmin state before each test session/module:

      * company_id pinned to Demo Salone (Switcher leaks between modules otherwise)
      * 2FA enabled with the well-known SUPERADMIN_TOTP_SECRET so the auto-injecting
        login patch upstream and any test that asserts twofa_enabled=True works.
    """
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "salonehcm_db")
        c = MongoClient(mongo_url, serverSelectionTimeoutMS=2000)[db_name]
        demo = c.companies.find_one({"name": "Demo Salone Ltd."}, {"_id": 0, "id": 1})
        update = {
            "$set": {
                "twofa_enabled": True,
                "twofa_secret": SUPERADMIN_TOTP_SECRET,
            },
            "$unset": {"twofa_pending_secret": ""},
        }
        if demo:
            update["$set"]["company_id"] = demo["id"]
        c.users.update_one({"email": SUPERADMIN_EMAIL}, update)
    except Exception:
        # Don't block tests if Mongo isn't reachable from the test host —
        # only the multi-tenant scoped tests will fail explicitly in that case.
        pass


_restore_superadmin_tenant()


# Re-run the restore as a module-scoped autouse fixture too — pytest invokes
# this once per test module, BEFORE any module fixtures resolve. This protects
# against /admin/companies/{cid}/switch leaks between test modules.
@pytest.fixture(scope="module", autouse=True)
def _reset_superadmin_tenant_per_module():
    _restore_superadmin_tenant()
    yield
