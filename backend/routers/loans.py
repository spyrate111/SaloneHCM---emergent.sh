"""Loans & Salary Advances — issuance, lifecycle, schedule projection.

Tier-gated behind `loans_advances` (professional + enterprise + gov).
Employees see only their own loans; admins see all.
"""
from __future__ import annotations
import uuid
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from core import (
    db, get_current_user, require_admin, require_feature, tenant_filter, with_tenant,
    audit, now_utc, iso, is_admin,
)

router = APIRouter(
    prefix="/loans",
    tags=["loans"],
    dependencies=[Depends(require_feature("loans_advances"))],
)


# ---------- Models ----------

class LoanIn(BaseModel):
    employee_id: str = Field(..., min_length=1)
    principal_sle: float = Field(..., gt=0, le=10_000_000)
    term_months: int = Field(..., ge=1, le=120)
    purpose: str = Field("", max_length=200)
    monthly_deduction_sle: Optional[float] = Field(None, gt=0)

    @model_validator(mode="after")
    def _default_monthly(self):
        if self.monthly_deduction_sle is None:
            self.monthly_deduction_sle = round(self.principal_sle / self.term_months, 2)
        return self


class LoanPatch(BaseModel):
    monthly_deduction_sle: Optional[float] = Field(None, gt=0)
    purpose: Optional[str] = Field(None, max_length=200)
    status: Optional[Literal["active", "paid", "cancelled", "defaulted"]] = None


def _annotate(loan: dict) -> dict:
    """Add derived fields for the UI."""
    principal = float(loan.get("principal_sle", 0))
    remaining = float(loan.get("remaining_balance_sle", 0))
    paid = max(0.0, principal - remaining)
    return {
        **loan,
        "paid_sle": round(paid, 2),
        "progress": round(paid / principal, 3) if principal else 0,
        "repayment_count": len(loan.get("repayments", [])),
    }


# ---------- CRUD ----------

@router.get("")
async def list_loans(user: dict = Depends(get_current_user)):
    """Admin sees all, employee sees only their own."""
    tf = tenant_filter(user)
    q = {**tf} if is_admin(user) else {"employee_id": user.get("employee_id"), **tf}
    loans = await db.loans.find(q, {"_id": 0}).sort("issued_at", -1).to_list(1000)
    return [_annotate(loan) for loan in loans]


@router.get("/{lid}")
async def get_loan(lid: str, user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    loan = await db.loans.find_one({"id": lid, **tf}, {"_id": 0})
    if not loan:
        raise HTTPException(404, "Loan not found")
    if not is_admin(user) and loan["employee_id"] != user.get("employee_id"):
        raise HTTPException(403, "Not allowed")
    return _annotate(loan)


@router.post("", status_code=201)
async def issue_loan(body: LoanIn, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    emp = await db.employees.find_one({"id": body.employee_id, **tf},
                                      {"_id": 0, "first_name": 1, "last_name": 1, "basic_salary_sle": 1})
    if not emp:
        raise HTTPException(404, "Employee not found")
    # Sanity: monthly deduction shouldn't exceed ~50% of basic salary (responsible-lending guard)
    basic = float(emp.get("basic_salary_sle") or 0)
    if basic and body.monthly_deduction_sle > basic * 0.5:
        raise HTTPException(409, f"Monthly deduction ({body.monthly_deduction_sle}) exceeds 50% of basic salary ({basic}). Reduce or extend term.")
    # Prevent double-active loans for the same employee (1 at a time)
    existing = await db.loans.find_one({"employee_id": body.employee_id, "status": "active", **tf}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(409, f"Employee already has an active loan ({existing['id']}). Cancel or pay it off first.")

    lid = str(uuid.uuid4())
    doc = with_tenant({
        "id": lid,
        "employee_id": body.employee_id,
        "employee_name": f"{emp.get('first_name','')} {emp.get('last_name','')}".strip(),
        "principal_sle": round(body.principal_sle, 2),
        "monthly_deduction_sle": round(body.monthly_deduction_sle, 2),
        "term_months": body.term_months,
        "remaining_balance_sle": round(body.principal_sle, 2),
        "currency": "SLE",
        "purpose": body.purpose,
        "status": "active",
        "issued_at": iso(now_utc()),
        "issued_by": user["email"],
        "repayments": [],
    }, user)
    await db.loans.insert_one(doc)
    await audit("loan_issue", f"loans/{lid}", user, {
        "employee_id": body.employee_id, "principal": body.principal_sle, "term": body.term_months,
    })
    return _annotate({k: v for k, v in doc.items() if k != "_id"})


@router.patch("/{lid}")
async def patch_loan(lid: str, body: LoanPatch, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    loan = await db.loans.find_one({"id": lid, **tf}, {"_id": 0})
    if not loan:
        raise HTTPException(404, "Loan not found")
    if loan["status"] in ("paid", "cancelled") and body.status and body.status not in ("paid", "cancelled"):
        raise HTTPException(409, f"Loan already {loan['status']} — cannot reopen")
    updates = body.model_dump(exclude_none=True)
    if updates:
        updates["updated_at"] = iso(now_utc())
        await db.loans.update_one({"id": lid, **tf}, {"$set": updates})
    await audit("loan_patch", f"loans/{lid}", user, updates)
    fresh = await db.loans.find_one({"id": lid, **tf}, {"_id": 0})
    return _annotate(fresh)


@router.get("/{lid}/schedule")
async def schedule(lid: str, user: dict = Depends(get_current_user)):
    """Project remaining repayments month-by-month (no time semantics — index-based)."""
    tf = tenant_filter(user)
    loan = await db.loans.find_one({"id": lid, **tf}, {"_id": 0})
    if not loan:
        raise HTTPException(404, "Loan not found")
    if not is_admin(user) and loan["employee_id"] != user.get("employee_id"):
        raise HTTPException(403, "Not allowed")
    remaining = float(loan["remaining_balance_sle"])
    monthly = float(loan["monthly_deduction_sle"])
    rows = []
    idx = 1
    safety = 240  # 20 years max
    while remaining > 0 and idx <= safety:
        amount = min(monthly, remaining)
        remaining = round(remaining - amount, 2)
        rows.append({
            "n": idx,
            "amount": round(amount, 2),
            "remaining_after": max(0.0, remaining),
        })
        idx += 1
    return {
        "loan_id": lid,
        "principal_sle": loan["principal_sle"],
        "monthly_deduction_sle": monthly,
        "remaining_balance_sle": loan["remaining_balance_sle"],
        "projected_periods": len(rows),
        "schedule": rows,
    }


@router.get("/employee/{eid}/active")
async def active_loan_for_employee(eid: str, user: dict = Depends(get_current_user)):
    """Convenience helper used by the ESS payslip page."""
    if not is_admin(user) and eid != user.get("employee_id"):
        raise HTTPException(403, "Not allowed")
    tf = tenant_filter(user)
    loan = await db.loans.find_one(
        {"employee_id": eid, "status": "active", **tf},
        {"_id": 0},
    )
    return _annotate(loan) if loan else None
