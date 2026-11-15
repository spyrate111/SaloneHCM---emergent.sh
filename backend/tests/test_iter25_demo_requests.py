"""Public marketing demo-request wizard endpoint (no auth)."""
import os
import requests
from pymongo import MongoClient

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"


def _db():
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "salonehcm_db")
    ]


def _payload(**overrides):
    base = {
        "name": "Aminata Demo",
        "email": f"demo_{os.urandom(2).hex()}@example.com",
        "phone": "+23230111222",
        "company": "Freetown Logistics",
        "industry": "banking",
        "size": "50-249",
        "topics": ["payroll", "compliance"],
        "message": "We need to switch off our manual ledger.",
    }
    base.update(overrides)
    return base


def test_demo_request_happy_path_persists():
    body = _payload()
    r = requests.post(f"{API}/marketing/demo-requests", json=body)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    doc = _db().marketing_demo_requests.find_one({"id": rid})
    assert doc is not None
    assert doc["email"] == body["email"]
    assert doc["company"] == body["company"]
    assert doc["industry"] == "banking"
    assert doc["size"] == "50-249"
    assert sorted(doc["topics"]) == ["compliance", "payroll"]
    assert doc["source"] == "demo_wizard"
    assert doc["status"] == "new"
    _db().marketing_demo_requests.delete_one({"id": rid})


def test_demo_request_phone_optional():
    body = _payload()
    body.pop("phone")
    r = requests.post(f"{API}/marketing/demo-requests", json=body)
    assert r.status_code == 201
    rid = r.json()["id"]
    doc = _db().marketing_demo_requests.find_one({"id": rid})
    assert doc["phone"] is None
    _db().marketing_demo_requests.delete_one({"id": rid})


def test_demo_request_rejects_invalid_industry():
    r = requests.post(f"{API}/marketing/demo-requests", json=_payload(industry="rocket-science"))
    assert r.status_code == 422


def test_demo_request_rejects_invalid_size():
    r = requests.post(f"{API}/marketing/demo-requests", json=_payload(size="huge"))
    assert r.status_code == 422


def test_demo_request_rejects_invalid_topic():
    r = requests.post(f"{API}/marketing/demo-requests", json=_payload(topics=["payroll", "yoga"]))
    assert r.status_code == 422


def test_demo_request_requires_at_least_one_topic():
    r = requests.post(f"{API}/marketing/demo-requests", json=_payload(topics=[]))
    assert r.status_code == 422


def test_demo_request_is_public_no_auth_required():
    r = requests.post(f"{API}/marketing/demo-requests", json=_payload())
    assert r.status_code == 201
    _db().marketing_demo_requests.delete_one({"id": r.json()["id"]})
