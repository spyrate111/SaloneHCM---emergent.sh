"""Pre-payroll budget-check module — Option A anti-fraud guardrail.

Prevents Gov tenants from running payroll they cannot fund. Every run must pass
a projection against per-budget-code IFMIS allocations. Unsafe runs require an
explicit `mof_approver`/superadmin override with a text reason (audit-logged +
SMS-notified to all MoF approvers). Employees without a budget_code are hard-
blocked because unallocated headcount is the #1 ghost-worker vector.

Endpoints
---------
GET  /api/payroll-budget/balances?period=YYYY-MM         list balances for tenant
PUT  /api/payroll-budget/balances/{code}                 upsert allocation
POST /api/payroll-budget/check                           project + snapshot
GET  /api/payroll-budget/checks                          history of snapshots
GET  /api/payroll-budget/checks/{id}                     single snapshot detail

Verdicts
--------
- safe                   : every code within budget
- warn                   : any code within 10% of ceiling
- over                   : any code over-budget → run blocked without override
- unallocated_employees  : any active employee has no budget_code → hard block
"""
from __future__ import annotations
import os
import uuid
import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, tenant_filter, require_admin, require_feature, audit, now_utc, iso

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/payroll-budget",
    tags=["payroll-budget"],
    dependencies=[Depends(require_feature("gov_payroll"))],
)


# ---------- Models ----------

class BalanceIn(BaseModel):
    allocated_sle: float = Field(..., ge=0)
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    note: Optional[str] = None


class CheckIn(BaseModel):
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")


class OverrideIn(BaseModel):
    check_id: str
    reason: str = Field(..., min_length=20, max_length=1000)


# ---------- Balances ----------

@router.get("/balances")
async def list_balances(period: str, user: dict = Depends(require_admin)):
    if not period or len(period) != 7:
        raise HTTPException(422, "period must be YYYY-MM")
    tf = tenant_filter(user)
    rows = await db.budget_balances.find({**tf, "period": period}, {"_id": 0}).to_list(2000)
    total_alloc = round(sum(r.get("allocated_sle", 0) for r in rows), 2)
    return {"period": period, "balances": rows, "total_allocated_sle": total_alloc}


@router.put("/balances/{code}")
async def upsert_balance(code: str, body: BalanceIn, user: dict = Depends(require_admin)):
    if not code.strip():
        raise HTTPException(422, "budget code required")
    tf = tenant_filter(user)
    doc = {
        **tf,
        "budget_code": code.strip().upper(),
        "period": body.period,
        "allocated_sle": round(body.allocated_sle, 2),
        "note": body.note,
        "updated_at": iso(now_utc()),
        "updated_by": user["email"],
    }
    await db.budget_balances.update_one(
        {**tf, "budget_code": doc["budget_code"], "period": body.period},
        {"$set": doc, "$setOnInsert": {"created_at": iso(now_utc())}},
        upsert=True,
    )
    await audit("budget_balance_upsert", f"budget_balances/{doc['budget_code']}/{body.period}",
                user, {"allocated_sle": body.allocated_sle})
    return {"ok": True, "budget_code": doc["budget_code"], "period": body.period,
            "allocated_sle": body.allocated_sle}


# ---------- Check (projection) ----------

async def _project_by_budget_code(company_id: str, period: str) -> tuple[dict, list[dict], int]:
    """Return (projections_by_code, unallocated_slips, unallocated_headcount).
    projections_by_code[code] = {gross, headcount}
    """
    from payroll_engine import calc_payslip
    try:
        from routers.civil_service import get_active_allowance_amounts
    except Exception:
        get_active_allowance_amounts = None

    emps = await db.employees.find(
        {"status": "active", "company_id": company_id}, {"_id": 0},
    ).to_list(5000)

    by_code: dict[str, dict] = defaultdict(lambda: {"gross": 0.0, "headcount": 0})
    unallocated_slips: list[dict] = []
    for e in emps:
        try:
            breakdown = await get_active_allowance_amounts(e, company_id, period) if get_active_allowance_amounts else {}
            slip = calc_payslip(e, allowance_breakdown=breakdown)
        except Exception:
            slip = calc_payslip(e)
        code = (e.get("budget_code") or "").strip().upper()
        if not code:
            unallocated_slips.append({
                "employee_id": e["id"],
                "name": f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
                "gross": slip["gross"],
            })
            continue
        by_code[code]["gross"] += slip["gross"]
        by_code[code]["headcount"] += 1
    for k in by_code:
        by_code[k]["gross"] = round(by_code[k]["gross"], 2)
    return by_code, unallocated_slips, len(unallocated_slips)


async def _spent_prior_by_code(company_id: str, period: str) -> dict[str, float]:
    """Compute prior spend for the period from any existing (completed) runs.
    Handles the case where a payroll was already run once and a re-run is being planned."""
    prior_runs = await db.payroll_runs.find(
        {"company_id": company_id, "period": period, "status": "completed"},
        {"_id": 0, "slips.budget_code": 1, "slips.gross": 1},
    ).to_list(50)
    spent: dict[str, float] = defaultdict(float)
    for r in prior_runs:
        for s in r.get("slips", []):
            code = (s.get("budget_code") or "").strip().upper()
            if code:
                spent[code] += float(s.get("gross") or 0)
    return {k: round(v, 2) for k, v in spent.items()}


def _verdict_row(code: str, projected: float, allocated: float, spent_prior: float, headcount: int) -> dict:
    total_needed = round(projected + spent_prior, 2)
    over_by = round(total_needed - allocated, 2) if allocated is not None else 0.0
    if allocated is None or allocated == 0:
        verdict = "over"
    elif total_needed > allocated:
        verdict = "over"
    elif total_needed >= allocated * 0.9:
        verdict = "warn"
    else:
        verdict = "safe"
    return {
        "budget_code": code,
        "headcount": headcount,
        "gross_projected_sle": projected,
        "spent_prior_sle": spent_prior,
        "total_needed_sle": total_needed,
        "allocated_sle": allocated or 0.0,
        "over_by_sle": max(0.0, over_by),
        "utilization_pct": round((total_needed / allocated * 100), 1) if allocated else None,
        "verdict": verdict,
    }


@router.post("/check")
async def run_budget_check(body: CheckIn, user: dict = Depends(require_admin)) -> dict:
    """Project current payroll gross by budget code and verdict against allocations.
    Persists a snapshot in `payroll_budget_checks` for audit."""
    tf = tenant_filter(user)
    company_id = user["company_id"]

    by_code, unallocated_slips, unallocated_headcount = await _project_by_budget_code(company_id, body.period)
    spent_prior = await _spent_prior_by_code(company_id, body.period)

    balances = await db.budget_balances.find({**tf, "period": body.period}, {"_id": 0}).to_list(2000)
    alloc_map = {b["budget_code"]: b["allocated_sle"] for b in balances}

    all_codes = sorted(set(by_code.keys()) | set(alloc_map.keys()))
    rows: list[dict] = []
    total_projected = 0.0
    total_allocated = 0.0
    worst = "safe"
    for code in all_codes:
        proj = by_code.get(code, {"gross": 0.0, "headcount": 0})
        row = _verdict_row(code, proj["gross"], alloc_map.get(code), spent_prior.get(code, 0.0), proj["headcount"])
        total_projected += row["gross_projected_sle"]
        total_allocated += row["allocated_sle"]
        if row["verdict"] == "over":
            worst = "over"
        elif row["verdict"] == "warn" and worst != "over":
            worst = "warn"
        rows.append(row)

    if unallocated_headcount > 0:
        worst = "unallocated_employees"

    check_id = str(uuid.uuid4())
    snapshot = {
        "id": check_id,
        **tf,
        "period": body.period,
        "ran_at": iso(now_utc()),
        "ran_by": user["email"],
        "verdict": worst,
        "totals": {
            "gross_projected_sle": round(total_projected, 2),
            "allocated_sle": round(total_allocated, 2),
            "codes_over": sum(1 for r in rows if r["verdict"] == "over"),
            "codes_warn": sum(1 for r in rows if r["verdict"] == "warn"),
            "unallocated_headcount": unallocated_headcount,
        },
        "by_code": rows,
        "unallocated_employees": unallocated_slips,
        "override": None,
        "run_id": None,
    }
    await db.payroll_budget_checks.insert_one(snapshot)
    await audit("payroll_budget_check", f"payroll_budget_checks/{check_id}", user,
                {"period": body.period, "verdict": worst,
                 "codes_over": snapshot["totals"]["codes_over"],
                 "unallocated_headcount": unallocated_headcount})
    snapshot.pop("_id", None)
    return snapshot


@router.get("/checks")
async def list_checks(period: Optional[str] = None, user: dict = Depends(require_admin)):
    q = tenant_filter(user)
    if period:
        q["period"] = period
    rows = await db.payroll_budget_checks.find(q, {"_id": 0, "unallocated_employees": 0}).sort("ran_at", -1).to_list(200)
    return rows


@router.get("/checks/{cid}")
async def get_check(cid: str, user: dict = Depends(require_admin)):
    doc = await db.payroll_budget_checks.find_one({"id": cid, **tenant_filter(user)}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "check not found")
    return doc


# ---------- Override (fraud-hardened) ----------

async def _notify_mof_approvers_of_override(company_id: str, check: dict, override: dict) -> None:
    """Fire-and-forget SMS to every MoF approver in the tenant. Never blocks the run."""
    try:
        approvers = await db.users.find(
            {"company_id": company_id, "mof_approver": True},
            {"_id": 0, "email": 1, "phone": 1},
        ).to_list(50)
        phones = [u["phone"] for u in approvers if u.get("phone")]
        if not phones:
            log.info("no MoF approvers with phone numbers — override SMS skipped")
            return
        from sms import send_one, normalize_phone
        msg = (f"SaloneHCM: Budget override applied for period {check['period']}. "
               f"By {override['by']}. Verdict was {check['verdict'].upper()}. "
               f"Reason: {override['reason'][:80]}")
        for p in phones:
            try:
                normalized = normalize_phone(p)
                if normalized:
                    await send_one(normalized, msg)
            except Exception as e:
                log.warning("MoF override SMS to %s failed: %s", p, e)
    except Exception as e:
        log.warning("override SMS notification pass failed: %s", e)


@router.post("/override")
async def apply_override(body: OverrideIn, user: dict = Depends(require_admin)):
    """Sign off on running payroll despite over-budget / unallocated verdict.
    Requires `mof_approver` role flag or superadmin. Reason must be ≥20 chars.
    Fires SMS to every MoF approver in the tenant."""
    is_super = user.get("role") == "superadmin"
    is_approver = bool(user.get("mof_approver"))
    if not (is_super or is_approver):
        raise HTTPException(403, "Only MoF approvers or superadmin can override a budget check")

    tf = tenant_filter(user)
    check = await db.payroll_budget_checks.find_one({"id": body.check_id, **tf}, {"_id": 0})
    if not check:
        raise HTTPException(404, "check not found")
    if check.get("override"):
        raise HTTPException(409, "This check has already been overridden")
    if check["verdict"] == "safe":
        raise HTTPException(422, "Safe checks do not require an override")

    override = {
        "by": user["email"],
        "role": user.get("role"),
        "mof_approver": is_approver,
        "reason": body.reason.strip(),
        "at": iso(now_utc()),
    }
    await db.payroll_budget_checks.update_one(
        {"id": body.check_id, **tf}, {"$set": {"override": override}},
    )
    await audit("payroll_budget_override", f"payroll_budget_checks/{body.check_id}",
                user, {"period": check["period"], "verdict_overridden": check["verdict"],
                       "reason_prefix": body.reason[:60]})
    check["override"] = override
    await _notify_mof_approvers_of_override(user["company_id"], check, override)
    return {"ok": True, "override": override}
