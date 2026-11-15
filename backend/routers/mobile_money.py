"""Controlled mobile-money payroll workpapers.

Provider APIs are intentionally disabled until Orange Money and Afrimoney supply
verified employer disbursement specifications and sandbox credentials.
"""
import csv
import io
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from core import db, require_roles, audit, tenant_filter, with_tenant, now_utc, iso


router = APIRouter(prefix="/payroll/runs", tags=["mobile-money"])
PROVIDERS = {
    "orange_money": {"label": "Orange Money", "api_enabled": False},
    "afrimoney": {"label": "Afrimoney", "api_enabled": False},
}


class BatchCreateIn(BaseModel):
    provider: Literal["orange_money", "afrimoney"]


class BatchSubmitIn(BaseModel):
    provider_batch_reference: str = Field(default="", max_length=120)


class BatchLineStatusIn(BaseModel):
    status: Literal["paid", "failed"]
    provider_transaction_reference: str = Field(default="", max_length=120)
    failure_reason: str = Field(default="", max_length=1000)


def _text_cell(value) -> str:
    """Neutralize spreadsheet formulas in text cells in exported workpapers."""
    text = str(value or "")
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _assignment_id(company_id: str, run_id: str, employee_id: str) -> str:
    return f"mobile-money:{company_id}:{run_id}:{employee_id}"


def _batch_id(company_id: str, run_id: str, provider: str) -> str:
    return str(uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"salonehcm:mobile-money:{company_id}:{run_id}:{provider}",
    ))


def _build_batch_csv(batch: dict) -> bytes:
    """Build SaloneHCM's internal workpaper, not a provider upload template."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "employee_name", "wallet_mobile_number", "amount_sle",
        "currency", "payroll_period", "payment_reference",
    ])
    for line in batch.get("lines", []):
        writer.writerow([
            _text_cell(line.get("employee_name")),
            _text_cell(line.get("mobile_money_number")),
            f'{float(line.get("amount_sle", 0)):.2f}',
            "SLE",
            _text_cell(batch.get("period")),
            _text_cell(line.get("payment_reference")),
        ])
    return buffer.getvalue().encode("utf-8")


async def _find_batch(run_id: str, batch_id: str, user: dict) -> dict:
    batch = await db.mobile_money_batches.find_one(
        {"id": batch_id, "run_id": run_id, **tenant_filter(user)},
        {"_id": 0},
    )
    if not batch:
        raise HTTPException(404, "Mobile-money batch not found")
    return batch


@router.get("/{rid}/mobile-money-batches")
async def list_mobile_money_batches(
    rid: str,
    response: Response,
    user: dict = Depends(require_roles("payroll")),
):
    response.headers["Cache-Control"] = "private, no-store"
    run = await db.payroll_runs.find_one(
        {"id": rid, **tenant_filter(user)}, {"_id": 0, "id": 1},
    )
    if not run:
        raise HTTPException(404, "Payroll run not found")
    batches = await db.mobile_money_batches.find(
        {"run_id": rid, **tenant_filter(user)}, {"_id": 0},
    ).sort("created_at", 1).to_list(20)
    return {"batches": batches, "providers": PROVIDERS}


@router.post("/{rid}/mobile-money-batches")
async def create_mobile_money_batch(
    rid: str,
    body: BatchCreateIn,
    user: dict = Depends(require_roles("payroll")),
):
    scope = tenant_filter(user)
    run = await db.payroll_runs.find_one(
        {"id": rid, **scope}, {"_id": 0},
    )
    if not run:
        raise HTTPException(404, "Payroll run not found")

    company_id = user["company_id"]
    batch_id = _batch_id(company_id, rid, body.provider)
    existing = await db.mobile_money_batches.find_one(
        {"_id": batch_id, **scope}, {"_id": 0},
    )
    if existing:
        return {"batch": existing, "created": False}

    slips = [s for s in run.get("slips", []) if float(s.get("net", 0) or 0) > 0]
    employee_ids = [s["employee_id"] for s in slips]
    employees = await db.employees.find(
        {"id": {"$in": employee_ids}, **scope}, {"_id": 0},
    ).to_list(2000)
    employee_by_id = {e["id"]: e for e in employees}

    lines = []
    excluded = []
    reservations = []
    for slip in slips:
        employee = employee_by_id.get(slip["employee_id"], {})
        if employee.get("mobile_money_provider") != body.provider:
            continue
        wallet_number = (employee.get("mobile_money_number") or "").strip()
        if not wallet_number:
            excluded.append({
                "employee_id": slip["employee_id"],
                "employee_name": slip.get("employee_name", ""),
                "reason": "Wallet number is missing",
            })
            continue
        lines.append({
            "employee_id": slip["employee_id"],
            "employee_name": slip.get("employee_name", ""),
            "mobile_money_number": wallet_number,
            "amount_sle": round(float(slip["net"]), 2),
            "payment_reference": f'PAYROLL-{run.get("period", "")}-{slip["employee_id"][:8]}',
            "status": "pending",
            "provider_transaction_reference": "",
            "failure_reason": "",
            "history": [],
        })

    assignment_keys = [
        _assignment_id(company_id, rid, line["employee_id"]) for line in lines
    ]
    existing_assignments = await db.mobile_money_assignments.find(
        {"_id": {"$in": assignment_keys}, **scope},
        {"_id": 1, "employee_id": 1, "batch_id": 1, "provider": 1},
    ).to_list(len(assignment_keys))
    assignment_by_key = {item["_id"]: item for item in existing_assignments}

    for line in lines:
        assignment_key = _assignment_id(company_id, rid, line["employee_id"])
        previous = assignment_by_key.get(assignment_key)
        if previous:
            if previous.get("batch_id") == batch_id:
                continue
            await db.mobile_money_assignments.delete_many({"_id": {"$in": reservations}})
            if previous.get("provider") == "bank":
                raise HTTPException(
                    409,
                    "This employee is already included in a bank-file export for this payroll run.",
                )
            raise HTTPException(
                409,
                "At least one employee is already assigned to another wallet batch for this payroll run.",
            )
        assignment = {
            "_id": assignment_key,
            "company_id": company_id,
            "run_id": rid,
            "employee_id": line["employee_id"],
            "batch_id": batch_id,
            "provider": body.provider,
            "created_at": iso(now_utc()),
        }
        try:
            await db.mobile_money_assignments.insert_one(assignment)
            reservations.append(assignment_key)
        except DuplicateKeyError:
            existing_assignment = await db.mobile_money_assignments.find_one(
                {"_id": assignment_key, **scope}, {"_id": 0},
            )
            if existing_assignment and existing_assignment.get("batch_id") == batch_id:
                continue
            await db.mobile_money_assignments.delete_many({"_id": {"$in": reservations}})
            existing = await db.mobile_money_batches.find_one(
                {"_id": batch_id, **scope}, {"_id": 0},
            )
            if existing:
                return {"batch": existing, "created": False}
            if existing_assignment and existing_assignment.get("provider") == "bank":
                raise HTTPException(
                    409,
                    "This employee is already included in a bank-file export for this payroll run.",
                )
            raise HTTPException(
                409,
                "At least one employee is already assigned to another wallet batch for this payroll run.",
            )

    now = iso(now_utc())
    batch = with_tenant({
        "_id": batch_id,
        "id": batch_id,
        "run_id": rid,
        "period": run.get("period", ""),
        "provider": body.provider,
        "provider_label": PROVIDERS[body.provider]["label"],
        "provider_api_enabled": False,
        "currency": "SLE",
        "status": "draft",
        "lines": lines,
        "excluded": excluded,
        "created_by": user.get("name") or user["email"],
        "created_by_email": user["email"],
        "created_at": now,
        "approved_by": None,
        "approved_by_email": None,
        "approved_at": None,
        "exported_at": None,
        "export_count": 0,
        "provider_batch_reference": "",
        "submitted_at": None,
        "submitted_by": None,
        "reconciled_at": None,
    }, user)
    try:
        await db.mobile_money_batches.insert_one(batch)
    except DuplicateKeyError:
        await db.mobile_money_assignments.delete_many({"_id": {"$in": reservations}})
        existing = await db.mobile_money_batches.find_one(
            {"_id": batch_id, **scope}, {"_id": 0},
        )
        if existing:
            return {"batch": existing, "created": False}
        raise HTTPException(409, "A wallet batch for this provider and payroll run is already being prepared.")

    batch.pop("_id", None)
    await audit(
        "mobile_money_batch_created",
        f"payroll_runs/{rid}/mobile-money/{batch_id}",
        user,
        {"provider": body.provider, "line_count": len(lines), "excluded_count": len(excluded)},
    )
    return {"batch": batch, "created": True}


@router.delete("/{rid}/mobile-money-batches/{batch_id}")
async def cancel_mobile_money_batch(
    rid: str,
    batch_id: str,
    user: dict = Depends(require_roles("payroll")),
):
    batch = await _find_batch(rid, batch_id, user)
    if batch.get("status") != "draft":
        raise HTTPException(409, "Only a draft wallet batch can be cancelled.")
    if batch.get("created_by_email") != user.get("email"):
        raise HTTPException(403, "Only the batch creator can cancel this draft.")
    deleted = await db.mobile_money_batches.delete_one({
        "id": batch_id, "run_id": rid, **tenant_filter(user), "status": "draft",
    })
    if deleted.deleted_count != 1:
        raise HTTPException(409, "The wallet batch changed. Refresh and try again.")
    await db.mobile_money_assignments.delete_many({
        "batch_id": batch_id, **tenant_filter(user),
    })
    await audit(
        "mobile_money_batch_cancelled",
        f"payroll_runs/{rid}/mobile-money/{batch_id}",
        user,
        {"provider": batch.get("provider"), "line_count": len(batch.get("lines", []))},
    )
    return {"ok": True}


@router.post("/{rid}/mobile-money-batches/{batch_id}/approve")
async def approve_mobile_money_batch(
    rid: str,
    batch_id: str,
    user: dict = Depends(require_roles("payroll")),
):
    batch = await _find_batch(rid, batch_id, user)
    if batch.get("status") != "draft":
        raise HTTPException(409, "Only a draft wallet batch can be approved.")
    if batch.get("created_by_email") == user.get("email"):
        raise HTTPException(403, "A different admin must approve the wallet batch.")
    if not batch.get("lines"):
        raise HTTPException(409, "Add a configured wallet number before approving this batch.")
    result = await db.mobile_money_batches.update_one(
        {
            "id": batch_id, "run_id": rid, **tenant_filter(user),
            "status": "draft", "created_by_email": {"$ne": user.get("email")},
        },
        {"$set": {
            "status": "approved",
            "approved_by": user.get("name") or user["email"],
            "approved_by_email": user["email"],
            "approved_at": iso(now_utc()),
        }},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "The wallet batch changed. Refresh and review it again.")
    await audit(
        "mobile_money_batch_approved",
        f"payroll_runs/{rid}/mobile-money/{batch_id}",
        user,
        {"provider": batch.get("provider"), "line_count": len(batch.get("lines", []))},
    )
    return await _find_batch(rid, batch_id, user)


@router.get("/{rid}/mobile-money-batches/{batch_id}.csv")
async def export_mobile_money_batch(
    rid: str,
    batch_id: str,
    response: Response,
    user: dict = Depends(require_roles("payroll")),
):
    response.headers["Cache-Control"] = "private, no-store"
    batch = await _find_batch(rid, batch_id, user)
    if batch.get("status") not in ("approved", "exported"):
        raise HTTPException(409, "Approve the wallet batch before exporting it.")
    if not batch.get("lines"):
        raise HTTPException(409, "The wallet batch has no payable employees.")
    now = iso(now_utc())
    updated = await db.mobile_money_batches.update_one(
        {
            "id": batch_id, "run_id": rid, **tenant_filter(user),
            "status": {"$in": ["approved", "exported"]},
        },
        {"$set": {"status": "exported", "exported_at": batch.get("exported_at") or now},
         "$inc": {"export_count": 1}},
    )
    if updated.matched_count != 1:
        raise HTTPException(409, "The wallet batch changed. Refresh and export it again.")
    await audit(
        "mobile_money_batch_workpaper_exported",
        f"payroll_runs/{rid}/mobile-money/{batch_id}",
        user,
        {"provider": batch.get("provider"), "line_count": len(batch.get("lines", []))},
    )
    payload = io.BytesIO(_build_batch_csv(batch))
    filename = f'mobile-money-{batch["provider"]}-{batch["period"]}.csv'
    return StreamingResponse(
        payload,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{rid}/mobile-money-batches/{batch_id}/mark-submitted")
async def mark_mobile_money_batch_submitted(
    rid: str,
    batch_id: str,
    body: BatchSubmitIn,
    user: dict = Depends(require_roles("payroll")),
):
    batch = await _find_batch(rid, batch_id, user)
    if batch.get("status") != "exported":
        raise HTTPException(409, "Export the approved workpaper before recording provider-portal submission.")
    result = await db.mobile_money_batches.update_one(
        {
            "id": batch_id, "run_id": rid, **tenant_filter(user),
            "status": "exported",
        },
        {"$set": {
            "status": "submitted",
            "provider_batch_reference": body.provider_batch_reference.strip(),
            "submitted_at": iso(now_utc()),
            "submitted_by": user.get("name") or user["email"],
            "submitted_by_email": user["email"],
        }},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "The wallet batch changed. Refresh and try again.")
    await audit(
        "mobile_money_batch_marked_submitted",
        f"payroll_runs/{rid}/mobile-money/{batch_id}",
        user,
        {"provider": batch.get("provider"), "line_count": len(batch.get("lines", []))},
    )
    return await _find_batch(rid, batch_id, user)


@router.patch("/{rid}/mobile-money-batches/{batch_id}/lines/{employee_id}")
async def reconcile_mobile_money_line(
    rid: str,
    batch_id: str,
    employee_id: str,
    body: BatchLineStatusIn,
    user: dict = Depends(require_roles("payroll")),
):
    batch = await _find_batch(rid, batch_id, user)
    if batch.get("status") not in ("submitted", "reconciling", "reconciled_with_failures"):
        raise HTTPException(409, "Record portal results after the batch is submitted.")
    if batch.get("status") == "reconciled":
        raise HTTPException(409, "This wallet batch is fully reconciled.")
    line = next(
        (item for item in batch.get("lines", []) if item.get("employee_id") == employee_id),
        None,
    )
    if not line:
        raise HTTPException(404, "Employee is not part of this wallet batch.")
    if line.get("status") == "paid":
        raise HTTPException(409, "A paid wallet line is locked.")
    reference = body.provider_transaction_reference.strip()
    failure_reason = body.failure_reason.strip()
    if body.status == "paid" and not reference:
        raise HTTPException(422, "Enter the provider transaction reference for a paid line.")
    if body.status == "failed" and not failure_reason:
        raise HTTPException(422, "Enter a failure reason for a failed line.")

    event = {
        "status": body.status,
        "provider_transaction_reference": reference if body.status == "paid" else "",
        "failure_reason": failure_reason if body.status == "failed" else "",
        "recorded_by": user.get("name") or user["email"],
        "recorded_by_email": user["email"],
        "recorded_at": iso(now_utc()),
    }
    result = await db.mobile_money_batches.update_one(
        {
            "id": batch_id, "run_id": rid, **tenant_filter(user),
            "status": {"$in": ["submitted", "reconciling", "reconciled_with_failures"]},
            "lines": {
                "$elemMatch": {
                    "employee_id": employee_id,
                    "status": {"$in": ["pending", "failed"]},
                },
            },
        },
        {
            "$set": {
                "status": "reconciling",
                "lines.$.status": body.status,
                "lines.$.provider_transaction_reference": event["provider_transaction_reference"],
                "lines.$.failure_reason": event["failure_reason"],
                "lines.$.updated_at": event["recorded_at"],
                "updated_at": event["recorded_at"],
            },
            "$push": {"lines.$.history": event},
        },
    )
    if result.matched_count != 1:
        raise HTTPException(409, "The wallet line changed. Refresh and reconcile it again.")

    updated_batch = await _find_batch(rid, batch_id, user)
    statuses = [item.get("status") for item in updated_batch.get("lines", [])]
    if statuses and all(status == "paid" for status in statuses):
        next_status = "reconciled"
    elif statuses and all(status in ("paid", "failed") for status in statuses):
        next_status = "reconciled_with_failures"
    else:
        next_status = "reconciling"
    await db.mobile_money_batches.update_one(
        {
            "id": batch_id, "run_id": rid, **tenant_filter(user),
            "status": {"$in": ["reconciling", "reconciled_with_failures"]},
        },
        {"$set": {
            "status": next_status,
            "reconciled_at": iso(now_utc()) if next_status != "reconciling" else None,
        }},
    )
    await audit(
        "mobile_money_line_reconciled",
        f"payroll_runs/{rid}/mobile-money/{batch_id}",
        user,
        {"provider": batch.get("provider"), "line_status": body.status},
    )
    return await _find_batch(rid, batch_id, user)
