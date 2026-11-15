"""Verify the startup feature-resync migration prevents `company.features` drift.

Scenario: any path (admin override, test fixture) that mutates `company.tier`
without re-deriving `company.features` historically caused 402 errors for
tier-gated routes. We now resync on every boot. This test simulates the
drift and verifies the next API call works.
"""
import os
import pytest
import requests
from pymongo import MongoClient

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"
GOV_EMAIL = "admin@gov.sl"
GOV_PASS = "GovAdmin@2026"


def _db():
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "salonehcm_db")
    ]


@pytest.fixture
def gov_h():
    tok = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_gov_features_array_matches_tier_after_boot(gov_h):
    """After every backend boot, Gov tenant features must include all gov-tier flags."""
    c = _db().companies.find_one({"name": "Government of Sierra Leone"})
    assert c["tier"] == "gov"
    must_have = {
        "civil_service", "gov_payroll", "ministry_reports",
        "bulk_sms_payslips", "nra_export", "mof_approval", "ghost_worker_detection",
        "ifmis_integration", "establishment_control", "loans_advances", "sector_presets",
    }
    have = set(c.get("features") or [])
    missing = must_have - have
    assert not missing, f"Gov tenant missing tier features after boot: {missing}"


def test_resync_function_corrects_drift():
    """Programmatic test: simulate drift, run resync, verify correction.

    The resync runs in a subprocess so we get a clean Motor client bound to a
    fresh event loop — required because prior async tests in the suite can
    close the module-level loop that `core.client` is bound to.
    """
    import subprocess

    db_sync = _db()
    gov = db_sync.companies.find_one({"name": "Government of Sierra Leone"})
    original = list(gov.get("features", []))

    # Simulate drift: strip out civil_service
    db_sync.companies.update_one(
        {"id": gov["id"]},
        {"$set": {"features": [f for f in original if f != "civil_service"]}},
    )
    drifted = db_sync.companies.find_one({"id": gov["id"]})
    assert "civil_service" not in drifted["features"]

    # Run resync in a subprocess with a clean interpreter/event-loop.
    result = subprocess.run(
        ["python", "-c",
         "import asyncio; from seeders import _resync_all_company_features; "
         "asyncio.run(_resync_all_company_features())"],
        cwd="/app/backend", capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"resync subprocess failed: {result.stderr}"

    # Verify drift is corrected
    fixed = db_sync.companies.find_one({"id": gov["id"]})
    assert "civil_service" in fixed["features"], "resync must restore civil_service"
    # And the api should now work
    tok = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]
    r = requests.get(f"{API}/promotion/eligible", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
