"""Centralized Payroll Voucher Repository — branch submission + approval workflow.

Every branch/office submits its monthly payroll voucher into ONE central
repository. Workflow:
    draft → [pending_supervisor] → submitted → under_review → approved → payment_authorized
Returned-for-correction is possible at every stage before payment authorization.
Vouchers are immutable after submission unless officially returned. Every
transition appends to `status_history` and is audit-logged.

Anti-fraud rails:
  * one voucher per (branch, period) — 409 on duplicates
  * an employee cannot appear on two active vouchers for the same period
  * the voucher creator can never finance-approve their own voucher
  * dual control on payment: authorizer must differ from creator AND approver
  * return-for-correction requires a written reason (≥10 chars)
  * payment_authorized vouchers are terminal — no edits, no returns
"""
from __future__ import annotations
import uuid
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import (
    db, get_current_user, require_admin, require_feature,
    tenant_filter, with_tenant, is_admin, audit, iso, now_utc,
)

FEATURE = "payroll_vouchers"

branches_router = APIRouter(
    prefix="/branches", tags=["branches"],
    dependencies=[Depends(require_feature(FEATURE))],
)
vouchers_router = APIRouter(
    prefix="/vouchers", tags=["vouchers"],
    dependencies=[Depends(require_feature(FEATURE))],
)

RETURNABLE = {"pending_supervisor", "submitted", "under_review", "approved"}
ACTIVE_STATUSES = {"pending_supervisor", "submitted", "under_review", "approved", "payment_authorized"}


def _is_finance(user: dict) -> bool:
    return is_admin(user) or bool(user.get("finance_officer"))


def _hist(user: dict, action: str, frm: Optional[str], to: str, note: str = "") -> dict:
    return {
        "action": action, "from": frm, "to": to,
        "by_email": user["email"], "by_name": user.get("name"),
        "by_role": user.get("role"), "at": iso(now_utc()), "note": note or "",
    }


def _totals(items: list[dict]) -> dict:
    return {
        "employee_count": len(items),
        "gross": round(sum(i["gross"] for i in items), 2),
        "paye": round(sum(i["paye"] for i in items), 2),
        "nassit_employee": round(sum(i["nassit_employee"] for i in items), 2),
        "loan_deductions": round(sum(i["loan_deduction"] for i in items), 2),
        "net": round(sum(i["net"] for i in items), 2),
    }


# ============================================================
# Branches / Offices CRUD
# ============================================================

class BranchIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    code: str = Field(..., min_length=2, max_length=20)
    region: Optional[str] = Field(default="", max_length=80)
    ministry: Optional[str] = Field(default="", max_length=120)
    supervisor_user_id: Optional[str] = None


class BranchPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    region: Optional[str] = Field(default=None, max_length=80)
    ministry: Optional[str] = Field(default=None, max_length=120)
    supervisor_user_id: Optional[str] = None


async def _resolve_supervisor(uid: Optional[str], user: dict) -> dict:
    if not uid:
        return {"supervisor_user_id": None, "supervisor_email": None, "supervisor_name": None}
    u = await db.users.find_one({"id": uid, **tenant_filter(user)}, {"_id": 0, "id": 1, "email": 1, "name": 1})
    if not u:
        raise HTTPException(404, "Supervisor user not found in this tenant")
    return {"supervisor_user_id": u["id"], "supervisor_email": u["email"], "supervisor_name": u["name"]}


@branches_router.get("")
async def list_branches(user: dict = Depends(get_current_user)):
    rows = await db.branches.find(tenant_filter(user), {"_id": 0}).sort("name", 1).to_list(200)
    for b in rows:
        b["employee_count"] = await db.employees.count_documents(
            {**tenant_filter(user), "branch_id": b["id"]})
    return rows


@branches_router.post("")
async def create_branch(body: BranchIn, user: dict = Depends(require_admin)):
    code = body.code.strip().upper()
    if await db.branches.find_one({**tenant_filter(user), "code": code}):
        raise HTTPException(409, f"Branch code '{code}' already exists")
    sup = await _resolve_supervisor(body.supervisor_user_id, user)
    doc = with_tenant({
        "id": str(uuid.uuid4()), "name": body.name.strip(), "code": code,
        "region": body.region or "", "ministry": body.ministry or "",
        **sup,
        "created_by": user["email"], "created_at": iso(now_utc()),
    }, user)
    await db.branches.insert_one(doc)
    await audit("branch_create", f"branches/{doc['id']}", user, {"code": code, "name": doc["name"]})
    doc.pop("_id", None)
    doc["employee_count"] = 0
    return doc


@branches_router.patch("/{bid}")
async def update_branch(bid: str, body: BranchPatch, user: dict = Depends(require_admin)):
    b = await db.branches.find_one({"id": bid, **tenant_filter(user)}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Branch not found")
    updates = {k: v for k, v in body.model_dump(exclude={"supervisor_user_id"}).items() if v is not None}
    if "supervisor_user_id" in body.model_fields_set:
        updates.update(await _resolve_supervisor(body.supervisor_user_id, user))
    if not updates:
        raise HTTPException(422, "Nothing to update")
    await db.branches.update_one({"id": bid, **tenant_filter(user)}, {"$set": updates})
    await audit("branch_update", f"branches/{bid}", user, updates)
    return {**b, **updates}


@branches_router.delete("/{bid}")
async def delete_branch(bid: str, user: dict = Depends(require_admin)):
    b = await db.branches.find_one({"id": bid, **tenant_filter(user)}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Branch not found")
    if await db.payroll_vouchers.find_one({**tenant_filter(user), "branch_id": bid}, {"_id": 1}):
        raise HTTPException(409, "Branch has payroll vouchers — cannot delete (audit record)")
    await db.employees.update_many({**tenant_filter(user), "branch_id": bid}, {"$unset": {"branch_id": ""}})
    await db.branches.delete_one({"id": bid, **tenant_filter(user)})
    await audit("branch_delete", f"branches/{bid}", user, {"code": b["code"]})
    return {"ok": True}


class AssignIn(BaseModel):
    employee_ids: list[str] = Field(..., min_length=1)
    unassign: bool = False


@branches_router.post("/{bid}/assign")
async def assign_employees(bid: str, body: AssignIn, user: dict = Depends(require_admin)):
    b = await db.branches.find_one({"id": bid, **tenant_filter(user)}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Branch not found")
    q = {**tenant_filter(user), "id": {"$in": body.employee_ids}}
    if body.unassign:
        res = await db.employees.update_many(q, {"$unset": {"branch_id": ""}})
    else:
        res = await db.employees.update_many(q, {"$set": {"branch_id": bid}})
    await audit("branch_assign", f"branches/{bid}", user,
                {"count": res.modified_count, "unassign": body.unassign})
    return {"ok": True, "modified": res.modified_count}


@branches_router.get("/{bid}/employees")
async def branch_employees(bid: str, user: dict = Depends(get_current_user)):
    """Employees available to a voucher for this branch (branch members + unassigned).
    Visible to finance/admin and the branch supervisor."""
    b = await db.branches.find_one({"id": bid, **tenant_filter(user)}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Branch not found")
    if not (_is_finance(user) or b.get("supervisor_user_id") == user["id"]):
        raise HTTPException(403, "Not authorised for this branch")
    rows = await db.employees.find(
        {**tenant_filter(user), "status": "active",
         "$or": [{"branch_id": bid}, {"branch_id": {"$exists": False}}, {"branch_id": None}]},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "department": 1,
         "basic_salary_sle": 1, "allowances_sle": 1, "branch_id": 1},
    ).sort("first_name", 1).to_list(2000)
    return rows


# ============================================================
# Voucher repository
# ============================================================

class LineItemIn(BaseModel):
    employee_id: str
    gross: float = Field(..., ge=0)
    paye: float = Field(default=0, ge=0)
    nassit_employee: float = Field(default=0, ge=0)
    loan_deduction: float = Field(default=0, ge=0)
    net: Optional[float] = None


class VoucherIn(BaseModel):
    branch_id: str
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    line_items: list[LineItemIn] = Field(..., min_length=1)
    note: Optional[str] = Field(default="", max_length=500)


class VoucherPatch(BaseModel):
    line_items: list[LineItemIn] = Field(..., min_length=1)


class ActionIn(BaseModel):
    note: Optional[str] = Field(default="", max_length=500)


class ReturnIn(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)


async def _visible_filter(user: dict) -> dict:
    if _is_finance(user):
        return dict(tenant_filter(user))
    sup = await db.branches.find(
        {**tenant_filter(user), "supervisor_user_id": user["id"]}, {"_id": 0, "id": 1}).to_list(100)
    ids = [b["id"] for b in sup]
    return {**tenant_filter(user), "$or": [{"branch_id": {"$in": ids}}, {"created_by": user["email"]}]}


async def _get_voucher(vid: str, user: dict) -> dict:
    v = await db.payroll_vouchers.find_one({"id": vid, **(await _visible_filter(user))}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Voucher not found")
    return v


async def _resolve_items(items: list[LineItemIn], user: dict, period: str,
                         branch_id: str, exclude_voucher_id: Optional[str] = None) -> list[dict]:
    seen = set()
    out = []
    for li in items:
        if li.employee_id in seen:
            raise HTTPException(422, "Duplicate employee on voucher — double-pay guard")
        seen.add(li.employee_id)
        emp = await db.employees.find_one(
            {"id": li.employee_id, **tenant_filter(user)},
            {"_id": 0, "first_name": 1, "last_name": 1, "branch_id": 1})
        if not emp:
            raise HTTPException(404, f"Employee {li.employee_id} not found")
        if emp.get("branch_id") and emp["branch_id"] != branch_id:
            raise HTTPException(422, f"{emp['first_name']} {emp['last_name']} belongs to another branch")
        dup_q = {**tenant_filter(user), "period": period, "status": {"$ne": "returned"},
                 "line_items.employee_id": li.employee_id}
        if exclude_voucher_id:
            dup_q["id"] = {"$ne": exclude_voucher_id}
        dup = await db.payroll_vouchers.find_one(dup_q, {"_id": 0, "voucher_ref": 1})
        if dup:
            raise HTTPException(
                422, f"{emp['first_name']} {emp['last_name']} is already on voucher "
                     f"{dup['voucher_ref']} for {period} — double-pay guard")
        net = li.net if li.net is not None else round(
            li.gross - li.paye - li.nassit_employee - li.loan_deduction, 2)
        out.append({
            "employee_id": li.employee_id,
            "employee_name": f"{emp['first_name']} {emp['last_name']}",
            "gross": round(li.gross, 2), "paye": round(li.paye, 2),
            "nassit_employee": round(li.nassit_employee, 2),
            "loan_deduction": round(li.loan_deduction, 2), "net": round(net, 2),
        })
    return out


def _new_voucher(user: dict, branch: dict, period: str, items: list[dict],
                 source: str, run_id: Optional[str] = None, note: str = "") -> dict:
    return with_tenant({
        "id": str(uuid.uuid4()),
        "voucher_ref": f"PV-{period.replace('-', '')}-{secrets.token_hex(2).upper()}",
        "branch_id": branch["id"], "branch_name": branch["name"], "branch_code": branch["code"],
        "period": period, "source": source, "run_id": run_id, "note": note or "",
        "line_items": items, "totals": _totals(items),
        "status": "draft", "revision": 1,
        "status_history": [_hist(user, "created", None, "draft", note)],
        "created_by": user["email"], "created_by_name": user.get("name"),
        "created_at": iso(now_utc()), "updated_at": iso(now_utc()),
    }, user)


@vouchers_router.get("/summary")
async def voucher_summary(period: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = await _visible_filter(user)
    if period:
        q["period"] = period
    rows = await db.payroll_vouchers.find(q, {"_id": 0, "line_items": 0, "status_history": 0}).to_list(2000)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    branches = await db.branches.find(tenant_filter(user), {"_id": 0, "id": 1, "name": 1}).to_list(200)
    submitted_ids = {r["branch_id"] for r in rows if r["status"] != "draft"}
    missing = [b["name"] for b in branches if b["id"] not in submitted_ids]
    return {
        "count": len(rows), "by_status": by_status,
        "total_net": round(sum(r["totals"]["net"] for r in rows), 2),
        "branches_total": len(branches),
        "branches_submitted": len(branches) - len(missing),
        "missing_branches": missing,
    }


@vouchers_router.post("/generate-from-run/{run_id}")
async def generate_from_run(run_id: str, user: dict = Depends(get_current_user)):
    """Split a completed payroll run into one draft voucher per branch."""
    if not _is_finance(user):
        raise HTTPException(403, "Finance officers or admins only")
    run = await db.payroll_runs.find_one({"id": run_id, **tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Payroll run not found")
    period = run["period"]
    emps = await db.employees.find(tenant_filter(user), {"_id": 0, "id": 1, "branch_id": 1}).to_list(3000)
    branch_of = {e["id"]: e.get("branch_id") for e in emps}
    groups: dict[str, list] = {}
    unassigned: list[str] = []
    for s in run.get("slips", []):
        bid = branch_of.get(s["employee_id"])
        if not bid:
            unassigned.append(s["employee_name"])
            continue
        groups.setdefault(bid, []).append({
            "employee_id": s["employee_id"], "employee_name": s["employee_name"],
            "gross": s["gross"], "paye": s["paye"], "nassit_employee": s["nassit_employee"],
            "loan_deduction": s.get("loan_deduction", 0), "net": s["net"],
        })
    created, skipped = [], []
    for bid, items in groups.items():
        branch = await db.branches.find_one({"id": bid, **tenant_filter(user)}, {"_id": 0})
        if not branch:
            unassigned.extend(i["employee_name"] for i in items)
            continue
        dup = await db.payroll_vouchers.find_one(
            {**tenant_filter(user), "branch_id": bid, "period": period},
            {"_id": 0, "voucher_ref": 1})
        if dup:
            skipped.append({"branch": branch["name"], "voucher_ref": dup["voucher_ref"]})
            continue
        doc = _new_voucher(user, branch, period, items, source="auto_run", run_id=run_id)
        await db.payroll_vouchers.insert_one(doc)
        await audit("voucher_create", f"payroll_vouchers/{doc['id']}", user,
                    {"source": "auto_run", "branch": branch["name"], "period": period})
        created.append({"id": doc["id"], "voucher_ref": doc["voucher_ref"],
                        "branch": branch["name"], "net": doc["totals"]["net"],
                        "employees": len(items)})
    return {"created": created, "skipped_existing": skipped, "period": period,
            "unassigned_count": len(unassigned), "unassigned": unassigned[:20]}


@vouchers_router.get("")
async def list_vouchers(period: Optional[str] = None, branch_id: Optional[str] = None,
                        status: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = await _visible_filter(user)
    if period:
        q["period"] = period
    if branch_id:
        q["branch_id"] = branch_id
    if status:
        q["status"] = status
    return await db.payroll_vouchers.find(
        q, {"_id": 0, "line_items": 0, "status_history": 0}).sort("updated_at", -1).to_list(1000)


@vouchers_router.post("")
async def create_voucher(body: VoucherIn, user: dict = Depends(get_current_user)):
    branch = await db.branches.find_one({"id": body.branch_id, **tenant_filter(user)}, {"_id": 0})
    if not branch:
        raise HTTPException(404, "Branch not found")
    if not (_is_finance(user) or branch.get("supervisor_user_id") == user["id"]):
        raise HTTPException(403, "Only finance/admin or the branch supervisor can create vouchers for this branch")
    dup = await db.payroll_vouchers.find_one(
        {**tenant_filter(user), "branch_id": body.branch_id, "period": body.period},
        {"_id": 0, "voucher_ref": 1})
    if dup:
        raise HTTPException(409, f"Voucher {dup['voucher_ref']} already exists for this branch and period")
    items = await _resolve_items(body.line_items, user, body.period, body.branch_id)
    doc = _new_voucher(user, branch, body.period, items, source="manual", note=body.note)
    await db.payroll_vouchers.insert_one(doc)
    await audit("voucher_create", f"payroll_vouchers/{doc['id']}", user,
                {"source": "manual", "branch": branch["name"], "period": body.period})
    doc.pop("_id", None)
    return doc


@vouchers_router.get("/{vid}")
async def get_voucher(vid: str, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    b = await db.branches.find_one(
        {"id": v["branch_id"], **tenant_filter(user)},
        {"_id": 0, "id": 1, "name": 1, "code": 1, "supervisor_user_id": 1, "supervisor_name": 1})
    v["branch"] = b or {}
    return v


@vouchers_router.get("/{vid}/audit")
async def voucher_audit(vid: str, user: dict = Depends(get_current_user)):
    await _get_voucher(vid, user)
    return await db.audit_logs.find(
        {**tenant_filter(user), "resource": f"payroll_vouchers/{vid}"},
        {"_id": 0}).sort("ts", 1).to_list(500)


@vouchers_router.patch("/{vid}")
async def edit_voucher(vid: str, body: VoucherPatch, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    if v["status"] not in ("draft", "returned"):
        raise HTTPException(409, f"Voucher is {v['status']} — immutable unless returned for correction")
    branch = await db.branches.find_one({"id": v["branch_id"], **tenant_filter(user)}, {"_id": 0})
    if not (_is_finance(user) or v["created_by"] == user["email"]
            or (branch or {}).get("supervisor_user_id") == user["id"]):
        raise HTTPException(403, "Not authorised to edit this voucher")
    items = await _resolve_items(body.line_items, user, v["period"], v["branch_id"], exclude_voucher_id=vid)
    hist = _hist(user, "edited", v["status"], v["status"])
    await db.payroll_vouchers.update_one(
        {"id": vid, **tenant_filter(user)},
        {"$set": {"line_items": items, "totals": _totals(items), "updated_at": iso(now_utc())},
         "$push": {"status_history": hist}})
    await audit("voucher_edit", f"payroll_vouchers/{vid}", user, {"lines": len(items)})
    return {"ok": True, "totals": _totals(items)}


@vouchers_router.delete("/{vid}")
async def delete_voucher(vid: str, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    if v["status"] != "draft":
        raise HTTPException(409, "Only draft vouchers can be deleted — submitted vouchers are permanent records")
    if not (_is_finance(user) or v["created_by"] == user["email"]):
        raise HTTPException(403, "Not authorised")
    await db.payroll_vouchers.delete_one({"id": vid, **tenant_filter(user)})
    await audit("voucher_delete", f"payroll_vouchers/{vid}", user, {"voucher_ref": v["voucher_ref"]})
    return {"ok": True}


async def _apply_transition(vid: str, user: dict, new_status: str, action: str,
                            note: str, extra: Optional[dict] = None) -> dict:
    v = await db.payroll_vouchers.find_one({"id": vid, **tenant_filter(user)}, {"_id": 0, "status": 1})
    hist = _hist(user, action, v["status"], new_status, note)
    sets = {"status": new_status, "updated_at": iso(now_utc()), **(extra or {})}
    await db.payroll_vouchers.update_one(
        {"id": vid, **tenant_filter(user)},
        {"$set": sets, "$push": {"status_history": hist}})
    await audit(f"voucher_{action}", f"payroll_vouchers/{vid}", user, {"to": new_status, "note": note})
    return {"ok": True, "status": new_status}


@vouchers_router.post("/{vid}/submit")
async def submit_voucher(vid: str, body: ActionIn, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    if v["status"] not in ("draft", "returned"):
        raise HTTPException(409, f"Cannot submit — voucher is {v['status']}")
    branch = await db.branches.find_one({"id": v["branch_id"], **tenant_filter(user)}, {"_id": 0})
    if not (_is_finance(user) or v["created_by"] == user["email"]
            or (branch or {}).get("supervisor_user_id") == user["id"]):
        raise HTTPException(403, "Not authorised to submit this voucher")
    sup_id = (branch or {}).get("supervisor_user_id")
    new_status = "pending_supervisor" if (sup_id and sup_id != user["id"]) else "submitted"
    extra = {"submitted_by": user["email"], "submitted_at": iso(now_utc())}
    if v["status"] == "returned":
        extra["revision"] = int(v.get("revision", 1)) + 1
    return await _apply_transition(vid, user, new_status, "submit", body.note, extra)


@vouchers_router.post("/{vid}/supervisor-approve")
async def supervisor_approve(vid: str, body: ActionIn, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    if v["status"] != "pending_supervisor":
        raise HTTPException(409, f"Voucher is {v['status']} — supervisor approval not applicable")
    branch = await db.branches.find_one({"id": v["branch_id"], **tenant_filter(user)}, {"_id": 0})
    if not ((branch or {}).get("supervisor_user_id") == user["id"] or is_admin(user)):
        raise HTTPException(403, "Only the branch supervisor can approve at this stage")
    return await _apply_transition(vid, user, "submitted", "supervisor_approve", body.note,
                                   {"supervisor_approved_by": user["email"],
                                    "supervisor_approved_at": iso(now_utc())})


@vouchers_router.post("/{vid}/start-review")
async def start_review(vid: str, body: ActionIn, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    if not _is_finance(user):
        raise HTTPException(403, "Finance officers or admins only")
    if v["status"] != "submitted":
        raise HTTPException(409, f"Voucher is {v['status']} — cannot start review")
    return await _apply_transition(vid, user, "under_review", "start_review", body.note,
                                   {"review_started_by": user["email"],
                                    "review_started_at": iso(now_utc())})


@vouchers_router.post("/{vid}/approve")
async def approve_voucher(vid: str, body: ActionIn, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    if not _is_finance(user):
        raise HTTPException(403, "Finance officers or admins only")
    if v["status"] != "under_review":
        raise HTTPException(409, f"Voucher is {v['status']} — must be under review to approve")
    if v["created_by"] == user["email"]:
        raise HTTPException(403, "Segregation of duties — you cannot approve a voucher you created")
    return await _apply_transition(vid, user, "approved", "approve", body.note,
                                   {"approved_by": user["email"], "approved_at": iso(now_utc())})


@vouchers_router.post("/{vid}/return")
async def return_voucher(vid: str, body: ReturnIn, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    if v["status"] not in RETURNABLE:
        raise HTTPException(409, f"Voucher is {v['status']} — cannot return")
    branch = await db.branches.find_one({"id": v["branch_id"], **tenant_filter(user)}, {"_id": 0})
    is_sup = (branch or {}).get("supervisor_user_id") == user["id"]
    if not (_is_finance(user) or (is_sup and v["status"] == "pending_supervisor")):
        raise HTTPException(403, "Not authorised to return this voucher")
    return await _apply_transition(vid, user, "returned", "return", body.reason,
                                   {"returned_by": user["email"], "returned_at": iso(now_utc()),
                                    "returned_reason": body.reason})


@vouchers_router.post("/{vid}/authorize")
async def authorize_payment(vid: str, body: ActionIn, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    if not (is_admin(user) or user.get("mof_approver")):
        raise HTTPException(403, "Only MoF approvers or admins can authorize payment")
    if v["status"] != "approved":
        raise HTTPException(409, f"Voucher is {v['status']} — must be approved before payment authorization")
    if v["created_by"] == user["email"]:
        raise HTTPException(403, "Dual control — the voucher creator cannot authorize its payment")
    if v.get("approved_by") == user["email"]:
        raise HTTPException(403, "Dual control — the finance approver cannot also authorize payment")
    return await _apply_transition(vid, user, "payment_authorized", "authorize", body.note,
                                   {"authorized_by": user["email"], "authorized_at": iso(now_utc())})
