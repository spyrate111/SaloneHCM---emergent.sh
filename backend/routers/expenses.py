"""Expense claims: submit → manager/HR approve → reimbursed on next payroll run."""
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from core import (db, get_current_user, require_roles, can_role, audit,
                  tenant_filter, with_tenant, now_utc, iso)
from storage import put_object, get_object, APP_NAME
import push_service

router = APIRouter(prefix="/expenses", tags=["expenses"])

CATEGORIES = {"transport", "meals", "accommodation", "supplies", "other"}
RECEIPT_MIME = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}
MAX_BYTES = 5 * 1024 * 1024


async def _visible_filter(user: dict) -> dict:
    """hr/admin/auditor: all claims; manager: own + reports; employee: own."""
    tf = tenant_filter(user)
    if can_role(user, "hr", "auditor"):
        return tf
    my_eid = user.get("employee_id")
    if not my_eid:
        return {**tf, "employee_id": "__none__"}
    if user.get("role") == "manager":
        reports = await db.employees.find(
            {**tf, "manager_id": my_eid}, {"_id": 0, "id": 1}).to_list(500)
        return {**tf, "employee_id": {"$in": [my_eid] + [r["id"] for r in reports]}}
    return {**tf, "employee_id": my_eid}


@router.post("")
async def submit_claim(
    bg: BackgroundTasks,
    description: str = Form(...),
    amount_sle: float = Form(...),
    category: str = Form(...),
    receipt: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
):
    if category not in CATEGORIES:
        raise HTTPException(422, f"Category must be one of: {', '.join(sorted(CATEGORIES))}")
    if amount_sle <= 0:
        raise HTTPException(422, "Amount must be greater than zero")
    eid = user.get("employee_id")
    if not eid:
        raise HTTPException(400, "Your account has no linked employee record — ask HR to link one")
    emp = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee record not found")

    receipt_meta = None
    if receipt is not None:
        if receipt.content_type not in RECEIPT_MIME:
            raise HTTPException(415, "Receipt must be a JPG, PNG or PDF")
        data = await receipt.read()
        if not data:
            raise HTTPException(400, "Empty receipt file")
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Receipt too large (max 5MB)")
        ext = RECEIPT_MIME[receipt.content_type]
        path = f"{APP_NAME}/{user['company_id']}/receipts/{eid}/{uuid.uuid4()}.{ext}"
        try:
            res = put_object(path, data, receipt.content_type)
        except Exception as e:
            raise HTTPException(502, f"Receipt upload failed: {e}") from e
        receipt_meta = {"storage_path": res.get("path", path),
                        "content_type": receipt.content_type,
                        "filename": receipt.filename or f"receipt.{ext}"}

    cid = str(uuid.uuid4())
    doc = with_tenant({
        "id": cid,
        "employee_id": eid,
        "employee_name": f'{emp.get("first_name", "")} {emp.get("last_name", "")}'.strip(),
        "description": description.strip()[:500],
        "amount_sle": round(float(amount_sle), 2),
        "category": category,
        "receipt": receipt_meta,
        "status": "pending",
        "payroll_run_id": None,
        "created_at": iso(now_utc()),
    }, user)
    await db.expense_claims.insert_one(doc)
    doc.pop("_id", None)
    await audit("expense_claim_submitted", f"expense_claims/{cid}", user,
                {"amount_sle": doc["amount_sle"], "category": category})
    if emp.get("manager_id"):
        bg.add_task(push_service.fanout_to_employee, emp["manager_id"], {
            "title": "New expense claim",
            "body": f'{doc["employee_name"]} — SLE {doc["amount_sle"]:,.2f} ({category})',
            "url": f"/expenses?claim={cid}",
            "kind": "expense_claim",
        })
    if doc.get("receipt"):
        doc["receipt"] = {"filename": doc["receipt"]["filename"]}
    return doc


@router.get("")
async def list_claims(user: dict = Depends(get_current_user)):
    q = await _visible_filter(user)
    rows = await db.expense_claims.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for r in rows:
        if r.get("receipt"):
            r["receipt"] = {"filename": r["receipt"]["filename"]}
    return rows


@router.get("/pending-reimbursements")
async def pending_reimbursements(user: dict = Depends(require_roles("payroll"))):
    """Approved, not-yet-reimbursed claims — what the next payroll run will add."""
    rows = await db.expense_claims.find(
        {**tenant_filter(user), "status": "approved", "payroll_run_id": None},
        {"_id": 0, "id": 1, "employee_id": 1, "employee_name": 1,
         "amount_sle": 1, "category": 1}).to_list(2000)
    by_emp: dict = {}
    for r in rows:
        b = by_emp.setdefault(r["employee_id"], {"employee_id": r["employee_id"],
                                                 "employee_name": r["employee_name"],
                                                 "total": 0.0, "count": 0})
        b["total"] = round(b["total"] + r["amount_sle"], 2)
        b["count"] += 1
    return {"total": round(sum(r["amount_sle"] for r in rows), 2),
            "count": len(rows),
            "by_employee": sorted(by_emp.values(), key=lambda x: -x["total"])}


@router.put("/{cid}/decision")
async def decide_claim(cid: str, body: dict, bg: BackgroundTasks,
                       user: dict = Depends(get_current_user)):
    status = (body or {}).get("status")
    if status not in ("approved", "rejected"):
        raise HTTPException(422, "status must be 'approved' or 'rejected'")
    claim = await db.expense_claims.find_one({"id": cid, **tenant_filter(user)}, {"_id": 0})
    if not claim:
        raise HTTPException(404, "Claim not found")
    if claim["status"] != "pending":
        raise HTTPException(409, "Claim already decided")
    if claim["employee_id"] == user.get("employee_id"):
        raise HTTPException(403, "You cannot decide your own claim")
    if not can_role(user, "hr"):
        emp = await db.employees.find_one(
            {"id": claim["employee_id"], **tenant_filter(user)}, {"_id": 0, "manager_id": 1})
        is_mgr = (user.get("role") == "manager" and emp
                  and emp.get("manager_id") == user.get("employee_id"))
        if not is_mgr:
            raise HTTPException(403, "Only the employee's manager, HR or an admin may decide")
    note = ((body or {}).get("note") or "").strip()[:300]
    await db.expense_claims.update_one({"id": cid}, {"$set": {
        "status": status,
        "decided_by": user.get("name") or user["email"],
        "decided_at": iso(now_utc()),
        "decision_note": note,
    }})
    await audit(f"expense_claim_{status}", f"expense_claims/{cid}", user,
                {"employee": claim["employee_name"], "amount_sle": claim["amount_sle"]})
    body_txt = f'Your {claim["category"]} claim of SLE {claim["amount_sle"]:,.2f} was {status}'
    if status == "rejected" and note:
        body_txt += f" — {note}"
    bg.add_task(push_service.fanout_to_employee, claim["employee_id"], {
        "title": f"Expense claim {status}",
        "body": body_txt,
        "url": f"/expenses?claim={cid}",
        "kind": "expense_claim",
    })
    return {"ok": True, "status": status}


@router.get("/{cid}/receipt")
async def get_receipt(cid: str, user: dict = Depends(get_current_user)):
    q = await _visible_filter(user)
    if can_role(user, "payroll"):  # payroll may verify receipts pre-run
        q = tenant_filter(user)
    claim = await db.expense_claims.find_one({"id": cid, **q}, {"_id": 0})
    if not claim:
        raise HTTPException(404, "Claim not found")
    if not claim.get("receipt"):
        raise HTTPException(404, "No receipt attached")
    data, ct = get_object(claim["receipt"]["storage_path"])
    return Response(data, media_type=ct or claim["receipt"]["content_type"],
                    headers={"Content-Disposition":
                             f'inline; filename="{claim["receipt"]["filename"]}"'})
