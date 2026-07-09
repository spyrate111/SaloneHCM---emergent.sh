"""iter30 — Payroll variance analysis + demo videos CDN fix."""
import os
import uuid
import requests
import pytest

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
GOV_EMAIL, GOV_PASS = "admin@gov.sl", "GovAdmin@2026"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def gov_token():
    return _login(GOV_EMAIL, GOV_PASS)


@pytest.fixture(scope="module")
def two_consecutive_runs(gov_token):
    """Create two consecutive-period payroll runs so variance has something to diff."""
    # Ensure runs exist for both 2026-05 and 2026-06 (conftest auto-satisfies budget check)
    r1 = requests.post(f"{API}/payroll/run", headers=_h(gov_token),
                       json={"period_year": 2026, "period_month": 5}, timeout=30)
    assert r1.status_code == 200, r1.text
    r2 = requests.post(f"{API}/payroll/run", headers=_h(gov_token),
                       json={"period_year": 2026, "period_month": 6}, timeout=30)
    assert r2.status_code == 200, r2.text
    return {"prior": r1.json(), "current": r2.json()}


class TestVarianceBasics:
    def test_variance_endpoint_returns_expected_shape(self, gov_token, two_consecutive_runs):
        rid = two_consecutive_runs["current"]["id"]
        r = requests.get(f"{API}/payroll/runs/{rid}/variance", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["run_id"] == rid
        assert d["current_period"] == "2026-06"
        assert d["prior_period"] == "2026-05"
        assert d["prior_exists"] is True
        for k in ("headcount", "gross", "paye", "nassit_employee", "nassit_employer", "net"):
            assert k in d["totals"]["current"], f"missing {k}"
            assert k in d["totals"]["prior"], f"missing {k}"
            assert k in d["totals"]["delta"], f"missing delta.{k}"
        assert "by_ministry" in d
        assert isinstance(d["by_ministry"], list)
        assert "anomalies" in d and isinstance(d["anomalies"], list)
        assert "anomaly_summary" in d

    def test_variance_no_prior_period_still_returns_baseline(self, gov_token):
        """Very early period → no prior run → prior_exists=False, no crash."""
        # Create a standalone run for 2021-02 (no 2021-01 run exists)
        r_run = requests.post(f"{API}/payroll/run", headers=_h(gov_token),
                              json={"period_year": 2021, "period_month": 2}, timeout=30)
        # This may already fail at run-time due to the budget guardrail — conftest auto-satisfies
        if r_run.status_code != 200:
            pytest.skip(f"cannot create baseline run: {r_run.text[:100]}")
        rid = r_run.json()["id"]
        r = requests.get(f"{API}/payroll/runs/{rid}/variance", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["prior_exists"] is False
        assert r.json()["prior_period"] == "2021-01"

    def test_variance_unknown_run_404(self, gov_token):
        r = requests.get(f"{API}/payroll/runs/does-not-exist/variance", headers=_h(gov_token), timeout=15)
        assert r.status_code == 404


class TestAnomalyDetection:
    def test_raise_anomaly_triggered_by_salary_bump(self, gov_token):
        """Manually spike an employee's basic salary → next run's variance flags a raise."""
        emps = requests.get(f"{API}/employees", headers=_h(gov_token), timeout=15).json()
        emp = emps[0]
        # Create baseline run at 2026-07
        requests.post(f"{API}/payroll/run", headers=_h(gov_token),
                      json={"period_year": 2026, "period_month": 7}, timeout=30)
        original_basic = emp.get("basic_salary_sle") or emp.get("base_salary_sle") or 3000
        # Spike +50%
        upd = requests.put(f"{API}/employees/{emp['id']}", headers=_h(gov_token),
                           json={**emp, "basic_salary_sle": original_basic * 1.5}, timeout=15)
        try:
            assert upd.status_code == 200, upd.text
            r2 = requests.post(f"{API}/payroll/run", headers=_h(gov_token),
                               json={"period_year": 2026, "period_month": 8}, timeout=30)
            assert r2.status_code == 200
            v = requests.get(f"{API}/payroll/runs/{r2.json()['id']}/variance",
                             headers=_h(gov_token), timeout=15).json()
            raises = [a for a in v["anomalies"] if a["kind"] == "raise" and a["employee_id"] == emp["id"]]
            assert raises, f"expected raise anomaly for {emp['first_name']} {emp['last_name']}: got {v['anomalies']}"
            assert raises[0]["severity"] in ("warn", "high")
            assert raises[0]["delta_pct"] >= 10
        finally:
            # Restore original salary
            requests.put(f"{API}/employees/{emp['id']}", headers=_h(gov_token),
                         json={**emp, "basic_salary_sle": original_basic}, timeout=15)

    def test_ministry_table_ranked_by_pct_change(self, gov_token, two_consecutive_runs):
        rid = two_consecutive_runs["current"]["id"]
        v = requests.get(f"{API}/payroll/runs/{rid}/variance", headers=_h(gov_token), timeout=15).json()
        rows = v["by_ministry"]
        # Ranked desc by |delta_gross_pct| — rows with non-null pct come first
        pcts = [abs(r["delta_gross_pct"] or 0) for r in rows]
        assert pcts == sorted(pcts, reverse=True), f"ministry table not ranked: {pcts}"


class TestDemoVideosCdn:
    def test_all_seeded_videos_use_working_cdn(self, gov_token):
        r = requests.get(f"{API}/marketing/videos", timeout=15)
        assert r.status_code == 200
        payload = r.json()
        videos = payload if isinstance(payload, list) else payload.get("videos", [])
        assert len(videos) >= 9, "expected at least 9 seeded videos"
        for v in videos:
            src = v.get("src", "")
            # Guard: no broken CDN
            assert "commondatastorage.googleapis.com/gtv-videos-bucket" not in src, \
                f"video still points at retired Google gtv-videos-bucket: {v['title']}"
            # Sanity: HTTPS media source
            assert src.startswith("https://"), f"insecure src: {src}"
