"""Sector Allowance Presets + Promotion Eligibility tests."""
import os
import requests
import pyotp
import pytest
from pymongo import MongoClient

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"
GOV_EMAIL = "admin@gov.sl"; GOV_PASS = "GovAdmin@2026"
SUPER_EMAIL = "admin@salonehcm.sl"; SUPER_PASS = "Admin@2026"
SUPER_SECRET = "KRSXG5BANFXSAYTBORQXG43LMR2A"


@pytest.fixture
def gov_h():
    tok = requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(autouse=True)
def _isolate():
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "salonehcm_db")]
    yield
    db.step_promotion_recommendations.delete_many({})
    # Reset Gov employees' sector overlay only
    db.employees.update_many(
        {"sector_preset_id": {"$exists": True}},
        {"$unset": {"sector_allowances": "", "sector_preset_id": "", "sector_applied_at": ""}},
    )


# ---------- Sector presets ----------

def test_sector_catalog_returns_five_presets(gov_h):
    r = requests.get(f"{API}/sector-presets/catalog", headers=gov_h)
    assert r.status_code == 200
    presets = r.json()["presets"]
    assert len(presets) == 5
    ids = {p["id"] for p in presets}
    assert ids == {"ngo", "mining", "banking", "telecom", "general"}
    for p in presets:
        assert "total_monthly_sle" in p and p["total_monthly_sle"] > 0


def test_apply_preset_to_employee(gov_h):
    emps = requests.get(f"{API}/employees", headers=gov_h).json()
    eid = emps[0]["id"]
    r = requests.post(f"{API}/sector-presets/apply/{eid}", headers=gov_h,
                      json={"preset_id": "ngo"})
    assert r.status_code == 200
    # Inspect
    r2 = requests.get(f"{API}/sector-presets/employee/{eid}", headers=gov_h)
    body = r2.json()
    assert body["preset_id"] == "ngo"
    assert len(body["allowances"]) == 4
    assert body["total_monthly_sle"] == 3800.0


def test_apply_preset_with_overrides(gov_h):
    emps = requests.get(f"{API}/employees", headers=gov_h).json()
    eid = emps[0]["id"]
    r = requests.post(f"{API}/sector-presets/apply/{eid}", headers=gov_h, json={
        "preset_id": "banking",
        "override_amounts": {"Cash-handling allowance": 1500.0},
    })
    assert r.status_code == 200
    body = requests.get(f"{API}/sector-presets/employee/{eid}", headers=gov_h).json()
    cash = next(a for a in body["allowances"] if a["label"] == "Cash-handling allowance")
    assert cash["amount_sle"] == 1500.0


def test_apply_bulk_by_ids(gov_h):
    emps = requests.get(f"{API}/employees", headers=gov_h).json()
    ids = [e["id"] for e in emps[:3]]
    r = requests.post(f"{API}/sector-presets/apply-bulk", headers=gov_h, json={
        "preset_id": "telecom", "employee_ids": ids,
    })
    assert r.status_code == 200
    assert r.json()["applied_to"] == 3


def test_clear_preset(gov_h):
    emps = requests.get(f"{API}/employees", headers=gov_h).json()
    eid = emps[0]["id"]
    requests.post(f"{API}/sector-presets/apply/{eid}", headers=gov_h, json={"preset_id": "mining"})
    r = requests.delete(f"{API}/sector-presets/clear/{eid}", headers=gov_h)
    assert r.status_code == 200
    body = requests.get(f"{API}/sector-presets/employee/{eid}", headers=gov_h).json()
    assert body["preset_id"] is None
    assert body["allowances"] == []


def test_sector_allowances_flow_into_payroll(gov_h):
    """Apply a preset, run payroll, verify the gross includes the preset total."""
    emps = requests.get(f"{API}/employees", headers=gov_h).json()
    e = emps[0]
    # Snapshot original gross
    rp = requests.post(f"{API}/payroll/run", headers=gov_h, json={"period_year": 2099, "period_month": 6})
    assert rp.status_code == 200
    before_slip = next(s for s in rp.json()["slips"] if s["employee_id"] == e["id"])
    before_gross = before_slip["gross"]
    # Apply general preset (2250 SLE total)
    requests.post(f"{API}/sector-presets/apply/{e['id']}", headers=gov_h, json={"preset_id": "general"})
    # Run NEW period (so payroll re-computes)
    rp2 = requests.post(f"{API}/payroll/run", headers=gov_h, json={"period_year": 2099, "period_month": 7})
    after_slip = next(s for s in rp2.json()["slips"] if s["employee_id"] == e["id"])
    # Gross should be higher by ~2250 (with rounding)
    assert after_slip["gross"] >= before_gross + 2200, f"expected +2250, got delta {after_slip['gross']-before_gross}"
    # Cleanup
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "salonehcm_db")]
    db.payroll_runs.delete_many({"period": {"$in": ["2099-06", "2099-07"]}})


# ---------- Promotion eligibility ----------

def test_eligible_list_returns_rows(gov_h):
    r = requests.get(f"{API}/promotion/eligible", headers=gov_h)
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body and "eligible_count" in body
    # Gov has 6+ active employees; all should appear with reasons (no one has 365d tenure yet)
    assert len(body["rows"]) >= 6


def test_cannot_recommend_non_eligible(gov_h):
    """All seeded Gov employees have 0-day tenure → all non-eligible."""
    rows = requests.get(f"{API}/promotion/eligible", headers=gov_h).json()["rows"]
    target = next(r for r in rows if not r["eligible"])
    r = requests.post(f"{API}/promotion/recommendations", headers=gov_h,
                      json={"employee_id": target["employee_id"]})
    assert r.status_code == 409


def test_recommend_approve_lifecycle(gov_h):
    """Force an employee to be eligible (set last_step_increment_at far in the past)
    and create a completed review, then recommend → approve."""
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "salonehcm_db")]
    gov_id = db.companies.find_one({"name": "Government of Sierra Leone"})["id"]
    emp = db.employees.find_one({"company_id": gov_id, "grade_code": "GR1"})
    # Force tenure + create a passing review
    db.employees.update_one(
        {"id": emp["id"]},
        {"$set": {"last_step_increment_at": "2024-01-01T00:00:00+00:00"}},
    )
    cid = "promo-test-cycle"
    db.review_cycles.update_one(
        {"id": cid},
        {"$set": {"id": cid, "company_id": gov_id, "name": "Promo Test", "period": "2025",
                  "status": "closed"}},
        upsert=True,
    )
    db.performance_reviews_v2.update_one(
        {"id": "promo-test-review"},
        {"$set": {
            "id": "promo-test-review", "company_id": gov_id, "cycle_id": cid,
            "employee_id": emp["id"], "status": "completed",
            "manager_rating": 5.0, "created_at": "2025-12-15T00:00:00+00:00",
        }},
        upsert=True,
    )
    try:
        # Now eligible
        elig_row = next((r for r in requests.get(f"{API}/promotion/eligible", headers=gov_h).json()["rows"]
                         if r["employee_id"] == emp["id"]), None)
        assert elig_row and elig_row["eligible"], f"expected eligible, got: {elig_row}"
        # Recommend
        rec = requests.post(f"{API}/promotion/recommendations", headers=gov_h,
                            json={"employee_id": emp["id"], "notes": "Testing"})
        assert rec.status_code == 201
        rid = rec.json()["id"]
        # Approve — need mof_approver flag (admin@gov.sl already has it per seed)
        ap = requests.post(f"{API}/promotion/recommendations/{rid}/approve", headers=gov_h, json={"note": "OK"})
        assert ap.status_code == 200
        body = ap.json()
        assert body["new_step"] == elig_row["next_step"]
        # Employee step should be bumped
        fresh = db.employees.find_one({"id": emp["id"]})
        assert fresh["step_number"] == elig_row["next_step"]
    finally:
        # Cleanup
        db.employees.update_one({"id": emp["id"]}, {"$set": {
            "step_number": emp.get("step_number", 5),
            "basic_salary_sle": emp.get("basic_salary_sle"),
        }, "$unset": {"last_step_increment_at": ""}})
        db.performance_reviews_v2.delete_one({"id": "promo-test-review"})
        db.review_cycles.delete_one({"id": cid})
        db.step_promotion_recommendations.delete_many({"employee_id": emp["id"]})


def test_double_pending_recommendation_blocked(gov_h):
    """Setting up eligibility for one employee, recommend twice."""
    db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "salonehcm_db")]
    gov_id = db.companies.find_one({"name": "Government of Sierra Leone"})["id"]
    # Pick an employee whose grade has a next step (Sia: GR5 4→5)
    emp = db.employees.find_one({"company_id": gov_id, "grade_code": "GR5"})
    db.employees.update_one({"id": emp["id"]}, {"$set": {"last_step_increment_at": "2024-01-01T00:00:00+00:00"}})
    cid = "promo-dup-cycle"
    db.review_cycles.update_one({"id": cid},
        {"$set": {"id": cid, "company_id": gov_id, "name": "Dup", "period": "2025", "status": "closed"}}, upsert=True)
    db.performance_reviews_v2.update_one({"id": "promo-dup-review"},
        {"$set": {"id": "promo-dup-review", "company_id": gov_id, "cycle_id": cid,
                  "employee_id": emp["id"], "status": "completed", "manager_rating": 5.0,
                  "created_at": "2025-12-15T00:00:00+00:00"}}, upsert=True)
    try:
        r1 = requests.post(f"{API}/promotion/recommendations", headers=gov_h,
                           json={"employee_id": emp["id"]})
        assert r1.status_code == 201
        r2 = requests.post(f"{API}/promotion/recommendations", headers=gov_h,
                           json={"employee_id": emp["id"]})
        assert r2.status_code == 409
    finally:
        db.employees.update_one({"id": emp["id"]}, {"$unset": {"last_step_increment_at": ""}})
        db.performance_reviews_v2.delete_one({"id": "promo-dup-review"})
        db.review_cycles.delete_one({"id": cid})
        db.step_promotion_recommendations.delete_many({"employee_id": emp["id"]})


def test_lite_tier_blocked_from_sector(gov_h):
    """sector_presets requires professional+. Lite gets 402."""
    super_tok = requests.post(f"{API}/auth/login", json={
        "email": SUPER_EMAIL, "password": SUPER_PASS,
        "totp_code": pyotp.TOTP(SUPER_SECRET).now(),
    }).json()["token"]
    h_super = {"Authorization": f"Bearer {super_tok}"}
    payload = {
        "name": f"SECT_TEST_LITE_{os.urandom(2).hex()}",
        "tier": "lite", "admin_name": "Sector Lite",
        "admin_email": f"sect_lite_{os.urandom(2).hex()}@nope.sl",
        "admin_password": "TestLite@2026",
    }
    r = requests.post(f"{API}/admin/companies", headers=h_super, json=payload)
    assert r.status_code == 200, r.text
    cid = r.json()["company"]["id"]
    try:
        lt = requests.post(f"{API}/auth/login",
                           json={"email": payload["admin_email"], "password": payload["admin_password"]}).json()["token"]
        r = requests.get(f"{API}/sector-presets/catalog", headers={"Authorization": f"Bearer {lt}"})
        assert r.status_code == 402
    finally:
        requests.delete(f"{API}/admin/companies/{cid}", headers=h_super)
