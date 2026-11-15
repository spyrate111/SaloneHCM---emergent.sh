"""Offboarding workflow — exit checklist with role-gated sign-offs, account deactivation on completion."""
import csv
import io
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import (db, get_current_user, require_roles, can_role, is_admin, audit,
                  tenant_filter, with_tenant, now_utc, iso)

router = APIRouter(prefix="/offboarding", tags=["offboarding"])


def _visible_offboarding(row: dict, user: dict) -> dict:
    """Keep final-pay figures visible only to payroll and tenant admins."""
    if row and not is_admin(user) and not can_role(user, "payroll"):
        row.pop("final_settlement", None)
    return row

CHECKLIST_TEMPLATE = [
    {"key": "final_settlement", "label": "Final payroll settlement", "responsible_role": "payroll"},
    {"key": "document_handover", "label": "Document handover", "responsible_role": "hr"},
    {"key": "equipment_return", "label": "Equipment return", "responsible_role": "hr"},
    {"key": "access_revocation", "label": "Access revocation", "responsible_role": "admin"},
]


class FinalSettlementIn(BaseModel):
    payroll_period: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    taxable_final_pay_sle: float = Field(..., ge=0, allow_inf_nan=False)
    termination_payment_sle: float = Field(default=0, ge=0, allow_inf_nan=False)
    termination_payment_basis: Literal[
        "", "redundancy", "termination", "loss_of_office", "similar_type",
    ] = ""
    paye_withheld_sle: float = Field(default=0, ge=0, allow_inf_nan=False)
    nassit_employee_sle: float = Field(default=0, ge=0, allow_inf_nan=False)
    nassit_employer_sle: float = Field(default=0, ge=0, allow_inf_nan=False)
    other_deductions_sle: float = Field(default=0, ge=0, allow_inf_nan=False)
    payment_method: Literal[
        "Bank transfer", "Orange Money", "Afrimoney", "Cheque", "Cash", "Not applicable",
    ]
    notes: str = Field(default="", max_length=3000)
    revision_reason: str = Field(default="", max_length=1000)


class FinalSettlementPaymentIn(BaseModel):
    payment_date: date
    payment_reference: str = Field(..., min_length=1, max_length=120)


def _may_complete(user: dict, item: dict) -> bool:
    role = item["responsible_role"]
    if role == "admin":
        return is_admin(user)
    return can_role(user, role)


@router.get("")
async def list_offboardings(
    response: Response,
    user: dict = Depends(require_roles("hr", "payroll", "auditor")),
):
    response.headers["Cache-Control"] = "private, no-store"
    rows = await db.offboardings.find(
        tenant_filter(user), {"_id": 0}).sort("started_at", -1).to_list(500)
    return [_visible_offboarding(row, user) for row in rows]


@router.get("/employee/{eid}")
async def get_for_employee(
    eid: str,
    response: Response,
    user: dict = Depends(require_roles("hr", "payroll", "auditor")),
):
    response.headers["Cache-Control"] = "private, no-store"
    row = await db.offboardings.find_one(
        {"employee_id": eid, **tenant_filter(user), "status": {"$ne": "cancelled"}},
        {"_id": 0}, sort=[("started_at", -1)])
    if not row:
        raise HTTPException(404, "No offboarding for this employee")
    return _visible_offboarding(row, user)


@router.post("/{eid}/start")
async def start_offboarding(eid: str, user: dict = Depends(require_roles("hr"))):
    emp = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")
    existing = await db.offboardings.find_one(
        {"employee_id": eid, **tenant_filter(user), "status": "in_progress"}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(409, "Offboarding already in progress for this employee")

    oid = str(uuid.uuid4())
    doc = with_tenant({
        "id": oid,
        "employee_id": eid,
        "employee_name": f'{emp.get("first_name", "")} {emp.get("last_name", "")}'.strip(),
        "status": "in_progress",
        "items": [{**i, "completed": False, "completed_by": None, "completed_at": None}
                  for i in CHECKLIST_TEMPLATE],
        "started_by": user.get("name") or user["email"],
        "started_at": iso(now_utc()),
        "completed_at": None,
    }, user)
    await db.offboardings.insert_one(doc)
    doc.pop("_id", None)
    await db.employees.update_one({"id": eid, **tenant_filter(user)},
                                  {"$set": {"status": "exiting"}})
    await audit("offboarding_started", f"offboardings/{oid}", user,
                {"employee": doc["employee_name"], "employee_id": eid})
    return doc


@router.put("/{oid}/items/{key}/complete")
async def complete_item(oid: str, key: str, user: dict = Depends(get_current_user)):
    ob = await db.offboardings.find_one({"id": oid, **tenant_filter(user)}, {"_id": 0})
    if not ob:
        raise HTTPException(404, "Offboarding not found")
    if ob["status"] != "in_progress":
        raise HTTPException(409, "Offboarding is not in progress")
    item = next((i for i in ob["items"] if i["key"] == key), None)
    if not item:
        raise HTTPException(404, "Checklist item not found")
    if item["completed"]:
        raise HTTPException(409, "Item already completed")
    if key == "final_settlement":
        settlement = ob.get("final_settlement") or {}
        settlement_status = settlement.get("status")
        net_amount = float(settlement.get("net_settlement_sle", 0) or 0)
        if settlement_status != "paid" and not (
            settlement_status == "approved" and net_amount == 0
        ):
            raise HTTPException(
                409,
                "Approve the final settlement and record payment before completing this checklist item.",
            )
    if not _may_complete(user, item):
        raise HTTPException(403, f"Only {item['responsible_role']} (or an admin) may complete '{item['label']}'")

    now = iso(now_utc())
    who = user.get("name") or user["email"]
    for i in ob["items"]:
        if i["key"] == key:
            i.update({"completed": True, "completed_by": who, "completed_at": now})
    all_done = all(i["completed"] for i in ob["items"])
    update = {"items": ob["items"]}
    await audit("offboarding_item_completed", f"offboardings/{oid}", user,
                {"item": key, "employee": ob["employee_name"]})

    deactivated = False
    if all_done:
        update["status"] = "completed"
        update["completed_at"] = now
        await db.employees.update_one({"id": ob["employee_id"], **tenant_filter(user)},
                                      {"$set": {"status": "exited"}})
        res = await db.users.update_many(
            {"employee_id": ob["employee_id"], **tenant_filter(user)},
            {"$set": {"disabled": True, "deactivated_at": now}})
        deactivated = res.modified_count > 0
        await audit("offboarding_completed", f"offboardings/{oid}", user,
                    {"employee": ob["employee_name"], "account_deactivated": deactivated})

    await db.offboardings.update_one({"id": oid}, {"$set": update})
    return {"ok": True, "all_complete": all_done, "account_deactivated": deactivated}


LEAVING_REASONS = {"resignation", "retirement", "redundancy", "contract_end", "dismissal", "other"}


class ExitInterviewIn(BaseModel):
    leaving_reason: str
    notes: str = ""


@router.put("/{oid}/exit-interview")
async def record_exit_interview(oid: str, body: ExitInterviewIn,
                                user: dict = Depends(require_roles("hr"))):
    if body.leaving_reason not in LEAVING_REASONS:
        raise HTTPException(422, f"leaving_reason must be one of: {', '.join(sorted(LEAVING_REASONS))}")
    ob = await db.offboardings.find_one({"id": oid, **tenant_filter(user)}, {"_id": 0})
    if not ob:
        raise HTTPException(404, "Offboarding not found")
    if ob["status"] == "cancelled":
        raise HTTPException(409, "Cannot record an exit interview on a cancelled offboarding")
    record = {
        "leaving_reason": body.leaving_reason,
        "notes": body.notes.strip()[:5000],
        "recorded_by": user.get("name") or user["email"],
        "recorded_at": iso(now_utc()),
    }
    await db.offboardings.update_one({"id": oid}, {"$set": {"exit_interview": record}})
    await audit("exit_interview_recorded", f"offboardings/{oid}", user,
                {"employee": ob["employee_name"], "leaving_reason": body.leaving_reason})
    return {"ok": True, "exit_interview": record}


@router.put("/{oid}/settlement")
async def save_final_settlement(
    oid: str,
    body: FinalSettlementIn,
    user: dict = Depends(require_roles("payroll")),
):
    scope = tenant_filter(user)
    offboarding = await db.offboardings.find_one(
        {"id": oid, **scope}, {"_id": 0},
    )
    if not offboarding:
        raise HTTPException(404, "Offboarding not found")
    if offboarding.get("status") != "in_progress":
        raise HTTPException(409, "Final settlements can only be prepared during active offboarding.")

    taxable_final_pay = round(float(body.taxable_final_pay_sle), 2)
    termination_payment = round(float(body.termination_payment_sle or 0), 2)
    paye_withheld = round(float(body.paye_withheld_sle or 0), 2)
    nassit_employee = round(float(body.nassit_employee_sle or 0), 2)
    nassit_employer = round(float(body.nassit_employer_sle or 0), 2)
    other_deductions = round(float(body.other_deductions_sle or 0), 2)
    gross_settlement = round(taxable_final_pay + termination_payment, 2)
    net_settlement = round(
        gross_settlement - paye_withheld - nassit_employee - other_deductions, 2,
    )
    if termination_payment > 0 and not body.termination_payment_basis:
        raise HTTPException(422, "Select the legal basis for the termination payment.")
    if net_settlement < 0:
        raise HTTPException(422, "PAYE, employee NASSIT, and other deductions cannot exceed the settlement total.")
    if net_settlement > 0 and body.payment_method == "Not applicable":
        raise HTTPException(422, "Select the payment method for a settlement with a positive net amount.")
    if gross_settlement == 0 and not body.notes.strip():
        raise HTTPException(422, "Add a note explaining a zero-value final settlement.")

    current = offboarding.get("final_settlement")
    if current and current.get("status") == "paid":
        raise HTTPException(409, "A paid final settlement is locked. Record any correction as a separate adjustment.")
    if current and current.get("status") == "approved" and not body.revision_reason.strip():
        raise HTTPException(422, "Enter a reason before revising an approved settlement.")

    revision = int(current.get("revision", 1)) if current else 1
    history = list(current.get("history", [])) if current else []
    settlement_id = current.get("id") if current and current.get("status") == "draft" else str(uuid.uuid4())
    if current and current.get("status") == "approved":
        revision += 1
        history.append({key: value for key, value in current.items() if key != "history"})

    now = iso(now_utc())
    settlement = {
        "id": settlement_id,
        "revision": revision,
        "status": "draft",
        "currency": "SLE",
        "payroll_period": body.payroll_period,
        "taxable_final_pay_sle": taxable_final_pay,
        "termination_payment_sle": termination_payment,
        "termination_payment_basis": body.termination_payment_basis,
        "paye_withheld_sle": paye_withheld,
        "nassit_employee_sle": nassit_employee,
        "nassit_employer_sle": nassit_employer,
        "other_deductions_sle": other_deductions,
        "gross_settlement_sle": gross_settlement,
        "net_settlement_sle": net_settlement,
        "payment_method": body.payment_method,
        "notes": body.notes.strip(),
        "revision_reason": body.revision_reason.strip(),
        "prepared_by": user.get("name") or user["email"],
        "prepared_by_email": user["email"],
        "prepared_at": now,
        "approved_by": None,
        "approved_by_email": None,
        "approved_at": None,
        "payment_reference": None,
        "payment_date": None,
        "paid_by": None,
        "paid_by_email": None,
        "paid_at": None,
        "history": history,
    }
    update_filter = {"id": oid, **scope, "status": "in_progress"}
    if current:
        update_filter.update({
            "final_settlement.revision": current.get("revision"),
            "final_settlement.status": current.get("status"),
            "final_settlement.prepared_at": current.get("prepared_at"),
        })
    else:
        update_filter["final_settlement"] = {"$exists": False}
    result = await db.offboardings.update_one(
        update_filter, {"$set": {"final_settlement": settlement}},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "Another user changed this settlement. Refresh and prepare it again.")
    await audit(
        "offboarding_final_settlement_prepared",
        f"offboardings/{oid}",
        user,
        {"settlement_id": settlement_id, "revision": revision, "payroll_period": body.payroll_period},
    )
    return await db.offboardings.find_one({"id": oid, **scope}, {"_id": 0})


@router.post("/{oid}/settlement/approve")
async def approve_final_settlement(
    oid: str,
    user: dict = Depends(require_roles("payroll")),
):
    scope = tenant_filter(user)
    offboarding = await db.offboardings.find_one({"id": oid, **scope}, {"_id": 0})
    if not offboarding:
        raise HTTPException(404, "Offboarding not found")
    settlement = offboarding.get("final_settlement") or {}
    if offboarding.get("status") != "in_progress" or settlement.get("status") != "draft":
        raise HTTPException(409, "Only a draft final settlement on active offboarding can be approved.")
    if settlement.get("prepared_by_email") == user.get("email"):
        raise HTTPException(403, "A different payroll user must approve the final settlement.")
    now = iso(now_utc())
    result = await db.offboardings.update_one(
        {
            "id": oid,
            **scope,
            "status": "in_progress",
            "final_settlement.status": "draft",
            "final_settlement.revision": settlement.get("revision"),
            "final_settlement.prepared_at": settlement.get("prepared_at"),
        },
        {"$set": {
            "final_settlement.status": "approved",
            "final_settlement.approved_by": user.get("name") or user["email"],
            "final_settlement.approved_by_email": user["email"],
            "final_settlement.approved_at": now,
        }},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "Another user changed this settlement. Refresh and review it again.")
    await audit(
        "offboarding_final_settlement_approved",
        f"offboardings/{oid}",
        user,
        {"settlement_id": settlement["id"], "revision": settlement["revision"]},
    )
    return await db.offboardings.find_one({"id": oid, **scope}, {"_id": 0})


@router.post("/{oid}/settlement/mark-paid")
async def mark_final_settlement_paid(
    oid: str,
    body: FinalSettlementPaymentIn,
    user: dict = Depends(require_roles("payroll")),
):
    scope = tenant_filter(user)
    offboarding = await db.offboardings.find_one({"id": oid, **scope}, {"_id": 0})
    if not offboarding:
        raise HTTPException(404, "Offboarding not found")
    settlement = offboarding.get("final_settlement") or {}
    if offboarding.get("status") != "in_progress" or settlement.get("status") != "approved":
        raise HTTPException(409, "Approve the final settlement before recording payment.")
    if float(settlement.get("net_settlement_sle", 0) or 0) <= 0:
        raise HTTPException(409, "This settlement has no positive amount to pay.")
    reference = body.payment_reference.strip()
    if not reference:
        raise HTTPException(422, "Enter the receipt or payment reference.")

    now = iso(now_utc())
    result = await db.offboardings.update_one(
        {
            "id": oid,
            **scope,
            "status": "in_progress",
            "final_settlement.status": "approved",
            "final_settlement.revision": settlement.get("revision"),
            "final_settlement.prepared_at": settlement.get("prepared_at"),
        },
        {"$set": {
            "final_settlement.status": "paid",
            "final_settlement.payment_reference": reference,
            "final_settlement.payment_date": body.payment_date.isoformat(),
            "final_settlement.paid_by": user.get("name") or user["email"],
            "final_settlement.paid_by_email": user["email"],
            "final_settlement.paid_at": now,
        }},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "Another user changed this settlement. Refresh the offboarding record.")
    await audit(
        "offboarding_final_settlement_paid",
        f"offboardings/{oid}",
        user,
        {"settlement_id": settlement["id"], "revision": settlement["revision"]},
    )
    return await db.offboardings.find_one({"id": oid, **scope}, {"_id": 0})


@router.get("/{oid}/settlement.csv")
async def export_final_settlement(
    oid: str,
    response: Response,
    user: dict = Depends(require_roles("payroll")),
):
    response.headers["Cache-Control"] = "private, no-store"
    scope = tenant_filter(user)
    offboarding = await db.offboardings.find_one({"id": oid, **scope}, {"_id": 0})
    if not offboarding:
        raise HTTPException(404, "Offboarding not found")
    settlement = offboarding.get("final_settlement") or {}
    if settlement.get("status") not in ("approved", "paid"):
        raise HTTPException(409, "Only an approved final settlement can be exported.")
    company_id = user.get("company_id")
    company = await db.companies.find_one(
        {"id": company_id}, {"_id": 0, "name": 1},
    ) if company_id else {}
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Employer", "Employee", "Payroll Period", "Currency",
        "Taxable Final Pay (SLE)", "Termination Payment (PAYE-exempt)",
        "Termination Payment Basis", "PAYE Withheld (SLE)",
        "Employee NASSIT (SLE)", "Employer NASSIT (SLE)", "Other Deductions (SLE)",
        "Gross Settlement (SLE)", "Net Settlement (SLE)", "Payment Method",
        "Payment Reference", "Payment Date", "Revision", "Prepared By", "Approved By",
    ])
    writer.writerow([
        company.get("name", ""), offboarding.get("employee_name", ""),
        settlement.get("payroll_period", ""), settlement.get("currency", "SLE"),
        f'{float(settlement.get("taxable_final_pay_sle", 0)):.2f}',
        f'{float(settlement.get("termination_payment_sle", 0)):.2f}',
        settlement.get("termination_payment_basis", ""),
        f'{float(settlement.get("paye_withheld_sle", 0)):.2f}',
        f'{float(settlement.get("nassit_employee_sle", 0)):.2f}',
        f'{float(settlement.get("nassit_employer_sle", 0)):.2f}',
        f'{float(settlement.get("other_deductions_sle", 0)):.2f}',
        f'{float(settlement.get("gross_settlement_sle", 0)):.2f}',
        f'{float(settlement.get("net_settlement_sle", 0)):.2f}',
        settlement.get("payment_method", ""),
        settlement.get("payment_reference") or "",
        settlement.get("payment_date") or "",
        settlement.get("revision", 1),
        settlement.get("prepared_by", ""),
        settlement.get("approved_by", ""),
    ])
    await audit(
        "offboarding_final_settlement_exported",
        f"offboardings/{oid}",
        user,
        {"settlement_id": settlement["id"], "revision": settlement["revision"]},
    )
    payload = io.BytesIO(buffer.getvalue().encode())
    filename = f'Final-Settlement-{settlement["payroll_period"]}-{oid[:8]}.csv'
    return StreamingResponse(
        payload,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{oid}")
async def cancel_offboarding(oid: str, user: dict = Depends(require_roles("hr"))):
    ob = await db.offboardings.find_one({"id": oid, **tenant_filter(user)}, {"_id": 0})
    if not ob:
        raise HTTPException(404, "Offboarding not found")
    if ob["status"] != "in_progress":
        raise HTTPException(409, "Only in-progress offboardings can be cancelled")
    if (ob.get("final_settlement") or {}).get("status") in ("approved", "paid"):
        raise HTTPException(
            409,
            "An approved final settlement must be resolved before offboarding can be cancelled.",
        )
    await db.offboardings.update_one({"id": oid}, {"$set": {
        "status": "cancelled",
        "cancelled_by": user.get("name") or user["email"],
        "cancelled_at": iso(now_utc()),
    }})
    await db.employees.update_one({"id": ob["employee_id"], **tenant_filter(user)},
                                  {"$set": {"status": "active"}})
    await audit("offboarding_cancelled", f"offboardings/{oid}", user,
                {"employee": ob["employee_name"]})
    return {"ok": True}
