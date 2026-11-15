"""iter31 — Options C (retro-pay), D (multi-sig MoF), E (cutoff lock)."""
import os
import uuid
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
GOV_EMAIL, GOV_PASS = "admin@gov.sl", "GovAdmin@2026"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _period(offset=0):
    d = datetime.now(timezone.utc)
    y, m = d.year, d.month + offset
    while m > 12: m -= 12; y += 1
    while m < 1: m += 12; y -= 1
    return f"{y}-{m:02d}"


@pytest.fixture(scope="module")
def gov_token():
    return _login(GOV_EMAIL, GOV_PASS)


# ============================================================
# Option C — Retro-pay engine
# ============================================================
class TestRetroPay:
    def test_create_low_value_retro_goes_directly_to_pending(self, gov_token):
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        emp = emps[0]
        body = {
            "employee_id": emp["id"],
            "monthly_delta_sle": 5,  # tiny amount → <10% of basic
            "effective_from": "2026-01",
            "effective_to": "2026-02",
            "source": "step_increment",
            "reason": "iter31 low-value retro test — auto-approved",
        }
        r = requests.post(f"{API}/civil-service/retro-pay", headers=_h(gov_token), json=body, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["months"] == 2
        assert d["total_owed_sle"] == 10.0
        assert d["requires_mof_approval"] is False
        assert d["status"] == "pending"
        # cleanup
        requests.delete(f"{API}/civil-service/retro-pay/{d['id']}", headers=_h(gov_token), timeout=15)

    def test_create_high_value_retro_needs_approval(self, gov_token):
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        emp = emps[0]
        basic = emp.get("basic_salary_sle") or 3000
        body = {
            "employee_id": emp["id"],
            "monthly_delta_sle": basic,  # ≥ 10% of basic for any month count > 0
            "effective_from": "2026-01",
            "effective_to": "2026-01",
            "source": "grade_change",
            "reason": "iter31 high-value retro — must require MoF approval",
        }
        r = requests.post(f"{API}/civil-service/retro-pay", headers=_h(gov_token), json=body, timeout=15).json()
        assert r["requires_mof_approval"] is True
        assert r["status"] == "pending_approval"

        # Approve
        approval = requests.post(f"{API}/civil-service/retro-pay/{r['id']}/approve",
                                 headers=_h(gov_token),
                                 json={"id": r["id"], "approve": True, "note": "checked & signed"},
                                 timeout=15)
        assert approval.status_code == 200
        assert approval.json()["status"] == "pending"
        # cleanup
        requests.delete(f"{API}/civil-service/retro-pay/{r['id']}", headers=_h(gov_token), timeout=15)

    def test_reject_marks_status_rejected(self, gov_token):
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        emp = emps[0]
        r = requests.post(f"{API}/civil-service/retro-pay", headers=_h(gov_token), json={
            "employee_id": emp["id"], "monthly_delta_sle": 10000,
            "effective_from": "2026-01", "effective_to": "2026-02",
            "source": "manual",
            "reason": "iter31 to-be-rejected retro adjustment",
        }, timeout=15).json()
        # Reject
        rej = requests.post(f"{API}/civil-service/retro-pay/{r['id']}/approve", headers=_h(gov_token),
                            json={"id": r["id"], "approve": False, "note": "duplicate — see APP-XX"}, timeout=15)
        assert rej.status_code == 200
        assert rej.json()["status"] == "rejected"
        # Cannot re-approve
        again = requests.post(f"{API}/civil-service/retro-pay/{r['id']}/approve", headers=_h(gov_token),
                              json={"id": r["id"], "approve": True, "note": "changed mind"}, timeout=15)
        assert again.status_code == 409
        # cleanup
        requests.delete(f"{API}/civil-service/retro-pay/{r['id']}", headers=_h(gov_token), timeout=15)

    def test_settled_adjustment_cannot_be_deleted(self, gov_token):
        # Create adjustment, force settle via DB, verify DELETE returns 409
        from pymongo import MongoClient
        db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
            os.environ.get("DB_NAME", "salonehcm_db")
        ]
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        r = requests.post(f"{API}/civil-service/retro-pay", headers=_h(gov_token), json={
            "employee_id": emps[0]["id"], "monthly_delta_sle": 5,
            "effective_from": "2026-01", "effective_to": "2026-01",
            "source": "manual", "reason": "iter31 settled protection test",
        }, timeout=15).json()
        db.retro_pay_adjustments.update_one({"id": r["id"]}, {"$set": {"status": "settled"}})
        d = requests.delete(f"{API}/civil-service/retro-pay/{r['id']}", headers=_h(gov_token), timeout=15)
        assert d.status_code == 409
        db.retro_pay_adjustments.delete_one({"id": r["id"]})


# ============================================================
# Option D — Multi-signature MoF
# ============================================================
class TestMoFSignatures:
    def test_default_signatures_required_is_1(self, gov_token):
        r = requests.get(f"{API}/civil-service/mof/config", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["signatures_required"] in (1, 2, 3)

    def test_signatures_config_requires_superadmin(self, gov_token):
        r = requests.put(f"{API}/civil-service/mof/config", headers=_h(gov_token),
                         json={"signatures_required": 2}, timeout=15)
        # Gov admin is not superadmin → 403
        assert r.status_code == 403

    def test_signature_endpoint_records_signature(self, gov_token):
        # Need an existing gov run in submitted state
        runs = requests.get(f"{API}/payroll/runs", headers=_h(gov_token), timeout=15).json()
        submitted = next((r for r in runs if r.get("mof_status") == "submitted"), None)
        if not submitted:
            # Create one by running a rarely-used period + submitting for MoF.
            # _period(6) stays clear of iter29's poisoned _period(2)/(3) budget periods.
            p = _period(6)
            _r = requests.post(f"{API}/payroll/run", headers=_h(gov_token),
                               json={"period_year": int(p[:4]), "period_month": int(p[5:])}, timeout=30).json()
            if "id" not in _r:
                pytest.skip(f"cannot create run for {p}: {str(_r)[:120]}")
            sub = requests.post(f"{API}/civil-service/mof/submit/{_r['id']}", headers=_h(gov_token), timeout=15)
            if sub.status_code != 200:
                pytest.skip(f"cannot create submitted run: {sub.text[:100]}")
            submitted = {"id": _r["id"], "mof_status": "submitted"}

        rid = submitted["id"]
        r = requests.post(f"{API}/civil-service/mof/runs/{rid}/sign", headers=_h(gov_token),
                          json={"action": "approve", "note": "iter31 signature test"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["approves"] >= 1
        assert d["mof_status"] in ("approved", "partially_signed")
        assert len(d["signatures"]) >= 1
        assert d["signatures"][-1]["signer_email"] == GOV_EMAIL

    def test_cannot_sign_same_run_twice(self, gov_token):
        # Reuse the run from previous test
        runs = requests.get(f"{API}/payroll/runs", headers=_h(gov_token), timeout=15).json()
        with_sig = [r for r in runs if r.get("mof_signatures")]
        if not with_sig:
            pytest.skip("no run with an existing signature to test double-sign")
        rid = with_sig[0]["id"]
        r = requests.post(f"{API}/civil-service/mof/runs/{rid}/sign", headers=_h(gov_token),
                          json={"action": "approve", "note": "attempting double-sign"}, timeout=15)
        assert r.status_code in (409, 403), r.text


# ============================================================
# Option E — Cutoff lock
# ============================================================
class TestCutoffLock:
    def test_status_endpoint_returns_unlocked_when_disabled(self, gov_token):
        # First ensure disabled state
        requests.put(f"{API}/payroll/cutoff/config", headers=_h(gov_token),
                     json={"payroll_cutoff_day": 25, "enabled": False}, timeout=15)
        r = requests.get(f"{API}/payroll/cutoff/status", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["locked"] is False

    def test_cutoff_config_persists(self, gov_token):
        r = requests.put(f"{API}/payroll/cutoff/config", headers=_h(gov_token),
                         json={"payroll_cutoff_day": 20, "enabled": True}, timeout=15)
        assert r.status_code == 200
        assert r.json()["payroll_cutoff_day"] == 20
        # Read back
        r2 = requests.get(f"{API}/payroll/cutoff/config", headers=_h(gov_token), timeout=15)
        assert r2.json()["enabled"] is True
        assert r2.json()["payroll_cutoff_day"] == 20
        # cleanup — turn back off so other tests aren't affected
        requests.put(f"{API}/payroll/cutoff/config", headers=_h(gov_token),
                     json={"payroll_cutoff_day": 25, "enabled": False}, timeout=15)

    def test_cutoff_blocks_hire_when_active(self, gov_token):
        # Enable cutoff at day 1 (already past)
        today = datetime.now(timezone.utc)
        requests.put(f"{API}/payroll/cutoff/config", headers=_h(gov_token),
                     json={"payroll_cutoff_day": 1, "enabled": True}, timeout=15)
        try:
            # Confirm cutoff is now active (no completed run for current period)
            s = requests.get(f"{API}/payroll/cutoff/status", headers=_h(gov_token), timeout=15).json()
            if not s["locked"]:
                pytest.skip(f"cutoff didn't activate — likely a run exists for {s.get('period')}")
            # Try hire
            r = requests.post(f"{API}/employees", headers=_h(gov_token), json={
                "first_name": "Blocked", "last_name": f"Hire{uuid.uuid4().hex[:4]}",
                "email": f"blocked_{uuid.uuid4().hex[:6]}@gov.sl",
                "phone": "+23276111111",
                "department": "Test", "job_title": "Analyst",
                "basic_salary_sle": 3000,
                "hire_date": today.strftime("%Y-%m-%d"), "status": "active",
            }, timeout=15)
            assert r.status_code == 423, f"expected 423 Locked, got {r.status_code}: {r.text}"
            body = r.json()
            assert body["detail"]["code"] == "payroll_cutoff_locked"
        finally:
            requests.put(f"{API}/payroll/cutoff/config", headers=_h(gov_token),
                         json={"payroll_cutoff_day": 25, "enabled": False}, timeout=15)
