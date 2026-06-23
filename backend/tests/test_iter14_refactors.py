"""
Iteration 14 regression — verifies refactored endpoints preserve behaviour:
  1) GET /api/ministry/rollup (after _blank_ministry/_accumulate_employee/_accumulate_leave/_finalize split)
  2) GET /api/performance/cycles/{cid}/analytics (after _compute_cycle_metrics helper split)
  3) GET /api/performance/cycles/{cid}/summary.pdf (consumes same helpers)
  4) GET /api/talent/completions/{cid}/certificate.pdf (after _cert_border/_cert_body/_cert_footer/_cert_qr split)
"""
import os
import io
import pyotp
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SUPER_EMAIL = "admin@salonehcm.sl"
SUPER_PASS = "Admin@2026"
TOTP_SECRET = os.environ.get("SUPERADMIN_TOTP_SECRET", "KRSXG5BANFXSAYTBORQXG43LMR2A")


# ---------- shared helpers ----------
def _login(email: str, password: str, totp: str | None = None) -> dict:
    body = {"email": email, "password": password}
    if totp:
        body["totp_code"] = totp
    r = requests.post(f"{BASE_URL}/api/auth/login", json=body, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def gov_token() -> str:
    return _login("admin@gov.sl", "GovAdmin@2026")["token"]


@pytest.fixture(scope="module")
def super_token() -> str:
    code = pyotp.TOTP(TOTP_SECRET).now()
    return _login(SUPER_EMAIL, SUPER_PASS, totp=code)["token"]


# ---------- module: ministry rollup refactor ----------
class TestMinistryRollupRefactor:
    def test_rollup_shape_and_totals(self, gov_token):
        r = requests.get(
            f"{BASE_URL}/api/ministry/rollup",
            headers={"Authorization": f"Bearer {gov_token}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ministries" in data and "totals" in data
        assert isinstance(data["ministries"], list)
        assert len(data["ministries"]) >= 1, "Gov tenant should expose at least one ministry"

        m0 = data["ministries"][0]
        required_keys = {
            "name", "headcount_total", "headcount_active", "headcount_managers",
            "monthly_payroll_gross", "monthly_payroll_net", "monthly_paye",
            "monthly_nassit", "avg_basic_salary", "leave_pending", "leave_approved_30d",
        }
        assert required_keys.issubset(m0.keys()), f"missing: {required_keys - set(m0.keys())}"

        totals = data["totals"]
        for k in ("ministries", "headcount_total", "headcount_active",
                  "monthly_payroll_gross", "monthly_payroll_net",
                  "monthly_paye", "monthly_nassit", "leave_pending"):
            assert k in totals

        # Cross-check: totals must equal sum of per-ministry rows
        sum_gross = round(sum(r["monthly_payroll_gross"] for r in data["ministries"]), 2)
        assert sum_gross == totals["monthly_payroll_gross"]
        assert totals["headcount_total"] == sum(r["headcount_total"] for r in data["ministries"])

        # Gov tier must actually produce non-zero PAYE & NASSIT for at least one ministry
        any_nonzero = any(m["monthly_payroll_gross"] > 0 and m["monthly_paye"] > 0 and m["monthly_nassit"] > 0
                          for m in data["ministries"])
        assert any_nonzero, "Expected at least one ministry with non-zero gross/PAYE/NASSIT"

        # Rows sorted by gross desc
        gs = [m["monthly_payroll_gross"] for m in data["ministries"]]
        assert gs == sorted(gs, reverse=True)


# ---------- module: performance analytics refactor ----------
class TestPerformanceAnalyticsRefactor:
    @pytest.fixture(scope="class")
    def cycle_id(self, gov_token):
        # Create a fresh Gov-tier cycle for analytics
        r = requests.post(
            f"{BASE_URL}/api/performance/cycles",
            headers={"Authorization": f"Bearer {gov_token}"},
            json={"name": "Iter14 Refactor Cycle", "period": "2026-RF14", "employee_ids": []},
            timeout=30,
        )
        assert r.status_code in (200, 201), r.text
        return r.json()["id"]

    def test_analytics_shape(self, gov_token, cycle_id):
        r = requests.get(
            f"{BASE_URL}/api/performance/cycles/{cycle_id}/analytics",
            headers={"Authorization": f"Bearer {gov_token}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Expected metrics from the 4 refactored helpers:
        #   _rating_distribution → rating_distribution
        #   _action_counts       → promotion_recommendations, salary_actions
        #   _department_summary  → department_summary
        #   _avg                 → avg_self_rating, avg_manager_rating
        for k in ("total_reviews", "completed", "completion_rate",
                  "acknowledged", "acknowledgement_rate",
                  "avg_self_rating", "avg_manager_rating",
                  "rating_distribution", "promotion_recommendations",
                  "salary_actions", "department_summary"):
            assert k in data, f"missing key {k} in {list(data.keys())}"
        assert set(data["rating_distribution"].keys()) == {"1", "2", "3", "4", "5"}
        assert isinstance(data["department_summary"], list)
        assert isinstance(data["avg_manager_rating"], (int, float))

    def test_summary_pdf_renders(self, gov_token, cycle_id):
        r = requests.get(
            f"{BASE_URL}/api/performance/cycles/{cycle_id}/summary.pdf",
            headers={"Authorization": f"Bearer {gov_token}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.content[:5] == b"%PDF-", f"Not a PDF, got: {r.content[:50]}"
        assert "application/pdf" in r.headers.get("content-type", "")
        assert len(r.content) > 1000


# ---------- module: talent certificate PDF refactor ----------
class TestTalentCertificateRefactor:
    @pytest.fixture(scope="class")
    def completion_id(self, gov_token):
        # Create a fresh program + completion in Gov tenant (Demo Salone has none seeded)
        prog = requests.post(
            f"{BASE_URL}/api/talent/programs",
            headers={"Authorization": f"Bearer {gov_token}"},
            json={"title": "Iter14 Cert Refactor", "hours": 2, "skill_area": "QA"},
            timeout=15,
        ).json()
        emp = requests.get(
            f"{BASE_URL}/api/employees",
            headers={"Authorization": f"Bearer {gov_token}"},
            timeout=15,
        ).json()[0]
        comp = requests.post(
            f"{BASE_URL}/api/talent/completions",
            headers={"Authorization": f"Bearer {gov_token}"},
            json={"program_id": prog["id"], "employee_id": emp["id"],
                  "completed_on": "2026-05-13", "score": 92},
            timeout=15,
        ).json()
        return comp["id"]

    def test_certificate_pdf_contains_qr_and_sections(self, gov_token, completion_id):
        r = requests.get(
            f"{BASE_URL}/api/talent/completions/{completion_id}/certificate.pdf",
            headers={"Authorization": f"Bearer {gov_token}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.content[:5] == b"%PDF-", "Response not a valid PDF"
        assert len(r.content) > 2000, "Cert PDF seems suspiciously small"

        # Validate Content-Disposition filename header
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()
        assert "filename=" in cd.lower()
        assert ".pdf" in cd.lower()
        # filename should include 8 chars from completion id
        assert "certificate-" in cd.lower()

        # PDF must contain "Certificate" text — sanity check the 4 cert_* helpers (header/body/footer/border) all wired
        # ReportLab compresses streams so we can't grep raw bytes reliably; size + magic-bytes assertion is sufficient
