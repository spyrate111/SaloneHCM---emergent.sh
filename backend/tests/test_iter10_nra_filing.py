"""Iter10 — NRA filing exports (PAYE CSV, NASSIT CSV), mark-filed, summary, tenant isolation."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback for in-container runs
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

DEMO = ("admin@salonehcm.sl", "Admin@2026")
GOV = ("admin@gov.sl", "GovAdmin@2026")


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def gov_token():
    return _login(*GOV)


@pytest.fixture(scope="module")
def demo_token():
    return _login(*DEMO)


@pytest.fixture(scope="module")
def gov_run_id(gov_token):
    # Pick any payroll run for Gov; if none, create one for current month
    r = requests.get(f"{BASE}/api/payroll/runs", headers=_h(gov_token), timeout=15)
    assert r.status_code == 200, r.text
    runs = r.json()
    if not runs:
        # Create
        period = "2026-01"
        c = requests.post(f"{BASE}/api/payroll/runs", headers=_h(gov_token),
                          json={"period": period}, timeout=30)
        assert c.status_code in (200, 201), c.text
        return c.json()["id"]
    return runs[0]["id"]


@pytest.fixture(scope="module")
def demo_run_id(demo_token):
    r = requests.get(f"{BASE}/api/payroll/runs", headers=_h(demo_token), timeout=15)
    assert r.status_code == 200
    runs = r.json()
    if not runs:
        c = requests.post(f"{BASE}/api/payroll/runs", headers=_h(demo_token),
                          json={"period": "2026-01"}, timeout=30)
        assert c.status_code in (200, 201)
        return c.json()["id"]
    return runs[0]["id"]


# --- 1. NRA PAYE Return CSV ---
class TestNRAPayeReturnCSV:
    def test_gov_returns_csv(self, gov_token, gov_run_id):
        r = requests.get(f"{BASE}/api/compliance/nra-paye-return.csv/{gov_run_id}",
                         headers=_h(gov_token), timeout=20)
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "")
        body = r.text
        assert "NRA PAYE RETURN" in body
        assert "Period" in body
        assert "Employer TIN" in body
        assert "Employer Name" in body
        # Detail header line — exact columns
        for col in ["tin", "employee_name", "nassit_no", "department",
                    "gross_sle", "taxable_sle", "paye_sle",
                    "nassit_employee_sle", "nassit_employer_sle", "net_sle"]:
            assert col in body, f"missing column {col}"
        assert "TOTAL" in body

    def test_demo_blocked_402(self, demo_token, demo_run_id):
        r = requests.get(f"{BASE}/api/compliance/nra-paye-return.csv/{demo_run_id}",
                         headers=_h(demo_token), timeout=20)
        assert r.status_code == 402, f"expected 402, got {r.status_code} {r.text}"


# --- 2. NASSIT schedule CSV ---
class TestNassitScheduleCSV:
    def test_gov_returns_csv(self, gov_token, gov_run_id):
        r = requests.get(f"{BASE}/api/compliance/nassit-schedule.csv/{gov_run_id}",
                         headers=_h(gov_token), timeout=20)
        assert r.status_code == 200, r.text
        assert "text/csv" in r.headers.get("content-type", "")
        body = r.text
        assert "NASSIT CONTRIBUTION SCHEDULE" in body
        assert "Period" in body
        assert "Employer NASSIT" in body
        for col in ["nassit_no", "employee_name", "basic_sle", "employee_5pct", "employer_10pct", "total_15pct"]:
            assert col in body, f"missing column {col}"
        assert "TOTAL" in body

    def test_demo_blocked_402(self, demo_token, demo_run_id):
        r = requests.get(f"{BASE}/api/compliance/nassit-schedule.csv/{demo_run_id}",
                         headers=_h(demo_token), timeout=20)
        assert r.status_code == 402


# --- 3. Mark NRA filed ---
class TestMarkNRAFiled:
    def test_mark_filed_flow_and_conflict(self, gov_token, gov_run_id):
        # First filing — might already be filed from a prior test run; tolerate both cases
        r1 = requests.post(f"{BASE}/api/compliance/file-nra/{gov_run_id}",
                           headers=_h(gov_token), timeout=20)
        if r1.status_code == 409:
            # already filed in a previous iteration — treat as initial state and skip create assertion
            already = True
        else:
            assert r1.status_code == 200, r1.text
            data = r1.json()
            assert data["run_id"] == gov_run_id
            assert data["nra_reference"].startswith("NRA-")
            assert data["nra_reference"].count("-") == 2  # NRA-{period}-{prefix}
            already = False
        # Second call MUST be 409
        r2 = requests.post(f"{BASE}/api/compliance/file-nra/{gov_run_id}",
                           headers=_h(gov_token), timeout=20)
        assert r2.status_code == 409, f"expected 409, got {r2.status_code} {r2.text}"

    def test_demo_blocked_402(self, demo_token, demo_run_id):
        r = requests.post(f"{BASE}/api/compliance/file-nra/{demo_run_id}",
                          headers=_h(demo_token), timeout=20)
        assert r.status_code == 402


# --- 4. Compliance summary with filing status ---
class TestComplianceSummary:
    def test_summary_shape(self, gov_token):
        r = requests.get(f"{BASE}/api/compliance/summary", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("ytd_paye_sle", "ytd_nassit_sle", "filed_count", "outstanding", "history"):
            assert k in d, f"summary missing {k}"
        assert isinstance(d["history"], list)
        if d["history"]:
            row = d["history"][0]
            for k in ("run_id", "period", "paye", "nassit_total", "employees", "nra_filed"):
                assert k in row, f"history row missing {k}"

    def test_filed_count_reflects_filing(self, gov_token, gov_run_id):
        r = requests.get(f"{BASE}/api/compliance/summary", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["filed_count"] >= 1, "expected at least one filed run after TestMarkNRAFiled"
        # Find the filed run in history
        filed_rows = [h for h in d["history"] if h["nra_filed"]]
        assert any(h["run_id"] == gov_run_id for h in filed_rows), "filed run not in history"
        # And NOT in outstanding
        assert all(o["run_id"] != gov_run_id for o in d["outstanding"])


# --- 5. Tenant isolation on filings list ---
class TestTenantIsolation:
    def test_filings_list_gov_only(self, gov_token):
        r = requests.get(f"{BASE}/api/compliance/filings", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        # All should be Gov tenant — every doc should be for a Gov payroll run.
        # We can't easily fetch company_id from the doc (it might be stripped), so we
        # verify by cross-checking each run_id against Gov's payroll-runs list.
        gov_runs = {p["id"] for p in requests.get(
            f"{BASE}/api/payroll/runs", headers=_h(gov_token), timeout=15).json()}
        for row in rows:
            assert row["run_id"] in gov_runs, f"filing for non-Gov run leaked: {row['run_id']}"

    def test_filings_list_demo_no_gov_data(self, demo_token):
        r = requests.get(f"{BASE}/api/compliance/filings", headers=_h(demo_token), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        demo_runs = {p["id"] for p in requests.get(
            f"{BASE}/api/payroll/runs", headers=_h(demo_token), timeout=15).json()}
        for row in rows:
            assert row["run_id"] in demo_runs, f"Gov filing leaked to Demo: {row['run_id']}"


# --- 6. PWA icons live ---
class TestPWAIcons:
    @pytest.mark.parametrize("path,min_size", [("/icon-192.png", 500), ("/icon-512.png", 500)])
    def test_icon_served(self, path, min_size):
        r = requests.get(f"{BASE}{path}", timeout=15)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert "image/png" in r.headers.get("content-type", "").lower(), \
            f"{path} content-type={r.headers.get('content-type')}"
        assert len(r.content) > min_size, f"{path} size={len(r.content)} too small"
        # PNG magic bytes
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n", f"{path} not a PNG"

    def test_manifest_references_icons(self):
        r = requests.get(f"{BASE}/manifest.json", timeout=15)
        assert r.status_code == 200
        m = r.json()
        srcs = [i["src"] for i in m.get("icons", [])]
        assert "/icon-192.png" in srcs
        assert "/icon-512.png" in srcs
        assert m.get("theme_color") == "#133326"
