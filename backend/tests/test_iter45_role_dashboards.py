"""iter45 — role-scoped dashboard data (/dashboard/role-summary) + /overview gating."""
import os
import time

import pytest
import requests

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")


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


def _summary(email, pw):
    tok = _login(email, pw)["token"]
    return requests.get(f"{API}/dashboard/role-summary", headers=_h(tok), timeout=15), tok


class TestRoleSummary:
    def test_superadmin_payload(self):
        r, _ = _summary("superadmin1@salonehcm.com", "Test@SuperAdmin1")
        assert r.status_code == 200
        b = r.json()
        assert b["role"] == "superadmin" and b["tenants"] >= 1 and b["platform_users"] >= 70

    def test_hr_payload_has_no_money(self):
        r, _ = _summary("hradmin1@salonehcm.com", "Test@HRAdmin1")
        assert r.status_code == 200
        b = r.json()
        assert b["role"] == "hr"
        for k in ("headcount", "pending_leaves", "on_leave_today", "punches_today", "departments"):
            assert k in b
        assert "monthly_payroll_sle" not in b and "runs_history" not in b

    def test_payroll_payload(self):
        r, _ = _summary("payroll1@salonehcm.com", "Test@Payroll1")
        assert r.status_code == 200
        b = r.json()
        assert b["role"] == "payroll"
        for k in ("monthly_payroll_sle", "runs_history", "outstanding_filings", "runs_total"):
            assert k in b
        assert "headcount" not in b

    def test_auditor_payload(self):
        r, _ = _summary("auditor1@salonehcm.com", "Test@Auditor1")
        assert r.status_code == 200
        b = r.json()
        assert b["role"] == "auditor"
        for k in ("audit_24h", "audit_total", "flagged_scans", "filings", "recent_audit"):
            assert k in b

    def test_manager_and_employee_403(self):
        for email, pw in (("manager1@salonehcm.com", "Test@Manager1"),
                          ("employee1@salonehcm.com", "Test@Employee1")):
            r, tok = _summary(email, pw)
            assert r.status_code == 403
            # they use /mobile/summary instead
            r2 = requests.get(f"{API}/mobile/summary", headers=_h(tok), timeout=15)
            assert r2.status_code == 200 and "todays_punches" in r2.json()


class TestOverviewGating:
    def test_admin_ok(self):
        tok = _login("admin1@salonehcm.com", "Test@Admin1")["token"]
        r = requests.get(f"{API}/dashboard/overview", headers=_h(tok), timeout=15)
        assert r.status_code == 200 and "monthly_payroll_sle" in r.json()

    def test_non_admin_roles_blocked(self):
        for email, pw in (("hradmin2@salonehcm.com", "Test@HRAdmin2"),
                          ("employee2@salonehcm.com", "Test@Employee2"),
                          ("auditor2@salonehcm.com", "Test@Auditor2")):
            tok = _login(email, pw)["token"]
            r = requests.get(f"{API}/dashboard/overview", headers=_h(tok), timeout=15)
            assert r.status_code == 403, email
