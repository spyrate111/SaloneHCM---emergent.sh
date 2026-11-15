"""Public marketing landing-page lead capture endpoint."""
import os
import requests
from pymongo import MongoClient

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"


def test_lead_capture_creates_doc_in_db():
    payload = {
        "name": "Aminata Test",
        "email": f"lead_{os.urandom(2).hex()}@example.com",
        "company": "ACME Sierra Leone",
        "employees": 87,
        "message": "Tell me about the Civil Service module.",
    }
    r = requests.post(f"{API}/marketing/leads", json=payload)
    assert r.status_code == 201, r.text
    lead_id = r.json()["id"]
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "salonehcm_db")]
    doc = db.marketing_leads.find_one({"id": lead_id})
    assert doc is not None
    assert doc["email"] == payload["email"]
    assert doc["company"] == payload["company"]
    assert doc["status"] == "new"
    assert doc["source"] == "landing_page"
    db.marketing_leads.delete_one({"id": lead_id})


def test_lead_capture_rejects_invalid_email():
    r = requests.post(f"{API}/marketing/leads", json={
        "name": "Test", "email": "not-an-email", "company": "x", "employees": 5,
    })
    assert r.status_code == 422


def test_lead_capture_rejects_zero_employees():
    r = requests.post(f"{API}/marketing/leads", json={
        "name": "Test", "email": "t@example.com", "company": "x", "employees": 0,
    })
    assert r.status_code == 422


def test_lead_capture_is_public_no_auth_required():
    """Endpoint must not require any auth — no Bearer, no cookie."""
    r = requests.post(f"{API}/marketing/leads", json={
        "name": "Pub Test", "email": f"pub_{os.urandom(2).hex()}@example.com",
        "company": "Pub Co", "employees": 1,
    })
    assert r.status_code == 201
