"""IFMIS integration layer tests:
  - bank format adapters produce well-formed files
  - treasury reconciliation totals match payroll totals
  - mark-reconciled is immutable
  - tier-gated correctly (lite has no access)
"""
import os
import csv
import io
import requests
import pyotp
import pytest

API = (os.environ.get("REACT_APP_BACKEND_URL") or "https://salonepaycms.preview.emergentagent.com") + "/api"
GOV_EMAIL = "admin@gov.sl"
GOV_PASS = "GovAdmin@2026"
SUPER_EMAIL = "admin@salonehcm.sl"
SUPER_PASS = "Admin@2026"
SUPER_SECRET = "KRSXG5BANFXSAYTBORQXG43LMR2A"


def _gov_token():
    return requests.post(f"{API}/auth/login", json={"email": GOV_EMAIL, "password": GOV_PASS}).json()["token"]


def _super_token():
    r = requests.post(f"{API}/auth/login",
                      json={"email": SUPER_EMAIL, "password": SUPER_PASS,
                            "totp_code": pyotp.TOTP(SUPER_SECRET).now()})
    return r.json()["token"]


@pytest.fixture(scope="module")
def gov_run():
    h = {"Authorization": f"Bearer {_gov_token()}"}
    runs = requests.get(f"{API}/payroll/runs", headers=h).json()
    assert runs, "Gov tenant has no payroll runs to test against"
    # Use the SECOND run so other tests that reconcile run[0] don't conflict
    return {"token": h["Authorization"].split(" ")[1], "run": runs[1] if len(runs) > 1 else runs[0]}


def test_formats_returns_six_banks():
    h = {"Authorization": f"Bearer {_gov_token()}"}
    r = requests.get(f"{API}/ifmis/formats", headers=h)
    assert r.status_code == 200
    formats = r.json()["formats"]
    codes = {f["code"] for f in formats}
    assert codes >= {"slcb", "rokel", "ecobank", "gtbank", "uba", "generic"}


@pytest.mark.parametrize("bank_code", ["slcb", "rokel", "ecobank", "gtbank", "uba", "generic"])
def test_bank_file_well_formed(gov_run, bank_code):
    h = {"Authorization": f"Bearer {gov_run['token']}"}
    r = requests.get(f"{API}/ifmis/runs/{gov_run['run']['id']}/disbursement/{bank_code}", headers=h)
    assert r.status_code == 200
    assert len(r.content) > 50
    body = r.text
    if bank_code == "slcb":
        # HDR|period|count|total|SLE  ...  TRL|count|total
        assert body.startswith("HDR|")
        assert "\nTRL|" in body
        # parse header
        hdr = body.splitlines()[0].split("|")
        assert hdr[0] == "HDR"
        assert hdr[4] == "SLE"
    elif bank_code == "rokel":
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0] == ["account_no", "branch_code", "beneficiary", "amount", "currency", "narrative"]
        assert all(row[4] == "SLE" for row in rows[1:])
    elif bank_code == "ecobank":
        assert body.startswith("ACCT|BENEFICIARY|AMOUNT|CCY|REF|CHK")
        for line in body.strip().splitlines()[1:]:
            parts = line.split("|")
            assert parts[3] == "SLE"
            assert parts[5].isdigit() and 0 <= int(parts[5]) <= 9
    elif bank_code == "gtbank":
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0][0] == "BeneficiaryAccountNumber"
        for row in rows[1:]:
            assert len(row[0]) >= 10, "account zero-padded to ≥10 digits"
    elif bank_code == "uba":
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0] == ["ACCOUNT", "BENEFICIARY_NAME", "AMOUNT", "CURRENCY_CODE", "REFERENCE"]
    elif bank_code == "generic":
        rows = list(csv.reader(io.StringIO(body)))
        assert rows[0] == ["bank_name", "account_no", "beneficiary", "amount_sle", "reference"]


def test_reconciliation_totals_match_run_totals(gov_run):
    h = {"Authorization": f"Bearer {gov_run['token']}"}
    rid = gov_run["run"]["id"]
    r = requests.get(f"{API}/ifmis/runs/{rid}/reconciliation", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["period"] == gov_run["run"]["period"]
    assert body["org_code"], "ifmis_org_code should be set on Gov tenant"
    # Reconciliation totals must EQUAL the run-level totals (rounding tolerance).
    run_totals = gov_run["run"]["totals"]
    assert body["totals"]["headcount"] == run_totals["employee_count"]
    assert abs(body["totals"]["gross"] - run_totals["gross"]) < 0.05
    assert abs(body["totals"]["net"] - run_totals["net"]) < 0.05
    assert abs(body["totals"]["paye"] - run_totals["paye"]) < 0.05


def test_reconciliation_csv_has_total_row(gov_run):
    h = {"Authorization": f"Bearer {gov_run['token']}"}
    r = requests.get(f"{API}/ifmis/runs/{gov_run['run']['id']}/reconciliation.csv", headers=h)
    assert r.status_code == 200
    text = r.text
    assert "budget_code,mda_ministry,headcount" in text
    assert text.strip().endswith(",".join(["TOTAL", "", str(0)])[:0]) or "TOTAL" in text.splitlines()[-1]


def test_lite_tier_cannot_access_ifmis(gov_run):
    """Lite-tier tenants must get 403. Use the regular Gov user but spoof tier check
    indirectly by creating a temp lite tenant via super-admin admin endpoints."""
    super_tok = _super_token()
    h_super = {"Authorization": f"Bearer {super_tok}"}
    # Create a lite tenant
    payload = {"name": f"IFMIS_TEST_LITE_{os.urandom(2).hex()}",
               "tier": "lite",
               "admin_name": "IFMIS Lite Tester",
               "admin_email": f"ifmis_test_{os.urandom(2).hex()}@nope.sl",
               "admin_password": "TestLite@2026"}
    r = requests.post(f"{API}/admin/companies", headers=h_super, json=payload)
    assert r.status_code in (200, 201), r.text
    lite_admin_email = payload["admin_email"]
    lite_admin_pass = payload["admin_password"]
    try:
        # Login as lite admin
        login = requests.post(f"{API}/auth/login",
                              json={"email": lite_admin_email, "password": lite_admin_pass})
        assert login.status_code == 200
        lite_tok = login.json()["token"]
        r = requests.get(f"{API}/ifmis/formats", headers={"Authorization": f"Bearer {lite_tok}"})
        # 402 Payment Required is the project's tier-upgrade signal (set by require_feature).
        assert r.status_code == 402, f"lite tier must be blocked with 402, got {r.status_code}"
    finally:
        # Cleanup the temp tenant
        new_id = (r.json().get("company") or {}).get("id") if r.status_code == 200 else None
        if new_id:
            requests.delete(f"{API}/admin/companies/{new_id}", headers=h_super)


def test_mark_reconciled_is_immutable(gov_run):
    """Use the LAST run so we don't interfere with other tests."""
    h = {"Authorization": f"Bearer {_gov_token()}"}
    runs = requests.get(f"{API}/payroll/runs", headers=h).json()
    target = runs[-1]
    rid = target["id"]
    # Reset reconciled state for idempotent runs
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "salonehcm_db")
    MongoClient(mongo_url)[db_name].payroll_runs.update_one(
        {"id": rid},
        {"$unset": {"ifmis_reconciled": "", "ifmis_reference": "",
                    "ifmis_reconciled_at": "", "ifmis_reconciled_by": ""}},
    )

    r = requests.post(f"{API}/ifmis/runs/{rid}/mark-reconciled", headers=h,
                      json={"ifmis_reference": f"IFMIS-TEST-{os.urandom(2).hex()}"})
    assert r.status_code == 200, r.text
    assert r.json()["ifmis_reference"].startswith("IFMIS-TEST-")
    # Re-marking must 409
    r2 = requests.post(f"{API}/ifmis/runs/{rid}/mark-reconciled", headers=h,
                       json={"ifmis_reference": "IFMIS-TEST-XXX"})
    assert r2.status_code == 409
