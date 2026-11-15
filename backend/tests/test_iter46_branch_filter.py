"""iter46 — punch map branch filter (managers multi-branch, hr/admin all)."""
import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]


def _login(email, password):
    for _ in range(6):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
        if r.status_code != 429:
            break
        time.sleep(5)
    r.raise_for_status()
    return r.json()


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def env():
    """Two branches supervised by manager1, one unsupervised, plus punches today."""
    mgr = _login("manager1@salonehcm.com", "Test@Manager1")
    mgr_user = _db.users.find_one({"email": "manager1@salonehcm.com"})
    cid = mgr["company_id"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).isoformat()
    b1, b2, b3 = (str(uuid.uuid4()) for _ in range(3))
    _db.branches.insert_many([
        {"id": b1, "company_id": cid, "code": "IT46A", "name": "Iter46 East",
         "lat": 8.48, "lng": -13.23, "geofence_radius_m": 150,
         "supervisor_user_id": mgr_user["id"]},
        {"id": b2, "company_id": cid, "code": "IT46B", "name": "Iter46 West",
         "lat": 8.46, "lng": -13.25, "geofence_radius_m": 150,
         "supervisor_user_id": mgr_user["id"]},
        {"id": b3, "company_id": cid, "code": "IT46C", "name": "Iter46 Other",
         "lat": 8.40, "lng": -13.20, "geofence_radius_m": 150,
         "supervisor_user_id": "someone-else"},
    ])
    punches = []
    for bid, lat, lng, n in ((b1, 8.48, -13.23, 2), (b2, 8.46, -13.25, 3), (b3, 8.40, -13.20, 1)):
        for i in range(n):
            punches.append({"id": str(uuid.uuid4()), "company_id": cid,
                            "employee_id": f"e-{bid[:4]}-{i}",
                            "employee_name": f"Iter46 Emp {bid[:4]}{i}",
                            "kind": "in", "date": today, "clocked_at": now,
                            "lat": lat, "lng": lng, "branch_id": bid})
    _db.attendance.insert_many(punches)
    yield {"mgr": mgr, "b1": b1, "b2": b2, "b3": b3, "cid": cid}
    _db.branches.delete_many({"id": {"$in": [b1, b2, b3]}})
    _db.attendance.delete_many({"employee_name": {"$regex": "^Iter46 Emp"}})


class TestBranchFilter:
    def test_manager_sees_only_supervised_branches(self, env):
        r = requests.get(f"{API}/mobile/punch/team", headers=_h(env["mgr"]["token"]), timeout=15)
        assert r.status_code == 200
        ids = {b["id"] for b in r.json()["branches"]}
        assert env["b1"] in ids and env["b2"] in ids and env["b3"] not in ids
        assert len([p for p in r.json()["punches"]
                    if p["employee_name"].startswith("Iter46")]) == 5

    def test_manager_filters_single_branch(self, env):
        r = requests.get(f"{API}/mobile/punch/team",
                         params={"branch_id": env["b2"]},
                         headers=_h(env["mgr"]["token"]), timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert [b["id"] for b in body["branches"]] == [env["b2"]]
        mine = [p for p in body["punches"] if p["employee_name"].startswith("Iter46")]
        assert len(mine) == 3 and all(p["branch_id"] == env["b2"] for p in mine)
        assert body["stats"]["total"] == len(body["punches"])

    def test_manager_blocked_from_foreign_branch(self, env):
        r = requests.get(f"{API}/mobile/punch/team",
                         params={"branch_id": env["b3"]},
                         headers=_h(env["mgr"]["token"]), timeout=15)
        assert r.status_code == 404

    def test_hr_sees_all_and_can_filter(self, env):
        hr = _login("hradmin1@salonehcm.com", "Test@HRAdmin1")
        r = requests.get(f"{API}/mobile/punch/team", headers=_h(hr["token"]), timeout=15)
        ids = {b["id"] for b in r.json()["branches"]}
        assert {env["b1"], env["b2"], env["b3"]} <= ids
        r2 = requests.get(f"{API}/mobile/punch/team",
                          params={"branch_id": env["b3"]}, headers=_h(hr["token"]), timeout=15)
        assert r2.status_code == 200
        mine = [p for p in r2.json()["punches"] if p["employee_name"].startswith("Iter46")]
        assert len(mine) == 1 and mine[0]["branch_id"] == env["b3"]

    def test_superadmin_filter(self, env):
        sa = _login("superadmin1@salonehcm.com", "Test@SuperAdmin1")
        r = requests.get(f"{API}/mobile/punch/team",
                         params={"branch_id": env["b1"]}, headers=_h(sa["token"]), timeout=15)
        assert r.status_code == 200
        mine = [p for p in r.json()["punches"] if p["employee_name"].startswith("Iter46")]
        assert len(mine) == 2

    def test_csv_respects_branch_filter(self, env):
        r = requests.get(f"{API}/mobile/punch/team.csv",
                         params={"branch_id": env["b1"]},
                         headers=_h(env["mgr"]["token"]), timeout=15)
        assert r.status_code == 200
        body = r.text
        assert "Iter46 East" in body and "Iter46 West" not in body
