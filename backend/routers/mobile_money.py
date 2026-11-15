"""SLE mobile-money payroll batches with independent approval and reconciliation.

Provider API calls are intentionally not implemented until Orange/Africell provide
confirmed employer payout specifications. The workbook is a provider-neutral
workpaper for manual use with each operator's approved salary-payment flow.
"""
import io
import math
import re
import uuid
import zipfile
from datetime import date
from typing import Literal, Optional
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from core import audit, db, iso, now_utc, require_roles, tenant_filter

router = APIRouter(prefix="/payroll", tags=["mobile-money"])
PROVIDERS = {
    "orange_money": "Orange Money",
    "afrimoney": "Afrimoney",
}


class MobileMoneyBatchIn(BaseModel):
    provider: Literal["orange_money", "afrimoney"]
    payment_date: date


class RetryMobileMoneyBatchIn(BaseModel):
    payment_date: date


class RecipientReconciliationIn(BaseModel):
    status: Literal["paid", "failed"]
    provider_reference: Optional[str] = Field(default="", max_length=120)
    failure_reason: Optional[str] = Field(default="", max_length=500)


def _normalize_wallet_number(raw: object) -> Optional[str]:
    value = re.sub(r"[\s().-]", "", str(raw or ""))
    if not re.fullmatch(r"\+?\d{8,15}", value):
        return None
    return value


def _assigned_mobile_money_provider(employee: dict) -> Optional[str]:
    preference = employee.get("mobile_money_provider") or "auto"
    if preference in PROVIDERS:
        return preference
    if preference == "none":
        return None
    if preference != "auto":
        return "invalid"

    wallets = {
        "orange_money": str(employee.get("orange_money_number") or "").strip(),
        "afrimoney": str(employee.get("afrimoney_number") or "").strip(),
    }
    available = [provider for provider, number in wallets.items() if number]
    if len(available) == 1:
        return available[0]
    if len(available) > 1:
        return "ambiguous"
    return None


def _route_mobile_money_recipients(
    slips: list[dict], employee_map: dict[str, dict], provider: str, period: str,
) -> tuple[list[dict], int, int, int]:
    recipients = []
    seen_employee_ids = set()
    invalid_count = 0
    ambiguous_count = 0
    excluded_count = 0
    wallet_field = "orange_money_number" if provider == "orange_money" else "afrimoney_number"

    for slip in slips:
        employee_id = slip.get("employee_id")
        if not employee_id or employee_id in seen_employee_ids:
            invalid_count += 1
            continue
        seen_employee_ids.add(employee_id)
        employee = employee_map.get(employee_id)
        if not employee:
            invalid_count += 1
            continue

        assigned_provider = _assigned_mobile_money_provider(employee)
        if assigned_provider == "ambiguous":
            ambiguous_count += 1
            continue
        if assigned_provider == "invalid":
            invalid_count += 1
            continue
        if assigned_provider != provider:
            excluded_count += 1
            continue

        wallet = _normalize_wallet_number(employee.get(wallet_field))
        try:
            raw_amount = float(slip.get("net", 0) or 0)
        except (TypeError, ValueError):
            invalid_count += 1
            continue
        if not wallet or not math.isfinite(raw_amount) or raw_amount <= 0:
            invalid_count += 1
            continue
        amount = round(raw_amount, 2)
        if amount <= 0:
            invalid_count += 1
            continue
        recipients.append({
            "id": str(uuid.uuid4()),
            "employee_id": employee_id,
            "employee_name": _employee_name(employee) or slip.get("employee_name", "Employee"),
            "mobile_number": wallet,
            "amount_sle": amount,
            "payment_reference": f"SHCM-{str(period).replace('-', '')}-{uuid.uuid4().hex[:8].upper()}",
            "status": "pending",
            "provider_reference": "",
            "failure_reason": "",
            "reconciliation_history": [],
        })
    return recipients, invalid_count, ambiguous_count, excluded_count


def _employee_name(employee: dict) -> str:
    return " ".join(
        str(employee.get(field) or "").strip()
        for field in ("first_name", "middle_name", "last_name")
        if str(employee.get(field) or "").strip()
    )


def _batch_summary(batch: dict) -> dict:
    return {
        key: batch.get(key)
        for key in (
            "id", "run_id", "period", "provider", "provider_name", "currency", "retry_of", "attempt_number",
            "payment_date", "status", "total_amount_sle", "recipient_count",
            "paid_count", "failed_count", "pending_count", "source_employee_count", "excluded_count", "created_by",
            "created_at", "approved_by", "approved_at", "exported_at",
            "reconciled_at",
        )
    }


def _xml_text(value: object) -> str:
    text = str(value if value is not None else "")
    text = "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)
    return xml_escape(text)


def _column_name(number: int) -> str:
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _build_mobile_money_xlsx(batch: dict) -> bytes:
    rows = [
        ["Provider", batch["provider_name"]],
        ["Payroll Period", batch["period"]],
        ["Payment Date", batch["payment_date"]],
        ["Currency", batch["currency"]],
        ["Employees in payroll", batch.get("source_employee_count", batch["recipient_count"])],
        ["Recipients in this provider batch", batch["recipient_count"]],
        ["Excluded (other provider or bank)", batch.get("excluded_count", 0)],
        [],
        ["Recipient Name", "Mobile Number", "Amount (SLE)", "Payment Reference"],
    ]
    for payment in batch["recipients"]:
        rows.append([
            payment["employee_name"],
            payment["mobile_number"],
            float(payment["amount_sle"]),
            payment["payment_reference"],
        ])
    rows.extend([
        [],
        ["TOTAL", "", float(batch["total_amount_sle"]), ""],
    ])

    sheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for col_number, value in enumerate(row, start=1):
            if value is None or value == "":
                continue
            cell_ref = f"{_column_name(col_number)}{row_number}"
            if isinstance(value, (int, float)):
                cell = f'<c r="{cell_ref}" t="n"><v>{float(value):.2f}</v></c>'
            else:
                cell = (
                    f'<c r="{cell_ref}" t="inlineStr"><is><t xml:space="preserve">'
                    f'{_xml_text(value)}</t></is></c>'
                )
            cells.append(cell)
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="9" topLeftCell="A10" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Mobile Money Batch" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    package_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml)
        workbook.writestr("_rels/.rels", package_rels_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


@router.get("/runs/{rid}/mobile-money-batches")
async def list_run_mobile_money_batches(
    rid: str,
    user: dict = Depends(require_roles("payroll")),
):
    run = await db.payroll_runs.find_one(
        {"id": rid, **tenant_filter(user)}, {"_id": 0, "id": 1},
    )
    if not run:
        raise HTTPException(404, "Payroll run not found")
    batches = await db.mobile_money_batches.find(
        {"run_id": rid, **tenant_filter(user)}, {"_id": 0, "recipients": 0},
    ).sort("created_at", -1).to_list(20)
    return [_batch_summary(batch) for batch in batches]


@router.post("/runs/{rid}/mobile-money-batches")
async def create_run_mobile_money_batch(
    rid: str,
    body: MobileMoneyBatchIn,
    user: dict = Depends(require_roles("payroll")),
):
    scope = tenant_filter(user)
    run = await db.payroll_runs.find_one(
        {"id": rid, **scope}, {"_id": 0},
    )
    if not run:
        raise HTTPException(404, "Payroll run not found")
    if run.get("status") != "completed":
        raise HTTPException(409, "Only a completed payroll run can be disbursed.")
    if str(run.get("currency") or "SLE").upper() != "SLE":
        raise HTTPException(
            409,
            "Mobile-money salary payouts require SLE-denominated payroll; FX conversion is not supported.",
        )
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "features": 1},
    ) or {}
    if (
        "gov_payroll" in (company.get("features") or [])
        and run.get("mof_status") not in ("approved", "released")
    ):
        raise HTTPException(412, "MoF approval is required before preparing this government payroll batch.")

    existing = await db.mobile_money_batches.find_one(
        {"run_id": rid, "provider": body.provider, "retry_of": {"$exists": False}, **scope}, {"_id": 0},
    )
    if existing:
        return {**existing, "already_exists": True}

    slips = run.get("slips", [])
    employee_ids = list({slip.get("employee_id") for slip in slips if slip.get("employee_id")})
    employees = []
    if employee_ids:
        employees = await db.employees.find(
            {"id": {"$in": employee_ids}, **scope},
            {
                "_id": 0, "id": 1, "first_name": 1, "middle_name": 1,
                "last_name": 1, "orange_money_number": 1, "afrimoney_number": 1,
                "mobile_money_provider": 1,
            },
        ).to_list(len(employee_ids))
    employee_map = {employee["id"]: employee for employee in employees}
    recipients, invalid_count, ambiguous_count, excluded_count = _route_mobile_money_recipients(
        slips, employee_map, body.provider, run.get("period", ""),
    )
    if ambiguous_count:
        raise HTTPException(
            422,
            f"{ambiguous_count} employee(s) have both provider wallets but no payout preference. Choose Orange Money or Afrimoney in each employee profile.",
        )
    if invalid_count:
        raise HTTPException(
            422,
            f"{invalid_count} payroll row(s) assigned to {PROVIDERS[body.provider]} have an invalid wallet number, non-positive net pay, or missing/duplicate employee data.",
        )
    if not recipients:
        raise HTTPException(
            422,
            f"No employees are assigned to {PROVIDERS[body.provider]} with a valid wallet in this payroll run.",
        )

    initial_batches = await db.mobile_money_batches.find(
        {"run_id": rid, "retry_of": {"$exists": False}, **scope},
        {"_id": 0, "provider": 1, "recipients.employee_id": 1},
    ).to_list(10)
    already_in_other_provider = {
        payment.get("employee_id")
        for batch in initial_batches
        if batch.get("provider") != body.provider
        for payment in batch.get("recipients", [])
        if payment.get("employee_id")
    }
    overlap = {
        payment["employee_id"] for payment in recipients
        if payment["employee_id"] in already_in_other_provider
    }
    if overlap:
        raise HTTPException(
            409,
            f"{len(overlap)} employee(s) are already included in another provider batch for this payroll run.",
        )
    source_employee_count = len(slips)

    batch_id = str(uuid.uuid4())
    now = iso(now_utc())
    total_amount = round(sum(recipient["amount_sle"] for recipient in recipients), 2)
    batch = {
        "id": batch_id,
        "batch_type": "initial",
        "company_id": user["company_id"],
        "run_id": rid,
        "period": run["period"],
        "provider": body.provider,
        "provider_name": PROVIDERS[body.provider],
        "currency": "SLE",
        "attempt_number": 1,
        "payment_date": body.payment_date.isoformat(),
        "status": "pending_approval",
        "total_amount_sle": total_amount,
        "recipient_count": len(recipients),
        "source_employee_count": source_employee_count,
        "excluded_count": excluded_count,
        "paid_count": 0,
        "failed_count": 0,
        "pending_count": len(recipients),
        "created_by": user["email"],
        "created_at": now,
        "approved_by": None,
        "approved_at": None,
        "exported_at": None,
        "reconciled_at": None,
        "recipients": recipients,
    }
    try:
        await db.mobile_money_batches.insert_one(dict(batch))
    except DuplicateKeyError:
        existing = await db.mobile_money_batches.find_one(
            {"run_id": rid, "provider": body.provider, "retry_of": {"$exists": False}, **scope},
            {"_id": 0},
        )
        if existing:
            return {**existing, "already_exists": True}
        raise
    await audit(
        "mobile_money_batch_created",
        f"payroll_runs/{rid}",
        user,
        {
            "batch_id": batch_id,
            "provider": body.provider,
            "period": run["period"],
            "recipient_count": len(recipients),
            "total_sle": total_amount,
        },
    )
    return batch


@router.post("/mobile-money/batches/{bid}/retry-failed")
async def retry_failed_mobile_money_payments(
    bid: str,
    body: RetryMobileMoneyBatchIn,
    user: dict = Depends(require_roles("payroll")),
):
    scope = tenant_filter(user)
    parent = await db.mobile_money_batches.find_one(
        {"id": bid, **scope}, {"_id": 0},
    )
    if not parent:
        raise HTTPException(404, "Mobile-money batch not found")
    if str(parent.get("currency") or "SLE").upper() != "SLE":
        raise HTTPException(
            409,
            "Mobile-money retry batches require SLE-denominated payroll; FX conversion is not supported.",
        )
    failed = [row for row in parent.get("recipients", []) if row.get("status") == "failed"]
    if not failed:
        raise HTTPException(409, "This batch has no failed payments to retry.")

    existing = await db.mobile_money_batches.find_one(
        {"retry_of": bid, **scope}, {"_id": 0},
    )
    if existing:
        return {**existing, "already_exists": True}

    recipients = []
    for payment in failed:
        recipients.append({
            "id": str(uuid.uuid4()),
            "employee_id": payment["employee_id"],
            "employee_name": payment["employee_name"],
            "mobile_number": payment["mobile_number"],
            "amount_sle": payment["amount_sle"],
            "payment_reference": (
                f"SHCM-{parent['period'].replace('-', '')}-"
                f"{uuid.uuid4().hex[:8].upper()}"
            ),
            "status": "pending",
            "provider_reference": "",
            "failure_reason": "",
            "reconciliation_history": [],
            "retry_of_recipient_id": payment["id"],
        })
    now = iso(now_utc())
    total_amount = round(sum(row["amount_sle"] for row in recipients), 2)
    retry = {
        "id": str(uuid.uuid4()),
        "batch_type": "retry",
        "company_id": user["company_id"],
        "run_id": parent["run_id"],
        "period": parent["period"],
        "provider": parent["provider"],
        "provider_name": parent["provider_name"],
        "currency": "SLE",
        "payment_date": body.payment_date.isoformat(),
        "status": "pending_approval",
        "attempt_number": int(parent.get("attempt_number", 1)) + 1,
        "retry_of": bid,
        "total_amount_sle": total_amount,
        "recipient_count": len(recipients),
        "source_employee_count": len(recipients),
        "excluded_count": 0,
        "paid_count": 0,
        "failed_count": 0,
        "pending_count": len(recipients),
        "created_by": user["email"],
        "created_at": now,
        "approved_by": None,
        "approved_at": None,
        "exported_at": None,
        "reconciled_at": None,
        "recipients": recipients,
    }
    try:
        await db.mobile_money_batches.insert_one(dict(retry))
    except DuplicateKeyError:
        existing = await db.mobile_money_batches.find_one(
            {"retry_of": bid, **scope}, {"_id": 0},
        )
        if existing:
            return {**existing, "already_exists": True}
        raise
    await audit(
        "mobile_money_failed_payments_retry_created",
        f"payroll_runs/{parent['run_id']}",
        user,
        {
            "batch_id": retry["id"],
            "retry_of": bid,
            "provider": retry["provider"],
            "period": retry["period"],
            "recipient_count": len(recipients),
            "total_sle": total_amount,
        },
    )
    return retry


@router.get("/mobile-money/pending-approvals")
async def list_pending_mobile_money_approvals(
    response: Response,
    user: dict = Depends(require_roles("manager", "admin", "superadmin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    batches = await db.mobile_money_batches.find(
        {"status": "pending_approval", **tenant_filter(user)},
        {"_id": 0, "recipients": 0},
    ).sort("created_at", -1).to_list(200)
    return [_batch_summary(batch) for batch in batches]


@router.get("/mobile-money/batches/{bid}")
async def get_mobile_money_batch(
    bid: str,
    response: Response,
    user: dict = Depends(require_roles("payroll", "manager", "admin", "superadmin")),
):
    response.headers["Cache-Control"] = "private, no-store"
    batch = await db.mobile_money_batches.find_one(
        {"id": bid, **tenant_filter(user)}, {"_id": 0},
    )
    if not batch:
        raise HTTPException(404, "Mobile-money batch not found")
    return batch


@router.post("/mobile-money/batches/{bid}/approve")
async def approve_mobile_money_batch(
    bid: str,
    user: dict = Depends(require_roles("manager", "admin", "superadmin")),
):
    if user.get("role") not in ("manager", "admin", "superadmin"):
        raise HTTPException(403, "Only a manager or admin can approve a payment batch.")
    batch = await db.mobile_money_batches.find_one(
        {"id": bid, **tenant_filter(user)}, {"_id": 0},
    )
    if not batch:
        raise HTTPException(404, "Mobile-money batch not found")
    if batch.get("created_by") == user.get("email"):
        raise HTTPException(403, "A different manager must approve this payment batch.")
    if batch.get("status") != "pending_approval":
        raise HTTPException(409, f"Cannot approve a batch with status {batch.get('status')}.")
    now = iso(now_utc())
    result = await db.mobile_money_batches.update_one(
        {"id": bid, **tenant_filter(user), "status": "pending_approval"},
        {"$set": {"status": "approved", "approved_by": user["email"], "approved_at": now}},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "Another manager changed this batch. Refresh and review its current status.")
    approved = await db.mobile_money_batches.find_one(
        {"id": bid, **tenant_filter(user)}, {"_id": 0},
    )
    await audit(
        "mobile_money_batch_approved",
        f"payroll_runs/{batch['run_id']}",
        user,
        {"batch_id": bid, "provider": batch["provider"], "period": batch["period"]},
    )
    return approved


@router.get("/mobile-money/batches/{bid}/workbook")
async def export_mobile_money_workbook(
    bid: str,
    user: dict = Depends(require_roles("payroll")),
):
    scope = tenant_filter(user)
    batch = await db.mobile_money_batches.find_one(
        {"id": bid, **scope}, {"_id": 0},
    )
    if not batch:
        raise HTTPException(404, "Mobile-money batch not found")
    if batch.get("status") != "approved" or batch.get("exported_at"):
        raise HTTPException(
            409,
            "This batch workpaper has already been exported or changed. Do not upload another copy; reconcile its results or prepare a failed-payment retry.",
        )
    pending_recipients = [
        recipient for recipient in batch.get("recipients", [])
        if recipient.get("status") == "pending"
    ]
    if not pending_recipients:
        raise HTTPException(409, "There are no pending payments left to export. Create a retry batch for failed payments.")
    export_batch = {
        **batch,
        "recipients": pending_recipients,
        "recipient_count": len(pending_recipients),
        "total_amount_sle": round(
            sum(float(recipient["amount_sle"]) for recipient in pending_recipients), 2,
        ),
    }
    payload = _build_mobile_money_xlsx(export_batch)
    exported_at = iso(now_utc())
    claimed = await db.mobile_money_batches.update_one(
        {"id": bid, **scope, "status": "approved", "exported_at": None},
        {"$set": {"status": "exported", "exported_at": exported_at}},
    )
    if claimed.modified_count != 1:
        raise HTTPException(
            409,
            "Another user already exported or changed this batch. Do not upload another copy; refresh the batch.",
        )
    await audit(
        "mobile_money_batch_workbook_exported",
        f"payroll_runs/{batch['run_id']}",
        user,
        {"batch_id": bid, "provider": batch["provider"], "period": batch["period"]},
    )
    filename = (
        f"SaloneHCM-Mobile-Money-Workpaper-{batch['provider']}-{batch['period']}.xlsx"
    )
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/mobile-money/batches/{bid}/recipients/{pid}/reconcile")
async def reconcile_mobile_money_recipient(
    bid: str,
    pid: str,
    body: RecipientReconciliationIn,
    user: dict = Depends(require_roles("payroll")),
):
    scope = tenant_filter(user)
    batch = await db.mobile_money_batches.find_one(
        {"id": bid, **scope}, {"_id": 0},
    )
    if not batch:
        raise HTTPException(404, "Mobile-money batch not found")
    if batch.get("status") not in ("exported", "partially_reconciled", "reconciled"):
        raise HTTPException(409, "Export the approved batch before reconciling provider results.")
    recipient = next((row for row in batch.get("recipients", []) if row.get("id") == pid), None)
    if not recipient:
        raise HTTPException(404, "Batch recipient not found")

    provider_reference = (body.provider_reference or "").strip()
    failure_reason = (body.failure_reason or "").strip()
    if body.status == "paid" and not provider_reference:
        raise HTTPException(422, "Enter the provider transaction reference for a successful payment.")
    if body.status == "failed" and not failure_reason:
        raise HTTPException(422, "Enter a reason for the failed payment.")
    already_recorded = (
        recipient.get("status") == body.status
        and recipient.get("provider_reference", "") == provider_reference
        and recipient.get("failure_reason", "") == failure_reason
    )
    if not already_recorded and recipient.get("status", "pending") != "pending":
        raise HTTPException(
            409,
            "This recipient is already reconciled. Create a retry batch for failed payments.",
        )

    recorded_at = iso(now_utc())
    if not already_recorded:
        event = {
            "status": body.status,
            "provider_reference": provider_reference,
            "failure_reason": failure_reason,
            "recorded_by": user["email"],
            "recorded_at": recorded_at,
        }
        result = await db.mobile_money_batches.update_one(
            {
                "id": bid,
                **scope,
                "recipients": {"$elemMatch": {"id": pid, "status": "pending"}},
            },
            {
                "$set": {
                    "recipients.$.status": body.status,
                    "recipients.$.provider_reference": provider_reference,
                    "recipients.$.failure_reason": failure_reason,
                    "recipients.$.reconciled_at": recorded_at,
                },
                "$push": {"recipients.$.reconciliation_history": event},
            },
        )
        if result.matched_count != 1:
            raise HTTPException(
                409,
                "This recipient was reconciled by another user. Refresh the batch before continuing.",
            )

    # Recalculate from the latest recipient states in one atomic update. Concurrent
    # reconciliations can finish in any order without leaving stale batch totals.
    await db.mobile_money_batches.update_one(
        {"id": bid, **scope},
        [
            {"$set": {
                "paid_count": {"$size": {"$filter": {
                    "input": {"$ifNull": ["$recipients", []]},
                    "as": "recipient",
                    "cond": {"$eq": ["$recipient.status", "paid"]},
                }}},
                "failed_count": {"$size": {"$filter": {
                    "input": {"$ifNull": ["$recipients", []]},
                    "as": "recipient",
                    "cond": {"$eq": ["$recipient.status", "failed"]},
                }}},
                "pending_count": {"$size": {"$filter": {
                    "input": {"$ifNull": ["$recipients", []]},
                    "as": "recipient",
                    "cond": {"$eq": ["$recipient.status", "pending"]},
                }}},
            }},
            {"$set": {
                "status": {"$cond": [
                    {"$eq": ["$pending_count", 0]},
                    "reconciled",
                    {"$cond": [
                        {"$eq": [{"$add": ["$paid_count", "$failed_count"]}, 0]},
                        "exported",
                        "partially_reconciled",
                    ]},
                ]},
                "reconciled_at": {"$cond": [
                    {"$eq": ["$pending_count", 0]},
                    {"$ifNull": ["$reconciled_at", recorded_at]},
                    None,
                ]},
            }},
        ],
    )
    updated = await db.mobile_money_batches.find_one(
        {"id": bid, **scope}, {"_id": 0},
    )
    if not already_recorded:
        await audit(
            "mobile_money_payment_reconciled",
            f"payroll_runs/{batch['run_id']}",
            user,
            {
                "batch_id": bid,
                "recipient_id": pid,
                "status": body.status,
                "provider_reference_recorded": bool(provider_reference),
            },
        )
    return updated
