"""Promotion Eligibility Tracker — pairs Civil Service step structure with Performance reviews.

A civil servant is eligible for promotion when:
  1. They have at least 12 months in their current step (tenure rule)
  2. Their last completed performance review has manager_rating >= threshold (default 4/5)
  3. Their grade has a next step available
  4. No active disciplinary action exists (we check `disciplinary_action` field)

The tracker surfaces eligible employees + provides a one-click "Recommend" action that
creates a `step_promotion_recommendations` record. MoF approver can then approve →
auto-bumps the employee to next step. Audit-trailed end to end.

Tier-gated behind `civil_service` (gov only — promotion semantics are SL civil-service).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import (
    db, get_current_user, require_admin, require_feature,
    tenant_filter, with_tenant, audit, now_utc, iso,
)

router = APIRouter(
    prefix="/promotion",
    tags=["promotion"],
    dependencies=[Depends(require_feature("civil_service"))],
)

# Configurable thresholds
DEFAULT_MIN_TENURE_DAYS = 365
DEFAULT_MIN_RATING = 4.0


def _months_since(iso_ts: str) -> int:
    if not iso_ts:
        return 0
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return (now_utc() - dt).days // 30
    except Exception:
        return 0


async def _last_review_rating(employee_id: str, company_id: str) -> tuple[float, str]:
    """Return (rating, period) of the most recent completed review."""
    row = await db.performance_reviews_v2.find_one(
        {"company_id": company_id, "employee_id": employee_id, "status": "completed",
         "manager_rating": {"$exists": True}},
        {"_id": 0, "manager_rating": 1, "cycle_id": 1},
        sort=[("created_at", -1)],
    )
    if not row:
        return 0.0, ""
    return float(row.get("manager_rating", 0)), row.get("cycle_id", "")


async def _next_step_for(grade_code: str, current_step: int, company_id: str) -> Optional[int]:
    """Return the step_number AFTER current_step if defined; else None."""
    if not grade_code or not current_step:
        return None
    nxt = await db.civil_service_steps.find_one(
        {"company_id": company_id, "grade_code": grade_code,
         "step_number": {"$gt": current_step}},
        sort=[("step_number", 1)], projection={"_id": 0, "step_number": 1},
    )
    return nxt["step_number"] if nxt else None


async def _eligibility_for(emp: dict, company_id: str, *,
                           min_tenure_days: int = DEFAULT_MIN_TENURE_DAYS,
                           min_rating: float = DEFAULT_MIN_RATING) -> dict:
    """Compute eligibility + reasons."""
    reasons: list[str] = []
    eligible = True

    # 1. Tenure
    last_step_change = emp.get("last_step_increment_at") or emp.get("hire_date") or emp.get("created_at")
    tenure_days = 0
    if last_step_change:
        try:
            dt = datetime.fromisoformat(last_step_change.replace("Z", "+00:00"))
            tenure_days = (now_utc() - dt).days
        except Exception:
            pass
    if tenure_days < min_tenure_days:
        eligible = False
        reasons.append(f"Tenure {tenure_days}d < {min_tenure_days}d")

    # 2. Performance
    rating, cycle = await _last_review_rating(emp["id"], company_id)
    if rating < min_rating:
        eligible = False
        reasons.append(f"Last rating {rating} < {min_rating}" if rating else "No completed review")

    # 3. Next step exists
    grade = emp.get("grade_code")
    cur_step = emp.get("step_number") or 1
    next_step = await _next_step_for(grade, cur_step, company_id)
    if next_step is None:
        eligible = False
        reasons.append(f"No step beyond {cur_step} for {grade or 'unset'}")

    # 4. No active disciplinary
    if emp.get("disciplinary_action") == "active":
        eligible = False
        reasons.append("Active disciplinary action")

    return {
        "employee_id": emp["id"],
        "name": f"{emp.get('first_name','')} {emp.get('last_name','')}".strip(),
        "grade_code": grade,
        "current_step": cur_step,
        "next_step": next_step,
        "tenure_days": tenure_days,
        "last_rating": rating,
        "last_cycle_id": cycle,
        "eligible": eligible,
        "reasons": reasons,
        "department": emp.get("department"),
        "mda_ministry": emp.get("mda_ministry"),
    }


# ---------- Endpoints ----------

class RecommendIn(BaseModel):
    employee_id: str = Field(..., min_length=1)
    notes: Optional[str] = Field("", max_length=500)


class ApproveIn(BaseModel):
    note: Optional[str] = Field("", max_length=500)


@router.get("/eligible")
async def list_eligible(user: dict = Depends(require_admin),
                        min_tenure_days: int = DEFAULT_MIN_TENURE_DAYS,
                        min_rating: float = DEFAULT_MIN_RATING):
    """List all employees with their eligibility status + reasons. Filter on the frontend."""
    tf = tenant_filter(user)
    employees = await db.employees.find(
        {**tf, "status": "active", "grade_code": {"$exists": True}}, {"_id": 0},
    ).to_list(5000)
    rows = []
    for e in employees:
        rows.append(await _eligibility_for(e, user["company_id"],
                                           min_tenure_days=min_tenure_days,
                                           min_rating=min_rating))
    rows.sort(key=lambda r: (not r["eligible"], -r["last_rating"], r["name"]))
    return {
        "rows": rows,
        "eligible_count": sum(1 for r in rows if r["eligible"]),
        "thresholds": {"min_tenure_days": min_tenure_days, "min_rating": min_rating},
    }


@router.post("/recommendations", status_code=201)
async def create_recommendation(body: RecommendIn, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    emp = await db.employees.find_one({"id": body.employee_id, **tf}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")
    # Re-check eligibility server-side
    elig = await _eligibility_for(emp, user["company_id"])
    if not elig["eligible"]:
        raise HTTPException(409, f"Employee not eligible: {', '.join(elig['reasons'])}")
    # Refuse if an open recommendation already exists
    existing = await db.step_promotion_recommendations.find_one(
        {"employee_id": body.employee_id, "status": "pending", **tf}, {"_id": 0, "id": 1},
    )
    if existing:
        raise HTTPException(409, f"Open recommendation already exists: {existing['id']}")
    rid = str(uuid.uuid4())
    doc = with_tenant({
        "id": rid,
        "employee_id": body.employee_id,
        "employee_name": elig["name"],
        "from_step": elig["current_step"],
        "to_step": elig["next_step"],
        "grade_code": elig["grade_code"],
        "department": emp.get("department"),
        "mda_ministry": emp.get("mda_ministry"),
        "last_rating": elig["last_rating"],
        "tenure_days": elig["tenure_days"],
        "notes": body.notes,
        "status": "pending",
        "recommended_by": user["email"],
        "recommended_at": iso(now_utc()),
    }, user)
    await db.step_promotion_recommendations.insert_one(doc)
    await audit("promotion_recommend", f"step_promotion_recommendations/{rid}", user, {
        "employee_id": body.employee_id, "from": elig["current_step"], "to": elig["next_step"],
    })
    return {k: v for k, v in doc.items() if k != "_id"}


@router.get("/recommendations")
async def list_recommendations(user: dict = Depends(require_admin),
                               status: Optional[str] = None):
    tf = tenant_filter(user)
    q = {**tf}
    if status:
        q["status"] = status
    return await db.step_promotion_recommendations.find(q, {"_id": 0}).sort("recommended_at", -1).to_list(500)


@router.post("/recommendations/{rid}/approve")
async def approve_recommendation(rid: str, body: ApproveIn, user: dict = Depends(require_admin)):
    """Admin/MoF approver: apply the step promotion + flip recommendation to approved."""
    tf = tenant_filter(user)
    if not (user.get("mof_approver") or user.get("role") == "superadmin"):
        raise HTTPException(403, "MoF approver flag required")
    rec = await db.step_promotion_recommendations.find_one({"id": rid, **tf}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Recommendation not found")
    if rec["status"] != "pending":
        raise HTTPException(409, f"Already {rec['status']}")
    # Look up next step's salary
    step_doc = await db.civil_service_steps.find_one(
        {"company_id": user["company_id"], "grade_code": rec["grade_code"],
         "step_number": rec["to_step"]},
        {"_id": 0, "monthly_amount_sle": 1},
    )
    new_basic = step_doc["monthly_amount_sle"] if step_doc else None
    ts = iso(now_utc())
    set_doc = {
        "step_number": rec["to_step"],
        "last_step_increment_at": ts,
        "updated_at": ts,
    }
    if new_basic is not None:
        set_doc["basic_salary_sle"] = float(new_basic)
    await db.employees.update_one({"id": rec["employee_id"], **tf}, {"$set": set_doc})
    await db.step_promotion_recommendations.update_one(
        {"id": rid, **tf},
        {"$set": {
            "status": "approved",
            "approved_by": user["email"],
            "approved_at": ts,
            "approval_note": body.note,
            "applied_basic_salary_sle": new_basic,
        }},
    )
    await audit("promotion_approve", f"step_promotion_recommendations/{rid}", user, {
        "employee_id": rec["employee_id"], "from": rec["from_step"], "to": rec["to_step"],
        "new_basic_sle": new_basic,
    })
    return {"ok": True, "applied_basic_sle": new_basic, "new_step": rec["to_step"]}


@router.post("/recommendations/{rid}/reject")
async def reject_recommendation(rid: str, body: ApproveIn, user: dict = Depends(require_admin)):
    if not (user.get("mof_approver") or user.get("role") == "superadmin"):
        raise HTTPException(403, "MoF approver flag required")
    tf = tenant_filter(user)
    rec = await db.step_promotion_recommendations.find_one({"id": rid, **tf}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Recommendation not found")
    if rec["status"] != "pending":
        raise HTTPException(409, f"Already {rec['status']}")
    await db.step_promotion_recommendations.update_one(
        {"id": rid, **tf},
        {"$set": {
            "status": "rejected",
            "rejected_by": user["email"],
            "rejected_at": iso(now_utc()),
            "rejection_reason": body.note,
        }},
    )
    await audit("promotion_reject", f"step_promotion_recommendations/{rid}", user, {
        "employee_id": rec["employee_id"], "reason": body.note,
    })
    return {"ok": True}
