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


# Known gov budget codes (from seeders/civil_service.py). Used to auto-seed
# generous allocations during tests so the anti-fraud budget check passes.
_GOV_BUDGET_CODES = [
    "110.01.001", "110.02.001", "110.02.002",
    "120.01.001", "310.01.001", "310.01.002",
]


def _auto_satisfy_budget_check(url: str, *args, **kwargs):
    """When a test POSTs /payroll/run and the guardrail returns 412
    budget_check_missing, transparently seed allocations + run the check and
    retry once. Prod behaviour unchanged — only monkey-patched in test context."""
    try:
        base_url = url[: url.rfind("/api/")] + "/api" if "/api/" in url else url
        body = kwargs.get("json") or {}
        year = body.get("period_year")
        month = body.get("period_month")
        if not (year and month):
            return None
        period = f"{year}-{int(month):02d}"
        auth = kwargs.get("headers", {}).get("Authorization")
        if not auth:
            return None
        h = {"Authorization": auth, "Content-Type": "application/json"}
        for code in _GOV_BUDGET_CODES:
            _orig_post(f"{base_url}/payroll-budget/balances/{code}",
                       json={"allocated_sle": 100_000_000, "period": period},
                       headers=h, timeout=15).close() if False else \
                requests.request("PUT", f"{base_url}/payroll-budget/balances/{code}",
                                 json={"allocated_sle": 100_000_000, "period": period},
                                 headers=h, timeout=15)
        _orig_post(f"{base_url}/payroll-budget/check",
                   json={"period": period}, headers=h, timeout=15)
        return _orig_post(url, *args, **kwargs)
    except Exception:
        return None


def _patched_post(url, *args, **kwargs):
    """Auto-inject totp_code when logging in as the seed superadmin, and
    auto-satisfy Gov pre-payroll budget check on /payroll/run in tests."""
    try:
        if isinstance(url, str) and url.endswith("/auth/login"):
            json_body = kwargs.get("json")
            if isinstance(json_body, dict) and (json_body.get("email", "").lower() == SUPERADMIN_EMAIL) and "totp_code" not in json_body:
                json_body = {**json_body, "totp_code": totp_now()}
                kwargs["json"] = json_body
    except Exception:
        pass
    resp = _orig_post(url, *args, **kwargs)
    try:
        if (isinstance(url, str) and url.endswith("/payroll/run")
                and resp.status_code == 412
                # Never auto-satisfy inside the iter29 suite — those tests
                # explicitly validate the guardrail's blocked responses.
                and "test_iter29_budget_check" not in os.environ.get("PYTEST_CURRENT_TEST", "")):
            body = resp.json() if resp.content else {}
            detail = body.get("detail") if isinstance(body, dict) else None
            if isinstance(detail, dict) and detail.get("code") == "budget_check_missing":
                retried = _auto_satisfy_budget_check(url, *args, **kwargs)
                if retried is not None:
                    return retried
    except Exception:
        pass
    return resp


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
        # Belt-and-braces: also resync every company's features to its tier.
        # Some test suites (iter19 billing) historically mutated `tier` without
        # re-deriving `features`, breaking tier-gated routes for later modules.
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from tiers import features_for, tier_label
        for comp in c.companies.find({}, {"_id": 0, "id": 1, "tier": 1, "features": 1}):
            expected = features_for(comp.get("tier", "lite"))
            if set(comp.get("features") or []) != set(expected):
                c.companies.update_one(
                    {"id": comp["id"]},
                    {"$set": {"features": expected, "label": tier_label(comp.get("tier", "lite"))}},
                )
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
