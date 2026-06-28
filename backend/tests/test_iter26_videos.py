"""Marketing video library endpoints — public read + superadmin CRUD."""
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


def _payload(**overrides):
    base = {
        "title": "Test walkthrough",
        "summary": "A short test of the marketing video API endpoint.",
        "src": "https://example.com/video.mp4",
        "poster": "https://example.com/poster.jpg",
        "duration_s": 60,
        "category": "getting_started",
        "persona": "small_business",
        "chapters": [{"t": 0, "label": "Intro"}, {"t": 30, "label": "Setup"}],
        "sort": 100,
        "published": True,
    }
    base.update(overrides)
    return base


def test_list_videos_is_public_returns_seeded():
    r = requests.get(f"{API}/marketing/videos")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 9  # seeded videos
    # Every item must have the standard fields
    for v in body:
        for k in ("id", "title", "src", "duration_s", "category", "persona"):
            assert k in v
        assert "_id" not in v  # ObjectId must be stripped


def test_list_videos_filter_by_category():
    r = requests.get(f"{API}/marketing/videos?category=getting_started")
    assert r.status_code == 200
    body = r.json()
    assert all(v["category"] == "getting_started" for v in body)
    assert len(body) >= 1


def test_list_videos_filter_by_persona():
    r = requests.get(f"{API}/marketing/videos?persona=government")
    assert r.status_code == 200
    body = r.json()
    assert all(v["persona"] == "government" for v in body)


def test_get_single_video_404():
    r = requests.get(f"{API}/marketing/videos/no-such-id")
    assert r.status_code == 404


def test_create_video_requires_superadmin(gov_h):
    r = requests.post(f"{API}/marketing/admin/videos", headers=gov_h, json=_payload())
    assert r.status_code == 403


def test_create_video_unauthenticated_rejected():
    r = requests.post(f"{API}/marketing/admin/videos", json=_payload())
    assert r.status_code in (401, 403)


def test_create_video_validates_category(super_h):
    r = requests.post(f"{API}/marketing/admin/videos", headers=super_h, json=_payload(category="cooking_show"))
    assert r.status_code == 422


def test_create_video_validates_persona(super_h):
    r = requests.post(f"{API}/marketing/admin/videos", headers=super_h, json=_payload(persona="aliens"))
    assert r.status_code == 422


def test_video_crud_lifecycle(super_h):
    payload = _payload(title="QA lifecycle test")
    r = requests.post(f"{API}/marketing/admin/videos", headers=super_h, json=payload)
    assert r.status_code == 201, r.text
    vid = r.json()["id"]
    try:
        # GET single
        g = requests.get(f"{API}/marketing/videos/{vid}")
        assert g.status_code == 200
        assert g.json()["title"] == "QA lifecycle test"
        # PATCH
        payload["title"] = "QA lifecycle test [edited]"
        u = requests.patch(f"{API}/marketing/admin/videos/{vid}", headers=super_h, json=payload)
        assert u.status_code == 200
        assert u.json()["title"].endswith("[edited]")
        # admin list shows it
        a = requests.get(f"{API}/marketing/admin/videos", headers=super_h)
        assert any(v["id"] == vid for v in a.json())
        # DELETE
        d = requests.delete(f"{API}/marketing/admin/videos/{vid}", headers=super_h)
        assert d.status_code == 204
        # Now 404
        g2 = requests.get(f"{API}/marketing/videos/{vid}")
        assert g2.status_code == 404
    finally:
        _db().marketing_videos.delete_one({"id": vid})


def test_unpublished_video_hidden_from_public(super_h):
    payload = _payload(title="QA hidden draft", published=False)
    r = requests.post(f"{API}/marketing/admin/videos", headers=super_h, json=payload)
    assert r.status_code == 201
    vid = r.json()["id"]
    try:
        # Public list doesn't see it
        pub = requests.get(f"{API}/marketing/videos").json()
        assert not any(v["id"] == vid for v in pub)
        # Public single-get returns 404 (we filter by published=True)
        single = requests.get(f"{API}/marketing/videos/{vid}")
        assert single.status_code == 404
        # Admin list still sees it
        ad = requests.get(f"{API}/marketing/admin/videos", headers=super_h).json()
        assert any(v["id"] == vid for v in ad)
    finally:
        requests.delete(f"{API}/marketing/admin/videos/{vid}", headers=super_h)
        _db().marketing_videos.delete_one({"id": vid})
