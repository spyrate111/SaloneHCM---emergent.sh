"""SLE mobile-money payroll batches with independent approval and reconciliation.

Provider API calls are intentionally not implemented until Orange/Africell provide
confirmed employer payout specifications. The workbook is a provider-neutral
workpaper for manual use with each operator's approved salary-payment flow.
"""
import io
import re
import uuid
import zipfile
from datetime import date
from typing import Literal, Optional
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import audit, db, iso, now_utc, require_roles, tenant_filter

router = APIRouter(prefix="/payroll", tags=["mobile-money"])
PROVIDERS = {
    "orange_money": "Orange Money",
    "afrimoney": "Afrimoney",
}


class MobileMoneyBatchIn(BaseModel):
    provider: Literal["orange_money", "afrimoney"]
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
            "id", "run_id", "period", "provider", "provider_name", "currency",
            "payment_date", "status", "total_amount_sle", "recipient_count",
            "paid_count", "failed_count", "pending_count", "created_by",
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
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="6" topLeftCell="A7" '
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
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "features": 1},
    ) or {}
    if (
        "gov_payroll" in (company.get("features") or [])
        and run.get("mof_status") not in ("approved", "released")
    ):
        raise HTTPException(412, "MoF approval is required before preparing this government payroll batch.")

    existing = await db.mobile_money_batches.find_one(
        {"run_id": rid, "provider": body.provider, **scope}, {"_id": 0},
    )
    if existing:
        return {**existing, "already_exists": True}

    employees = await db.employees.find(scope, {"_id": 0}).to_list(2000)
    employee_map = {employee["id"]: employee for employee in employees}
    wallet_field = (
        "orange_money_number" if body.provider == "orange_money"
        else "afrimoney_number"
    )
    invalid = []
    recipients = []
    for slip in run.get("slips", []):
        employee = employee_map.get(slip.get("employee_id"), {})
        wallet = _normalize_wallet_number(employee.get(wallet_field))
        amount = round(float(slip.get("net", 0) or 0), 2)
        if not wallet or amount <= 0:
            invalid.append(slip.get("employee_name", "Employee"))
            continue
        recipients.append({
            "id": str(uuid.uuid4()),
            "employee_id": slip["employee_id"],
            "employee_name": _employee_name(employee) or slip.get("employee_name", "Employee"),
            "mobile_number": wallet,
            "amount_sle": amount,
            "payment_reference": (
                f"SHCM-{run['period'].replace('-', '')}-"
                f"{uuid.uuid4().hex[:8].upper()}"
            ),
            "status": "pending",
            "provider_reference": "",
            "failure_reason": "",
            "reconciliation_history": [],
        })
    if invalid:
        raise HTTPException(
            422,
            f"{len(invalid)} employee(s) have a missing/invalid {PROVIDERS[body.provider]} wallet number or non-positive net pay. Correct the records and prepare the batch again.",
        )
    if not recipients:
        raise HTTPException(422, "This payroll run has no positive net-pay recipients.")

    batch_id = str(uuid.uuid4())
    now = iso(now_utc())
    total_amount = round(sum(recipient["amount_sle"] for recipient in recipients), 2)
    batch = {
        "id": batch_id,
        "company_id": user["company_id"],
        "run_id": rid,
        "period": run["period"],
        "provider": body.provider,
        "provider_name": PROVIDERS[body.provider],
        "currency": "SLE",
        "payment_date": body.payment_date.isoformat(),
        "status": "pending_approval",
        "total_amount_sle": total_amount,
        "recipient_count": len(recipients),
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
    await db.mobile_money_batches.insert_one(dict(batch))
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


@router.get("/mobile-money/pending-approvals")
async def list_pending_mobile_money_approvals(
    user: dict = Depends(require_roles("manager", "admin", "superadmin")),
):
    batches = await db.mobile_money_batches.find(
        {"status": "pending_approval", **tenant_filter(user)},
        {"_id": 0, "recipients": 0},
    ).sort("created_at", -1).to_list(200)
    return [_batch_summary(batch) for batch in batches]


@router.get("/mobile-money/batches/{bid}")
async def get_mobile_money_batch(
    bid: str,
    user: dict = Depends(require_roles("payroll", "manager", "admin", "superadmin")),
):
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
    await db.mobile_money_batches.update_one(
        {"id": bid, **tenant_filter(user), "status": "pending_approval"},
        {"$set": {"status": "approved", "approved_by": user["email"], "approved_at": now}},
    )
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
    if batch.get("status") not in ("approved", "exported", "partially_reconciled", "reconciled"):
        raise HTTPException(409, "A manager must approve this batch before export.")
    payload = _build_mobile_money_xlsx(batch)
    exported_at = batch.get("exported_at") or iso(now_utc())
    next_status = "exported" if batch.get("status") == "approved" else batch["status"]
    await db.mobile_money_batches.update_one(
        {"id": bid, **scope},
        {"$set": {"status": next_status, "exported_at": exported_at}},
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
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    if (
        recipient.get("status") == body.status
        and recipient.get("provider_reference", "") == provider_reference
        and recipient.get("failure_reason", "") == failure_reason
    ):
        return batch

    recorded_at = iso(now_utc())
    event = {
        "status": body.status,
        "provider_reference": provider_reference,
        "failure_reason": failure_reason,
        "recorded_by": user["email"],
        "recorded_at": recorded_at,
    }
    await db.mobile_money_batches.update_one(
        {"id": bid, **scope, "recipients.id": pid},
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
    updated = await db.mobile_money_batches.find_one(
        {"id": bid, **scope}, {"_id": 0},
    )
    statuses = [row.get("status", "pending") for row in updated["recipients"]]
    updated["paid_count"] = statuses.count("paid")
    updated["failed_count"] = statuses.count("failed")
    updated["pending_count"] = statuses.count("pending")
    if updated["pending_count"] == len(statuses):
        updated["status"] = "exported"
    elif updated["pending_count"]:
        updated["status"] = "partially_reconciled"
    else:
        updated["status"] = "reconciled"
        updated["reconciled_at"] = recorded_at
    await db.mobile_money_batches.update_one(
        {"id": bid, **scope},
        {"$set": {
            "status": updated["status"],
            "paid_count": updated["paid_count"],
            "failed_count": updated["failed_count"],
            "pending_count": updated["pending_count"],
            "reconciled_at": updated.get("reconciled_at"),
        }},
    )
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
