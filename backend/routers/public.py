"""Public read-only transparency endpoints — Gov-tier customers can opt-in to publish anonymised ministry rollups for the citizenry."""
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from core import db, require_admin, audit, now_utc, iso
from payroll_engine import calc_payslip

router = APIRouter(prefix="/public", tags=["public"])


# ===== Public read-only endpoints (no auth) =====
@router.get("/certificate/{cid}")
async def public_certificate_verify(cid: str):
    """Anyone can verify a Certificate ID — returns ONLY the data printed on the certificate.
    No PII beyond what the printed PDF already contains (employee name, program, completion date)."""
    completion = await db.training_completions.find_one({"id": cid}, {"_id": 0})
    if not completion:
        return {"valid": False, "reason": "not_found"}
    program = await db.training_programs.find_one({"id": completion["program_id"]}, {"_id": 0}) or {}
    employee = await db.employees.find_one({"id": completion["employee_id"]}, {"_id": 0}) or {}
    company = await db.companies.find_one({"id": completion.get("company_id")}, {"_id": 0}) or {}
    return {
        "valid": True,
        "certificate_id": cid,
        "employee_name": f"{employee.get('first_name','')} {employee.get('last_name','')}".strip() or "—",
        "program_title": program.get("title") or "—",
        "skill_area": program.get("skill_area") or "—",
        "hours": program.get("hours") or 0,
        "score": completion.get("score"),
        "completed_on": completion.get("completed_on"),
        "issued_by": company.get("name") or "SaloneHCM",
    }


async def _log_transparency_view(company: dict, slug: str, request: Request) -> None:
    """Best-effort audit trail — never blocks the response."""
    try:
        await db.transparency_views.insert_one({
            "company_id": company["id"],
            "slug": slug,
            "ip_prefix": (request.client.host if request.client else "?").rsplit(".", 1)[0] + ".x",
            "ts": iso(now_utc()),
        })
    except Exception:
        pass


def _aggregate_ministries(employees: list[dict]) -> list[dict]:
    """Group active employees by department → anonymised ministry rollup."""
    by_ministry: dict[str, dict] = defaultdict(lambda: {
        "name": "",
        "headcount": 0,
        "monthly_gross_sle": 0.0,
        "monthly_paye_sle": 0.0,
        "monthly_nassit_sle": 0.0,
    })
    for e in employees:
        m = by_ministry[e["department"]]
        m["name"] = e["department"]
        m["headcount"] += 1
        slip = calc_payslip(e)
        m["monthly_gross_sle"] += slip["gross"]
        m["monthly_paye_sle"] += slip["paye"]
        m["monthly_nassit_sle"] += slip["nassit_employee"] + slip["nassit_employer"]
    rows = sorted(by_ministry.values(), key=lambda r: -r["monthly_gross_sle"])
    for r in rows:
        r["monthly_gross_sle"] = round(r["monthly_gross_sle"], 2)
        r["monthly_paye_sle"] = round(r["monthly_paye_sle"], 2)
        r["monthly_nassit_sle"] = round(r["monthly_nassit_sle"], 2)
    return rows


async def _last_payroll_and_compliance(company_id: str) -> tuple[Optional[dict], int, Optional[str]]:
    """Return (last_run_summary_or_None, filings_count, most_recent_filing_period_or_None)."""
    runs = await db.payroll_runs.find(
        {"company_id": company_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(12)
    last = runs[0] if runs else None
    last_summary = {"period": last["period"], "ran_at": last["created_at"]} if last else None

    filings = await db.nra_filings.find(
        {"company_id": company_id}, {"_id": 0}
    ).sort("filed_at", -1).to_list(12)
    return last_summary, len(filings), (filings[0]["period"] if filings else None)


@router.get("/transparency/{slug}")
async def public_transparency(slug: str, request: Request):
    """Anonymised ministry payroll rollup — no auth required.

    Returns ZERO personally identifiable information. Aggregated counts and gross totals only.
    Companies must explicitly opt-in via /transparency/settings before they appear here.
    """
    company = await db.companies.find_one(
        {"transparency_slug": slug.lower().strip(), "transparency_public": True},
        {"_id": 0},
    )
    if not company:
        raise HTTPException(404, "No public transparency portal for this slug")

    await _log_transparency_view(company, slug, request)

    employees = await db.employees.find(
        {"company_id": company["id"], "status": "active"},
        {"_id": 0},
    ).to_list(5000)
    rows = _aggregate_ministries(employees)
    last_payroll, filings_count, most_recent_filing = await _last_payroll_and_compliance(company["id"])

    return {
        "organization": {
            "name": company["name"],
            "country": company.get("country", "Sierra Leone"),
            "tier_label": company.get("label"),
            "published_at": company.get("transparency_published_at"),
        },
        "as_of": iso(now_utc()),
        "totals": {
            "ministries": len(rows),
            "headcount": sum(r["headcount"] for r in rows),
            "monthly_gross_sle": round(sum(r["monthly_gross_sle"] for r in rows), 2),
            "monthly_paye_sle": round(sum(r["monthly_paye_sle"] for r in rows), 2),
            "monthly_nassit_sle": round(sum(r["monthly_nassit_sle"] for r in rows), 2),
        },
        "ministries": rows,
        "last_payroll": last_payroll,
        "compliance": {
            "returns_filed_12m": filings_count,
            "most_recent_filing": most_recent_filing,
        },
    }


# ===== Admin: opt-in & manage =====
class TransparencyToggleIn(BaseModel):
    enabled: bool
    slug: Optional[str] = None


@router.get("/transparency/admin/status")
async def my_transparency_status(user: dict = Depends(require_admin)):
    c = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    return {
        "enabled": bool(c.get("transparency_public")),
        "slug": c.get("transparency_slug"),
        "published_at": c.get("transparency_published_at"),
        "public_url": (
            f"/transparency/{c['transparency_slug']}"
            if c.get("transparency_slug") else None
        ),
    }


def _make_slug(name: str) -> str:
    raw = "".join(c if c.isalnum() else "-" for c in (name or "").lower()).strip("-")
    # collapse repeated hyphens
    while "--" in raw:
        raw = raw.replace("--", "-")
    return raw[:60]


@router.post("/transparency/admin/toggle")
async def toggle_transparency(body: TransparencyToggleIn, user: dict = Depends(require_admin)):
    c = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Company not found")
    if body.slug and body.slug.strip():
        desired_slug = _make_slug(body.slug)
        if not desired_slug:
            raise HTTPException(400, "Slug must contain at least one alphanumeric character")
    else:
        desired_slug = c.get("transparency_slug") or _make_slug(c["name"]) or "company"
    # uniqueness check
    if body.enabled:
        clash = await db.companies.find_one(
            {"transparency_slug": desired_slug, "id": {"$ne": c["id"]}},
            {"_id": 0, "id": 1},
        )
        if clash:
            raise HTTPException(409, f"Slug '{desired_slug}' already taken — pick another")

    updates = {
        "transparency_public": body.enabled,
        "transparency_slug": desired_slug,
        "transparency_published_at": iso(now_utc()) if body.enabled else c.get("transparency_published_at"),
    }
    await db.companies.update_one({"id": c["id"]}, {"$set": updates})
    await audit(
        "transparency_enable" if body.enabled else "transparency_disable",
        f"companies/{c['id']}", user,
        {"slug": desired_slug},
    )
    return {**updates, "public_url": f"/transparency/{desired_slug}"}


@router.get("/transparency/admin/views")
async def view_count(user: dict = Depends(require_admin)):
    """How many citizens have viewed the public portal."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    total = await db.transparency_views.count_documents({"company_id": user["company_id"]})
    last7 = await db.transparency_views.count_documents({
        "company_id": user["company_id"],
        "ts": {"$gte": cutoff},
    })
    return {"total_views": total, "last_7d": last7}
