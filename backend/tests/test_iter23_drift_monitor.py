"""Tier-features drift monitor endpoints — superadmin only."""
import os
import pyotp
import pytest
import requests
from pymongo import MongoClient

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"
SUPER_EMAIL = "admin@salonehcm.sl"
SUPER_PASS = "Admin@2026"
SUPER_SECRET = os.environ.get("SUPERADMIN_TOTP_SECRET", "KRSXG5BANFXSAYTBORQXG43LMR2A")
GOV_EMAIL = "admin@gov.sl"
GOV_PASS = "GovAdmin@2026"


def _db():
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "salonehcm_db")
    ]


@pytest.fixture
def super_h():
    r = requests.post(f"{API}/auth/login", json={
        "email": SUPER_EMAIL, "password": SUPER_PASS,
        "totp_code": pyotp.TOTP(SUPER_SECRET).now(),
    })
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def gov_h():
    r = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_drift_check_clean_state(super_h):
    """In a clean DB state, drift-check returns ok=true and drifted_count=0."""
    r = requests.get(f"{API}/admin/companies/drift-check", headers=super_h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["drifted_count"] == 0
    assert body["total_companies"] >= 2  # demo + gov
    assert body["drifted"] == []


def test_drift_check_requires_superadmin(gov_h):
    """Gov-tenant admin (not super-admin) is forbidden."""
    r = requests.get(f"{API}/admin/companies/drift-check", headers=gov_h)
    assert r.status_code == 403


def test_drift_check_detects_and_resync_fixes(super_h):
    """Simulate drift, verify endpoint reports it, then resync and verify fixed."""
    db = _db()
    gov = db.companies.find_one({"name": "Government of Sierra Leone"})
    original_features = list(gov.get("features", []))
    try:
        # Inject drift: strip 'civil_service' from Gov tenant
        broken = [f for f in original_features if f != "civil_service"]
        db.companies.update_one({"id": gov["id"]}, {"$set": {"features": broken}})
        # Drift check should now report drift
        r = requests.get(f"{API}/admin/companies/drift-check", headers=super_h)
        body = r.json()
        assert body["ok"] is False
        assert body["drifted_count"] == 1
        drifted = body["drifted"][0]
        assert drifted["id"] == gov["id"]
        assert "civil_service" in drifted["missing"]
        assert drifted["extra"] == []
        # Now resync
        r2 = requests.post(f"{API}/admin/companies/drift-resync", headers=super_h)
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["ok"] is True
        assert body2["fixed_count"] == 1
        assert body2["fixed"][0]["id"] == gov["id"]
        # Drift check after resync = clean
        r3 = requests.get(f"{API}/admin/companies/drift-check", headers=super_h).json()
        assert r3["ok"] is True
        assert r3["drifted_count"] == 0
        # Endpoint that uses civil_service feature now works
        gov_tok = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]
        r4 = requests.get(f"{API}/promotion/eligible", headers={"Authorization": f"Bearer {gov_tok}"})
        assert r4.status_code == 200, f"expected 200 after resync, got {r4.status_code}"
    finally:
        # Cleanup: restore original features
        db.companies.update_one({"id": gov["id"]}, {"$set": {"features": original_features}})


def test_drift_resync_with_no_drift_returns_zero(super_h):
    """If no drift exists, resync returns fixed_count=0 — safe to call repeatedly."""
    r = requests.post(f"{API}/admin/companies/drift-resync", headers=super_h)
    assert r.status_code == 200
    assert r.json()["fixed_count"] == 0
