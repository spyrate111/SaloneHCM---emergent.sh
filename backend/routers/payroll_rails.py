"""Gov Payroll anti-fraud rails — Options C (retro-pay), D (multi-sig MoF), E (cutoff lock).

C — Retro-pay engine
    Tracks backdated grade/step/acting adjustments so employees whose owed
    amount grew in past periods get an `retro_arrears` line on the next
    payroll run. Fraud guardrail: adjustments > 10% of monthly gross require
    an mof_approver override before they can settle.

D — Multi-signature MoF approval
    Runs above a per-tenant threshold require N distinct MoF signatures
    before status flips to 'approved'. Prevents unilateral sign-off.

E — Payroll cutoff-day lock
    After the tenant's monthly cutoff day, all employee mutations (hire /
    terminate / salary change) are blocked until the current period's
    payroll is completed. Prevents last-minute ghost worker insertion.
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from core import db, tenant_filter, require_admin, require_feature, audit, iso, now_utc

log = logging.getLogger(__name__)


# ============================================================
# Option C — Retro-pay engine
# ============================================================

retro_router = APIRouter(
    prefix="/retro-pay",
    tags=["retro-pay"],
    dependencies=[Depends(require_feature("gov_payroll"))],
)


class RetroPayIn(BaseModel):
    employee_id: str
    monthly_delta_sle: float = Field(..., description="Monthly amount owed (positive) or clawed back (negative)")
    effective_from: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    effective_to: str = Field(..., pattern=r"^\d{4}-\d{2}$",
                              description="Inclusive last month to arrear across (usually the current period).")
    source: str = Field("manual", description="grade_change | step_increment | acting | manual")
    reason: str = Field(..., min_length=10, max_length=500)


class RetroPayApproval(BaseModel):
    id: str
    approve: bool
    note: Optional[str] = Field(default="", max_length=500)


def _months_between(a: str, b: str) -> int:
    """Inclusive month count between YYYY-MM strings a→b (b >= a)."""
    ay, am = int(a[:4]), int(a[5:7])
    by, bm = int(b[:4]), int(b[5:7])
    return max(0, (by - ay) * 12 + (bm - am) + 1)


@retro_router.get("")
async def list_retro_pay(status: Optional[str] = None,
                         employee_id: Optional[str] = None,
                         user: dict = Depends(require_admin)):
    q = tenant_filter(user)
    if status:
        q["status"] = status
    if employee_id:
        q["employee_id"] = employee_id
    rows = await db.retro_pay_adjustments.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return rows


@retro_router.post("")
async def create_retro_pay(body: RetroPayIn, user: dict = Depends(require_admin)):
    emp = await db.employees.find_one({"id": body.employee_id, "company_id": user["company_id"]}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")
    if body.effective_from > body.effective_to:
        raise HTTPException(422, "effective_from must be ≤ effective_to")

    months = _months_between(body.effective_from, body.effective_to)
    total = round(body.monthly_delta_sle * months, 2)
    basic = float(emp.get("basic_salary_sle") or emp.get("base_salary_sle") or 0)
    ratio_pct = round((abs(total) / basic * 100) if basic else 0, 1)
    # Fraud gate: > 10% of monthly gross requires MoF approval.
    high_value = ratio_pct >= 10

    rid = str(uuid.uuid4())
    doc = {
        "id": rid,
        "company_id": user["company_id"],
        "employee_id": body.employee_id,
        "employee_name": f"{emp.get('first_name','')} {emp.get('last_name','')}".strip(),
        "monthly_delta_sle": body.monthly_delta_sle,
        "months": months,
        "total_owed_sle": total,
        "effective_from": body.effective_from,
        "effective_to": body.effective_to,
        "source": body.source,
        "reason": body.reason,
        "ratio_pct": ratio_pct,
        "requires_mof_approval": high_value,
        "status": "pending_approval" if high_value else "pending",
        "created_by": user["email"],
        "created_at": iso(now_utc()),
        "settled_run_id": None,
    }
    await db.retro_pay_adjustments.insert_one(doc)
    await audit("retro_pay_create", f"retro_pay_adjustments/{rid}", user,
                {"employee_id": body.employee_id, "total": total, "high_value": high_value})
    doc.pop("_id", None)
    return doc


@retro_router.post("/{rid}/approve")
async def approve_retro_pay(rid: str, body: RetroPayApproval, user: dict = Depends(require_admin)):
    if user["role"] != "superadmin" and not user.get("mof_approver"):
        raise HTTPException(403, "Only MoF approvers can approve retro-pay adjustments")
    tf = tenant_filter(user)
    doc = await db.retro_pay_adjustments.find_one({"id": rid, **tf}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Retro-pay adjustment not found")
    if doc["status"] not in ("pending", "pending_approval"):
        raise HTTPException(409, f"Cannot approve — status is {doc['status']}")
    new_status = "pending" if body.approve else "rejected"
    await db.retro_pay_adjustments.update_one(
        {"id": rid, **tf},
        {"$set": {
            "status": new_status,
            "approved_by": user["email"],
            "approved_at": iso(now_utc()),
            "approval_note": body.note,
        }},
    )
    await audit("retro_pay_approval", f"retro_pay_adjustments/{rid}", user,
                {"approve": body.approve, "employee_id": doc["employee_id"]})
    return {"ok": True, "status": new_status}


@retro_router.delete("/{rid}")
async def delete_retro_pay(rid: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    doc = await db.retro_pay_adjustments.find_one({"id": rid, **tf}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    if doc.get("status") == "settled":
        raise HTTPException(409, "Cannot delete settled adjustments — historical audit record")
    await db.retro_pay_adjustments.delete_one({"id": rid, **tf})
    await audit("retro_pay_delete", f"retro_pay_adjustments/{rid}", user, {})
    return {"ok": True}


async def settle_pending_retros_for_run(run_id: str, period: str, company_id: str) -> dict:
    """Called by payroll_engine after a successful run: mark applicable retros
    as settled and stamp settled_run_id. Returns count of settled + sum owed."""
    q = {
        "company_id": company_id,
        "status": "pending",
        "effective_to": {"$lte": period},
    }
    docs = await db.retro_pay_adjustments.find(q, {"_id": 0}).to_list(500)
    if not docs:
        return {"settled": 0, "total_sle": 0}
    ids = [d["id"] for d in docs]
    total = sum(d["total_owed_sle"] for d in docs)
    await db.retro_pay_adjustments.update_many(
        {"company_id": company_id, "id": {"$in": ids}},
        {"$set": {"status": "settled", "settled_run_id": run_id,
                  "settled_at": iso(now_utc())}},
    )
    log.info("[retro] settled %d rows against run %s (SLE %.2f)", len(docs), run_id, total)
    return {"settled": len(docs), "total_sle": round(total, 2)}


# ============================================================
# Option D — Multi-signature MoF approval
# ============================================================

signatures_router = APIRouter(
    prefix="/mof",
    tags=["mof-signatures"],
    dependencies=[Depends(require_feature("mof_approval"))],
)


class SigConfig(BaseModel):
    signatures_required: int = Field(..., ge=1, le=5,
                                     description="Number of distinct MoF approvers required to approve a run.")


@signatures_router.get("/config")
async def get_mof_config(user: dict = Depends(require_admin)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0, "mof_signatures_required": 1})
    return {"signatures_required": (company or {}).get("mof_signatures_required", 1)}


@signatures_router.put("/config")
async def set_mof_config(body: SigConfig, user: dict = Depends(require_admin)):
    if user["role"] != "superadmin":
        raise HTTPException(403, "Only superadmin can change MoF signature requirements")
    await db.companies.update_one(
        {"id": user["company_id"]},
        {"$set": {"mof_signatures_required": body.signatures_required}},
    )
    await audit("mof_config_set", f"companies/{user['company_id']}", user,
                {"signatures_required": body.signatures_required})
    return {"ok": True, "signatures_required": body.signatures_required}


@signatures_router.get("/runs/{run_id}/signatures")
async def list_signatures(run_id: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    run = await db.payroll_runs.find_one({"id": run_id, **tf}, {"_id": 0, "mof_signatures": 1, "mof_status": 1})
    if not run:
        raise HTTPException(404, "Run not found")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0, "mof_signatures_required": 1})
    return {
        "signatures": run.get("mof_signatures", []),
        "signatures_required": (company or {}).get("mof_signatures_required", 1),
        "mof_status": run.get("mof_status", "draft"),
    }


class SignAction(BaseModel):
    action: str = Field(..., pattern=r"^(approve|reject)$")
    note: Optional[str] = Field(default="", max_length=500)


async def _validate_signing(run_id: str, user: dict) -> dict:
    """Permission + state checks; returns the run or raises."""
    if user["role"] != "superadmin" and not user.get("mof_approver"):
        raise HTTPException(403, "Only MoF approvers can sign")
    run = await db.payroll_runs.find_one({"id": run_id, **tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("mof_status") not in ("submitted", "partially_signed"):
        raise HTTPException(409, f"Run must be 'submitted' — current status: {run.get('mof_status', 'draft')}")
    if any(s["signer_email"] == user["email"] for s in run.get("mof_signatures", [])):
        raise HTTPException(409, "You have already signed this run")
    return run


def _resolve_sign_status(sigs: list, required: int, user: dict) -> tuple[str, dict]:
    """Derive the new mof_status + status-stamp fields from the signature set."""
    approves = sum(1 for s in sigs if s["action"] == "approve")
    rejects = sum(1 for s in sigs if s["action"] == "reject")
    if rejects > 0:
        new_status = "rejected"
    elif approves >= required:
        new_status = "approved"
    else:
        new_status = "partially_signed"
    stamps = {}
    if new_status == "approved":
        stamps = {"mof_approved_by": user["email"], "mof_approved_at": iso(now_utc())}
    elif new_status == "rejected":
        stamps = {"mof_rejected_by": user["email"], "mof_rejected_at": iso(now_utc())}
    return new_status, {"approves": approves, "rejects": rejects, **stamps}


@signatures_router.post("/runs/{run_id}/sign")
async def sign_run(run_id: str, body: SignAction, user: dict = Depends(require_admin)):
    """Record one signature. When count of approves ≥ signatures_required → run flips to 'approved'.
    Any reject immediately flips to 'rejected'. An approver cannot sign the same run twice."""
    run = await _validate_signing(run_id, user)

    sigs = list(run.get("mof_signatures", []))
    sigs.append({
        "id": str(uuid.uuid4()),
        "signer_email": user["email"],
        "signer_role": user.get("role"),
        "signer_name": user.get("name"),
        "action": body.action,
        "note": body.note,
        "signed_at": iso(now_utc()),
    })

    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0, "mof_signatures_required": 1})
    required = (company or {}).get("mof_signatures_required", 1)
    new_status, meta = _resolve_sign_status(sigs, required, user)
    approves, rejects = meta.pop("approves"), meta.pop("rejects")

    await db.payroll_runs.update_one(
        {"id": run_id, **tenant_filter(user)},
        {"$set": {"mof_signatures": sigs, "mof_status": new_status, **meta}})
    await audit(f"mof_sign_{body.action}", f"payroll_runs/{run_id}", user,
                {"period": run["period"], "approves": approves, "required": required, "new_status": new_status})
    return {
        "ok": True,
        "mof_status": new_status,
        "signatures": sigs,
        "signatures_required": required,
        "approves": approves,
        "rejects": rejects,
    }


# ============================================================
# Option E — Payroll cutoff-day lock
# ============================================================

cutoff_router = APIRouter(prefix="/cutoff", tags=["payroll-cutoff"])


class CutoffConfig(BaseModel):
    payroll_cutoff_day: int = Field(..., ge=1, le=28,
                                    description="Day of month after which employee mutations are locked until the run is completed. 1-28.")
    enabled: bool = True


@cutoff_router.get("/config")
async def get_cutoff_config(user: dict = Depends(require_admin)):
    company = await db.companies.find_one(
        {"id": user["company_id"]},
        {"_id": 0, "payroll_cutoff_day": 1, "payroll_cutoff_enabled": 1},
    )
    return {
        "payroll_cutoff_day": (company or {}).get("payroll_cutoff_day", 25),
        "enabled": (company or {}).get("payroll_cutoff_enabled", False),
    }


@cutoff_router.put("/config")
async def set_cutoff_config(body: CutoffConfig, user: dict = Depends(require_admin)):
    await db.companies.update_one(
        {"id": user["company_id"]},
        {"$set": {
            "payroll_cutoff_day": body.payroll_cutoff_day,
            "payroll_cutoff_enabled": body.enabled,
        }},
    )
    await audit("cutoff_config_set", f"companies/{user['company_id']}", user,
                {"day": body.payroll_cutoff_day, "enabled": body.enabled})
    return {"ok": True, "payroll_cutoff_day": body.payroll_cutoff_day, "enabled": body.enabled}


@cutoff_router.get("/status")
async def get_cutoff_status(user: dict = Depends(require_admin)):
    """Current lock status — used by the frontend banner + before-mutation checks."""
    company = await db.companies.find_one(
        {"id": user["company_id"]},
        {"_id": 0, "payroll_cutoff_day": 1, "payroll_cutoff_enabled": 1},
    )
    if not company or not company.get("payroll_cutoff_enabled"):
        return {"locked": False, "reason": "cutoff not enabled"}

    day = company.get("payroll_cutoff_day", 25)
    today = datetime.now(timezone.utc)
    period = f"{today.year}-{today.month:02d}"

    if today.day < day:
        return {"locked": False, "reason": f"today ({today.day}) is before cutoff ({day})"}

    completed = await db.payroll_runs.find_one(
        {"company_id": user["company_id"], "period": period, "status": {"$in": ["completed", "released"]}},
        {"_id": 0, "id": 1},
    )
    if completed:
        return {"locked": False, "reason": f"payroll for {period} already completed", "period": period}

    return {
        "locked": True,
        "reason": f"payroll cutoff — {period} run not yet completed",
        "period": period,
        "cutoff_day": day,
    }


async def assert_not_cutoff_locked(user: dict, action: str) -> None:
    """Raise 423 Locked if the tenant is in a payroll-cutoff window and the
    action is a mutating one. Superadmin bypasses. Called from mutation routes."""
    if user["role"] == "superadmin":
        return
    status = await get_cutoff_status(user)
    if status.get("locked"):
        raise HTTPException(423, {
            "code": "payroll_cutoff_locked",
            "message": f"Blocked — {action} is locked until the {status['period']} payroll run is completed. Contact a superadmin to override.",
            "cutoff_day": status.get("cutoff_day"),
            "period": status.get("period"),
        })
