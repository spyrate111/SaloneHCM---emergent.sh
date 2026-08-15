"""iter35 — Team punch map + branch geofencing.

Verifies:
- Branches carry lat/lng + geofence_radius_m (seed backfill)
- GET /mobile/punch/team: admin sees all tenant branches; plain employees 403
- in_zone computed from branch geofence (fallback 250m)
- Branch PATCH accepts geofence_radius_m and lat/lng, validates bounds
- GET /mobile/punch/team.csv streams a CSV with a zone column
"""
import os
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")

_db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
    os.environ.get("DB_NAME", "salonehcm_db")
]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def gov_admin():
    return _login("admin@gov.sl", "GovAdmin@2026")


@pytest.fixture(scope="module")
def adama():
    # MOF-HQ branch supervisor with an employee record — used for punches.
    return _login("adama.sankoh@gov.sl", "Employee@2026")


class TestBranchGeofence:
    def test_seeded_branches_have_coords(self, gov_admin):
        r = requests.get(f"{API}/branches", headers=_h(gov_admin["token"]), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) >= 3
        for b in rows:
            assert b.get("lat") is not None, f"{b['code']} missing lat"
            assert b.get("lng") is not None
            assert b.get("geofence_radius_m")

    def test_patch_geofence_radius(self, gov_admin):
        r = requests.get(f"{API}/branches", headers=_h(gov_admin["token"]), timeout=15)
        b = r.json()[0]
        try:
            p = requests.patch(f"{API}/branches/{b['id']}", headers=_h(gov_admin["token"]),
                               json={"geofence_radius_m": 500.0}, timeout=15)
            assert p.status_code == 200
            assert p.json()["geofence_radius_m"] == 500.0
        finally:
            requests.patch(f"{API}/branches/{b['id']}", headers=_h(gov_admin["token"]),
                           json={"geofence_radius_m": b.get("geofence_radius_m") or 250.0}, timeout=15)

    def test_patch_geofence_out_of_bounds_422(self, gov_admin):
        r = requests.get(f"{API}/branches", headers=_h(gov_admin["token"]), timeout=15)
        b = r.json()[0]
        p = requests.patch(f"{API}/branches/{b['id']}", headers=_h(gov_admin["token"]),
                           json={"geofence_radius_m": 5.0}, timeout=15)
        assert p.status_code == 422
        p2 = requests.patch(f"{API}/branches/{b['id']}", headers=_h(gov_admin["token"]),
                            json={"lat": 95.0}, timeout=15)
        assert p2.status_code == 422


class TestTeamMap:
    def test_admin_sees_team_map(self, gov_admin):
        r = requests.get(f"{API}/mobile/punch/team", headers=_h(gov_admin["token"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(d.keys()) == {"date", "branches", "punches", "stats"}
        assert len(d["branches"]) >= 3
        assert set(d["stats"].keys()) == {"total", "in_zone", "out_zone", "no_gps"}

    def test_plain_employee_403(self, gov_admin):
        """A user who is neither admin nor any branch's supervisor must be rejected."""
        company_id = gov_admin["company_id"]
        sup_ids = {b.get("supervisor_user_id")
                   for b in _db.branches.find({"company_id": company_id})}
        candidate = _db.users.find_one({
            "company_id": company_id, "role": "employee",
            "id": {"$nin": list(filter(None, sup_ids))},
        })
        if not candidate:
            pytest.skip("no non-supervisor employee available on gov tenant")
        tok = _login(candidate["email"], "Employee@2026")["token"]
        r = requests.get(f"{API}/mobile/punch/team", headers=_h(tok), timeout=15)
        assert r.status_code == 403

    def test_in_and_out_zone_computation(self, gov_admin, adama):
        tok = adama["token"]
        eid = adama["employee_id"]
        emp = _db.employees.find_one({"id": eid})
        branch = _db.branches.find_one({"id": emp["branch_id"]})
        assert branch and branch.get("lat") is not None
        created = []
        try:
            # in-zone punch: exactly at the branch
            r1 = requests.post(f"{API}/mobile/punch", headers=_h(tok), json={
                "kind": "in", "lat": branch["lat"], "lng": branch["lng"], "accuracy_m": 5,
            }, timeout=15)
            assert r1.status_code == 200, r1.text
            created.append(r1.json()["id"])
            # out-of-zone punch: ~11km north (0.1 deg lat)
            r2 = requests.post(f"{API}/mobile/punch", headers=_h(tok), json={
                "kind": "out", "lat": branch["lat"] + 0.1, "lng": branch["lng"], "accuracy_m": 5,
            }, timeout=15)
            assert r2.status_code == 200, r2.text
            created.append(r2.json()["id"])

            team = requests.get(f"{API}/mobile/punch/team",
                                headers=_h(gov_admin["token"]), timeout=15).json()
            by_id = {p["id"]: p for p in team["punches"]}
            assert by_id[created[0]]["in_zone"] is True
            assert by_id[created[1]]["in_zone"] is False
            assert by_id[created[1]]["distance_from_branch_m"] > 1000
            assert team["stats"]["out_zone"] >= 1
        finally:
            _db.attendance.delete_many({"id": {"$in": created}})

    def test_supervisor_scope_limited_to_own_branches(self, adama):
        """Adama supervises MOF-HQ — team map must only include her branches."""
        r = requests.get(f"{API}/mobile/punch/team", headers=_h(adama["token"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        own = {b["id"] for b in _db.branches.find({"supervisor_user_id": adama["id"]})}
        assert {b["id"] for b in d["branches"]} == own
        for p in d["punches"]:
            assert p["branch_id"] in own

    def test_csv_export(self, gov_admin):
        r = requests.get(f"{API}/mobile/punch/team.csv", headers=_h(gov_admin["token"]), timeout=15)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        head = r.text.splitlines()[0]
        assert "employee" in head and "zone" in head and "distance_from_branch_m" in head

    def test_date_filter(self, gov_admin):
        r = requests.get(f"{API}/mobile/punch/team", params={"date": "2020-01-01"},
                         headers=_h(gov_admin["token"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["date"] == "2020-01-01"
        assert d["stats"]["total"] == 0
