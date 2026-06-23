"""Establishment Control tests:
  - hierarchy build (Ministry → Directorate → Unit)
  - position CRUD
  - assign/unassign + vacancy/overrun tracking
  - tier-gating (lite gets 402)
"""
import os
import requests
import pyotp
import pytest

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"
GOV_EMAIL = "admin@gov.sl"
GOV_PASS = "GovAdmin@2026"
SUPER_EMAIL = "admin@salonehcm.sl"
SUPER_PASS = "Admin@2026"
SUPER_SECRET = os.environ.get("SUPERADMIN_TOTP_SECRET", "KRSXG5BANFXSAYTBORQXG43LMR2A")


@pytest.fixture
def gov_h():
    tok = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


def test_tree_returns_seeded_ministries(gov_h):
    r = requests.get(f"{API}/establishment/tree", headers=gov_h)
    assert r.status_code == 200
    body = r.json()
    ministries = body["ministries"]
    assert len(ministries) >= 3, f"expected ≥3 ministries, got {len(ministries)}"
    names = {m["name"] for m in ministries}
    assert "Ministry of Finance" in names
    assert "Ministry of Health and Sanitation" in names
    # Roll-up: each ministry has approved/filled/vacancy counts
    for m in ministries:
        assert "approved_count" in m and "filled_count" in m and "vacancy_count" in m
        assert m["filled_count"] <= m["approved_count"] + m.get("overrun_count", 0)
        # Directorate counts roll up
        sum_d = sum(d["approved_count"] for d in m["directorates"])
        assert sum_d == m["approved_count"]


def test_positions_flat_list_includes_metadata(gov_h):
    r = requests.get(f"{API}/establishment/positions", headers=gov_h)
    assert r.status_code == 200
    positions = r.json()
    assert len(positions) >= 14
    sample = positions[0]
    assert "filled_count" in sample and "vacancy_count" in sample
    assert "overrun_count" in sample and "utilisation" in sample


def test_create_patch_delete_lifecycle(gov_h):
    create = requests.post(f"{API}/establishment/positions", headers=gov_h, json={
        "ministry": f"TestMin_{os.urandom(2).hex()}",
        "directorate": "TestDir",
        "unit": "TestUnit",
        "position_title": "Test Officer",
        "approved_count": 2,
        "grade_code": "GS09",
    })
    assert create.status_code == 201, create.text
    pid = create.json()["id"]
    # Patch — increase approved count
    patch = requests.patch(f"{API}/establishment/positions/{pid}", headers=gov_h,
                           json={"approved_count": 5})
    assert patch.status_code == 200
    assert patch.json()["approved_count"] == 5
    # Try to delete with filled=0 → ok
    d = requests.delete(f"{API}/establishment/positions/{pid}", headers=gov_h)
    assert d.status_code == 200


def test_assign_and_unassign_employee(gov_h):
    # Find a free position with capacity in MoF
    positions = requests.get(f"{API}/establishment/positions", headers=gov_h).json()
    target = next((p for p in positions if p["vacancy_count"] > 0 and p["status"] == "active"), None)
    assert target, "Need at least one vacant Gov position to test assignment"
    initial_filled = target["filled_count"]
    # Find an unassigned Gov employee, or unassign one first so we can re-assign cleanly.
    employees = requests.get(f"{API}/employees", headers=gov_h).json()
    candidate = next((e for e in employees if not e.get("position_id")), None)
    if not candidate:
        candidate = employees[0]
        cur_pos = candidate.get("position_id")
        if cur_pos:
            requests.post(f"{API}/establishment/positions/{cur_pos}/unassign",
                          headers=gov_h, json={"employee_id": candidate["id"]})
        # Re-fetch initial_filled because we may have changed it via unassign
        positions = requests.get(f"{API}/establishment/positions", headers=gov_h).json()
        target = next(p for p in positions if p["id"] == target["id"])
        initial_filled = target["filled_count"]
    eid = candidate["id"]
    r = requests.post(f"{API}/establishment/positions/{target['id']}/assign",
                      headers=gov_h, json={"employee_id": eid})
    assert r.status_code == 200, r.text
    # Position filled_count should bump by exactly 1
    re = requests.get(f"{API}/establishment/positions", headers=gov_h).json()
    fresh = next(p for p in re if p["id"] == target["id"])
    assert fresh["filled_count"] == initial_filled + 1, f"expected {initial_filled + 1}, got {fresh['filled_count']}"
    # Unassign
    u = requests.post(f"{API}/establishment/positions/{target['id']}/unassign",
                      headers=gov_h, json={"employee_id": eid})
    assert u.status_code == 200


def test_cannot_lower_approved_below_filled(gov_h):
    # Pick a position with filled > 0
    positions = requests.get(f"{API}/establishment/positions", headers=gov_h).json()
    target = next((p for p in positions if p["filled_count"] > 0), None)
    if not target:
        pytest.skip("No filled positions available for this test")
    r = requests.patch(f"{API}/establishment/positions/{target['id']}", headers=gov_h,
                       json={"approved_count": 0})
    assert r.status_code == 409
    assert "filled" in r.text.lower()


def test_cannot_assign_to_full_position(gov_h):
    # Create a tiny position with capacity=1, fill it, then attempt 2nd assignment.
    c = requests.post(f"{API}/establishment/positions", headers=gov_h, json={
        "ministry": "Cap Test", "directorate": "X", "unit": "Y",
        "position_title": "Capacity Probe", "approved_count": 1,
    })
    assert c.status_code == 201
    pid = c.json()["id"]
    # Two employees in the tenant
    employees = requests.get(f"{API}/employees", headers=gov_h).json()
    e1, e2 = employees[0], employees[1]
    requests.post(f"{API}/establishment/positions/{pid}/assign",
                  headers=gov_h, json={"employee_id": e1["id"]})
    r = requests.post(f"{API}/establishment/positions/{pid}/assign",
                      headers=gov_h, json={"employee_id": e2["id"]})
    assert r.status_code == 409
    # Cleanup
    requests.post(f"{API}/establishment/positions/{pid}/unassign",
                  headers=gov_h, json={"employee_id": e1["id"]})
    requests.delete(f"{API}/establishment/positions/{pid}", headers=gov_h)


def test_cannot_delete_filled_position(gov_h):
    positions = requests.get(f"{API}/establishment/positions", headers=gov_h).json()
    target = next((p for p in positions if p["filled_count"] > 0), None)
    if not target:
        pytest.skip("No filled positions available")
    r = requests.delete(f"{API}/establishment/positions/{target['id']}", headers=gov_h)
    assert r.status_code == 409


def test_vacancies_and_overruns_endpoints(gov_h):
    v = requests.get(f"{API}/establishment/vacancies", headers=gov_h)
    o = requests.get(f"{API}/establishment/overruns", headers=gov_h)
    assert v.status_code == 200 and o.status_code == 200
    assert all(p["vacancy_count"] > 0 for p in v.json())
    assert all(p["overrun_count"] > 0 for p in o.json())


def test_lite_tier_blocked_by_402():
    """Spin up a lite tenant via super-admin and verify it gets 402 on establishment endpoints."""
    super_tok = requests.post(f"{API}/auth/login", json={
        "email": SUPER_EMAIL, "password": SUPER_PASS,
        "totp_code": pyotp.TOTP(SUPER_SECRET).now(),
    }).json()["token"]
    h_super = {"Authorization": f"Bearer {super_tok}"}
    payload = {
        "name": f"EST_TEST_LITE_{os.urandom(2).hex()}",
        "tier": "lite",
        "admin_name": "Lite Tester",
        "admin_email": f"est_lite_{os.urandom(2).hex()}@nope.sl",
        "admin_password": "TestLite@2026",
    }
    r = requests.post(f"{API}/admin/companies", headers=h_super, json=payload)
    assert r.status_code == 200, r.text
    new_id = r.json()["company"]["id"]
    try:
        login = requests.post(f"{API}/auth/login",
                              json={"email": payload["admin_email"], "password": payload["admin_password"]})
        lite_tok = login.json()["token"]
        r = requests.get(f"{API}/establishment/tree", headers={"Authorization": f"Bearer {lite_tok}"})
        assert r.status_code == 402
    finally:
        requests.delete(f"{API}/admin/companies/{new_id}", headers=h_super)
