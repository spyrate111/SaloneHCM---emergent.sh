"""Loan deduction lifecycle integration with the payroll engine.

Each loan has:
  * principal_sle, monthly_deduction_sle, remaining_balance_sle
  * status: pending | active | paid | cancelled | defaulted
  * a `repayments` array of {period, amount, payroll_run_id, applied_at}

When run_payroll() finalizes a period, we:
  1. For each active loan, the period's deduction = min(monthly_deduction, remaining_balance).
  2. Append to repayments (idempotent — keyed on period+loan_id).
  3. Decrement remaining_balance.
  4. If balance hits 0, flip status → paid.
"""
from __future__ import annotations
from core import db, now_utc, iso


async def _active_loans_for_employee(employee_id: str, company_id: str) -> list[dict]:
    return await db.loans.find(
        {"employee_id": employee_id, "company_id": company_id,
         "status": {"$in": ["active", "pending"]}},
        {"_id": 0},
    ).to_list(50)


async def compute_loan_deduction_for_period(employee_id: str, company_id: str, period: str) -> tuple[float, list[dict]]:
    """Return (total_deduction_for_this_employee, applied_rows).

    `applied_rows` describes which loans contributed (used by apply_loan_deductions_for_run
    to persist repayments against the run).
    """
    loans = await _active_loans_for_employee(employee_id, company_id)
    total = 0.0
    applied: list[dict] = []
    for ln in loans:
        # Skip if already deducted for this period (idempotency)
        already_paid = any(r.get("period") == period for r in ln.get("repayments", []))
        if already_paid:
            continue
        remaining = float(ln.get("remaining_balance_sle", 0) or 0)
        monthly = float(ln.get("monthly_deduction_sle", 0) or 0)
        if remaining <= 0 or monthly <= 0:
            continue
        due = round(min(monthly, remaining), 2)
        if due <= 0:
            continue
        total += due
        applied.append({
            "loan_id": ln["id"],
            "amount": due,
            "remaining_before": remaining,
            "period": period,
        })
    return round(total, 2), applied


async def apply_loan_deductions_for_run(run_id: str, period: str, rows: list[dict]) -> None:
    """Persist repayments against affected loans. Called after run_payroll inserts the run."""
    ts = iso(now_utc())
    for row in rows:
        new_balance = round(row["remaining_before"] - row["amount"], 2)
        new_status = "paid" if new_balance <= 0 else "active"
        await db.loans.update_one(
            {"id": row["loan_id"]},
            {
                "$set": {
                    "remaining_balance_sle": max(0.0, new_balance),
                    "status": new_status,
                    "last_deduction_at": ts,
                    "last_deduction_period": period,
                },
                "$push": {"repayments": {
                    "period": period,
                    "amount": row["amount"],
                    "payroll_run_id": run_id,
                    "applied_at": ts,
                }},
            },
        )
