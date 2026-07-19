"""iter33 — Voucher deadline nudges + MoF pack cover sign-off block."""
import io
import os
import secrets
import time

import pytest
import requests

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

API = os.environ.get("API_BASE_URL", "http://localhost:8001/api")
GOV_EMAIL, GOV_PASS = "admin@gov.sl", "GovAdmin@2026"
SUP_EMAIL, SUP_PASS = "adama.sankoh@gov.sl", "Employee@2026"


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
def sup_token():
    return _login(SUP_EMAIL, SUP_PASS)


@pytest.fixture(scope="module")
def mof_branch(gov_token):
    branches = requests.get(f"{API}/branches", headers=_h(gov_token), timeout=15).json()
    return next(b for b in branches if b["code"] == "MOF-HQ")


# ============================================================
# Nudge endpoints
# ============================================================

class TestVoucherNudge:
    def test_manual_send_nudge_smoke(self, gov_token):
        # Manual send-now for a period with no submissions -> should return sent count
        period = f"20{40 + secrets.randbelow(50)}-{1 + secrets.randbelow(12):02d}"
        r = requests.post(f"{API}/vouchers/nudge/send-now?period={period}",
                          headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        payload = r.json()
        assert payload["ok"] is True
        assert payload["period"] == period
        assert payload["window"] == "manual"
        assert isinstance(payload.get("results"), list)
        assert payload["sent"] == len(payload["results"])  # since no submissions

    def test_idempotent_manual_nudge(self, gov_token):
        # Second call for the same period+window should return "already_sent" for all rows
        period = f"20{40 + secrets.randbelow(50)}-{1 + secrets.randbelow(12):02d}"
        r1 = requests.post(f"{API}/vouchers/nudge/send-now?period={period}",
                           headers=_h(gov_token), timeout=15)
        r2 = requests.post(f"{API}/vouchers/nudge/send-now?period={period}",
                           headers=_h(gov_token), timeout=15)
        assert r1.status_code == r2.status_code == 200
        # Second call must all be "already_sent"
        assert all(row["status"] == "already_sent" for row in r2.json()["results"])
        assert r2.json()["sent"] == 0

    def test_nudge_history_visible_to_finance(self, gov_token, sup_token):
        # Ensure at least one nudge exists
        period = f"20{40 + secrets.randbelow(50)}-{1 + secrets.randbelow(12):02d}"
        requests.post(f"{API}/vouchers/nudge/send-now?period={period}",
                      headers=_h(gov_token), timeout=15)
        r = requests.get(f"{API}/vouchers/nudge/history", headers=_h(gov_token), timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        assert any(rw["period"] == period for rw in rows)

    def test_nudge_history_forbidden_for_plain_employee(self):
        emp_tok = _login("joseph.williams@gov.sl", "Employee@2026")
        r = requests.get(f"{API}/vouchers/nudge/history", headers=_h(emp_tok), timeout=15)
        # Plain employee (not finance_officer, not admin, not mof_approver) is 403
        assert r.status_code == 403

    def test_nudge_manual_requires_admin(self):
        emp_tok = _login("joseph.williams@gov.sl", "Employee@2026")
        r = requests.post(f"{API}/vouchers/nudge/send-now", headers=_h(emp_tok), timeout=15)
        assert r.status_code == 403


# ============================================================
# MoF pack cover sign-off block
# ============================================================

@pytest.mark.skipif(PdfReader is None, reason="pypdf not installed")
class TestPackCoverSignOff:
    def test_cover_page_contains_minister_signoff(self, gov_token, mof_branch):
        """Full workflow: create → submit → approve → authorize a voucher, then
        request the batch PDF and confirm the Minister sign-off block is on
        the cover page."""
        # unique period
        period = f"20{55 + secrets.randbelow(30)}-{1 + secrets.randbelow(12):02d}"
        # find an employee attached to the MOF-HQ branch
        emps = requests.get(f"{API}/branches/{mof_branch['id']}/employees",
                            headers=_h(gov_token), timeout=15).json()
        # accept any employee
        emp = emps[0]
        # Build a minimal voucher payload
        body = {"branch_id": mof_branch["id"], "period": period,
                "line_items": [{"employee_id": emp["id"], "gross": 4000,
                                "paye": 200, "nassit_employee": 100,
                                "loan_deduction": 0, "net": 3700}]}
        r = requests.post(f"{API}/vouchers", headers=_h(gov_token), json=body, timeout=15)
        assert r.status_code == 200, r.text
        vid = r.json()["id"]

        # submit → supervisor_approve → start_review → approve → authorize
        # gov admin created it — supervisor is Adama; but admin can pass through
        # all stages except approve (segregation of duties) — so log in as
        # supervisor for that stage. Simpler: use two tokens.
        sup_tok = _login(SUP_EMAIL, SUP_PASS)
        # submit as sup (admin is creator, cannot approve own)
        # Wait — voucher was created by GOV admin. Then admin submits.
        assert requests.post(f"{API}/vouchers/{vid}/submit", headers=_h(gov_token),
                             json={"note": ""}, timeout=15).status_code == 200
        # supervisor approve
        assert requests.post(f"{API}/vouchers/{vid}/supervisor-approve",
                             headers=_h(sup_tok), json={"note": ""},
                             timeout=15).status_code == 200
        # finance officer needed for review/approve (not creator)
        fin_tok = _login("memuna.tucker@gov.sl", "Employee@2026")
        assert requests.post(f"{API}/vouchers/{vid}/start-review",
                             headers=_h(fin_tok), json={"note": ""},
                             timeout=15).status_code == 200
        assert requests.post(f"{API}/vouchers/{vid}/approve",
                             headers=_h(fin_tok), json={"note": ""},
                             timeout=15).status_code == 200
        # authorize (mof_approver = Adama, different from admin creator + Memuna approver)
        assert requests.post(f"{API}/vouchers/{vid}/authorize",
                             headers=_h(sup_tok), json={"note": ""},
                             timeout=15).status_code == 200

        # Fetch batch pdf
        time.sleep(0.5)
        pdf = requests.get(f"{API}/vouchers/export-batch.pdf?period={period}",
                           headers=_h(gov_token), timeout=15)
        assert pdf.status_code == 200
        reader = PdfReader(io.BytesIO(pdf.content))
        assert len(reader.pages) >= 2  # cover + at least one voucher
        cover_text = (reader.pages[0].extract_text() or "").lower()
        for keyword in ("mof payment pack",
                        "ministry of finance",
                        "minister of finance",
                        "full name",
                        "signature",
                        "official stamp",
                        "counter-sign"):
            assert keyword in cover_text, f"Missing '{keyword}' on cover page"


# ============================================================
# Frontend manifest reflects Temne when videos exist
# ============================================================

def test_manifest_endpoint_exposes_temne_when_ready():
    """Non-blocking smoke: if any Temne video was seeded, the marketing
    endpoint must expose lang='temne' entries with matching base_slug."""
    r = requests.get(f"{API}/marketing/videos?limit=60", timeout=15)
    assert r.status_code == 200
    vids = r.json()
    temne = [v for v in vids if (v.get("lang") == "temne")]
    if temne:
        english_slugs = {v.get("slug") for v in vids if (v.get("lang") or "en") == "en"}
        for tv in temne:
            assert tv.get("base_slug") in english_slugs
