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
import io
import uuid
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    if _is_finance(user) or user.get("mof_approver"):
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


@vouchers_router.get("/export-batch.pdf")
async def export_voucher_batch_pdf(period: str, user: dict = Depends(get_current_user)):
    if not _is_finance(user):
        raise HTTPException(403, "Finance officers or admins only")
    vs = await db.payroll_vouchers.find(
        {**tenant_filter(user), "period": period, "status": "payment_authorized"},
        {"_id": 0}).sort("branch_name", 1).to_list(500)
    if not vs:
        raise HTTPException(404, f"No payment-authorized vouchers for {period}")
    branches = {b["id"]: b for b in await db.branches.find(tenant_filter(user), {"_id": 0}).to_list(200)}
    pdf = _batch_pdf(vs, branches, period)
    await audit("voucher_batch_export", "payroll_vouchers", user, {"period": period, "count": len(vs)})
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="mof-voucher-pack-{period}.pdf"'})


class PackConfigIn(BaseModel):
    email: Optional[str] = Field(default="", max_length=200)


@vouchers_router.get("/pack-config")
async def get_pack_config(user: dict = Depends(require_admin)):
    c = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0, "mof_pack_email": 1})
    last = await db.mof_pack_emails.find_one(tenant_filter(user), {"_id": 0}, sort=[("sent_at", -1)])
    return {"email": (c or {}).get("mof_pack_email") or "", "last_sent": last}


@vouchers_router.put("/pack-config")
async def set_pack_config(body: PackConfigIn, user: dict = Depends(require_admin)):
    email = (body.email or "").strip().lower()
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        raise HTTPException(422, "Invalid email address")
    await db.companies.update_one({"id": user["company_id"]}, {"$set": {"mof_pack_email": email}})
    await audit("voucher_pack_config", f"companies/{user['company_id']}", user, {"email": email})
    return {"ok": True, "email": email}


@vouchers_router.get("/pack-history")
async def pack_history(user: dict = Depends(get_current_user)):
    if not _is_finance(user):
        raise HTTPException(403, "Finance officers or admins only")
    return await db.mof_pack_emails.find(tenant_filter(user), {"_id": 0}).sort("sent_at", -1).to_list(24)


@vouchers_router.post("/pack-config/send-now")
async def send_pack_now(period: str, user: dict = Depends(require_admin)):
    result = await _send_period_pack(user, period, force=True)
    if not result.get("attempted"):
        raise HTTPException(409, result.get("reason", "Pack not ready to send"))
    return result


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


FLAG_STRIPES = ["#1EB53A", "#FFFFFF", "#0072C6"]
ACTION_LABEL = {
    "created": "Prepared", "edited": "Corrected", "submit": "Submitted",
    "supervisor_approve": "Supervisor approved", "start_review": "Review started",
    "approve": "Finance approved", "return": "Returned for correction",
    "authorize": "Payment authorized",
}


def _flag_page(cnv, doc):
    from reportlab.lib import colors as rc
    from reportlab.lib.units import cm
    w, h = doc.pagesize
    cnv.saveState()
    for i, col in enumerate(FLAG_STRIPES):
        cnv.setFillColor(rc.HexColor(col))
        cnv.rect(0, h - (i + 1) * 4, w, 4, fill=1, stroke=0)
    cnv.setFont("Helvetica", 7.5)
    cnv.setFillColor(rc.HexColor("#686D76"))
    cnv.drawString(1.6 * cm, 1.0 * cm, "SaloneHCM — Centralized Payroll Voucher Repository")
    cnv.drawRightString(w - 1.6 * cm, 1.0 * cm, f"Page {cnv.getPageNumber()}")
    cnv.restoreState()


def _money(x) -> str:
    return f"{(x or 0):,.2f}"


def _sig_block(label: str, name: str, email: str, at: str) -> list:
    done = bool(email)
    return [label, (name or email or "—"), (at or "")[:10] if done else "pending",
            "_________________" if done else ""]


def _voucher_flowables(v: dict, branch: dict) -> list:
    from reportlab.lib.units import cm
    from reportlab.lib import colors as rc
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    green, blue, ink, grey, line = "#0A4A1E", "#0072C6", "#1A1C1E", "#525860", "#E2DFD6"
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=18, textColor=rc.HexColor(green))
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9.5, textColor=rc.HexColor(grey), leading=13)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, textColor=rc.HexColor(blue),
                        spaceBefore=14, spaceAfter=5)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=8, textColor=rc.HexColor(ink), leading=10.5)

    names = {h.get("by_email"): h.get("by_name") for h in v.get("status_history", []) if h.get("by_name")}
    status = v["status"].replace("_", " ").upper()

    story = [
        Paragraph(f"PAYROLL VOUCHER · <font color='{ink}'>{v['voucher_ref']}</font>", h1),
        Spacer(1, 4),
        Paragraph(
            f"{v['branch_name']} ({v['branch_code']})"
            + (f" · {branch.get('ministry')}" if branch.get("ministry") else "")
            + f" · Period <b>{v['period']}</b> · Status <b>{status}</b>"
            + f" · Revision {v.get('revision', 1)}"
            + (" · Generated from payroll run" if v.get("source") == "auto_run" else " · Manual submission"),
            sub),
    ]
    if v.get("note"):
        story.append(Paragraph(f"Note: {v['note']}", sub))

    story.append(Paragraph("Line items", h2))
    rows = [["Employee", "Gross", "PAYE", "NASSIT", "Loan", "Net"]]
    for li in v["line_items"]:
        rows.append([li["employee_name"], _money(li["gross"]), _money(li["paye"]),
                     _money(li["nassit_employee"]), _money(li["loan_deduction"]), _money(li["net"])])
    t = v["totals"]
    rows.append([f"TOTAL · {t['employee_count']} employees", _money(t["gross"]), _money(t["paye"]),
                 _money(t["nassit_employee"]), _money(t["loan_deductions"]), _money(t["net"])])
    lt = Table(rows, colWidths=[6.2 * cm] + [2.35 * cm] * 5, repeatRows=1)
    lt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rc.HexColor(green)),
        ("TEXTCOLOR", (0, 0), (-1, 0), rc.white),
        ("BACKGROUND", (0, -1), (-1, -1), rc.HexColor("#E4F7E7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, rc.HexColor(line)),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(lt)

    story.append(Paragraph("Signature approval chain", h2))
    srows = [["#", "Action", "Officer", "Role", "Date & time", "Note"]]
    for i, h in enumerate(v.get("status_history", []), start=1):
        srows.append([str(i), ACTION_LABEL.get(h["action"], h["action"].replace("_", " ").title()),
                      Paragraph(h.get("by_name") or h.get("by_email") or "", small),
                      (h.get("by_role") or "").replace("_", " "),
                      (h.get("at") or "").replace("T", " ")[:16],
                      Paragraph(h.get("note") or "", small)])
    st = Table(srows, colWidths=[0.8 * cm, 3.6 * cm, 3.6 * cm, 2.2 * cm, 2.8 * cm, 4.9 * cm], repeatRows=1)
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rc.HexColor(blue)),
        ("TEXTCOLOR", (0, 0), (-1, 0), rc.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, rc.HexColor(line)),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(st)

    story.append(Paragraph("Certification", h2))
    sig_rows = [["Stage", "Officer", "Date", "Signature"]]
    sig_rows.append(_sig_block("Prepared by", v.get("created_by_name"), v.get("created_by"), v.get("created_at")))
    if v.get("supervisor_approved_by") or branch.get("supervisor_name"):
        sig_rows.append(_sig_block("Branch supervisor", names.get(v.get("supervisor_approved_by")) or branch.get("supervisor_name"),
                                   v.get("supervisor_approved_by"), v.get("supervisor_approved_at")))
    sig_rows.append(_sig_block("Finance approval", names.get(v.get("approved_by")), v.get("approved_by"), v.get("approved_at")))
    sig_rows.append(_sig_block("Payment authorization (MoF)", names.get(v.get("authorized_by")), v.get("authorized_by"), v.get("authorized_at")))
    gt = Table(sig_rows, colWidths=[5.2 * cm, 5.2 * cm, 2.6 * cm, 4.9 * cm])
    gt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rc.HexColor("#F7F6F2")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.4, rc.HexColor(line)),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(gt)

    if v["status"] == "payment_authorized":
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            "This voucher is payment-authorized and constitutes a permanent, immutable record. "
            "Any alteration after authorization is invalid.", sub))

    return story


def _build_pdf(story: list, title: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.8 * cm, title=title)
    doc.build(story, onFirstPage=_flag_page, onLaterPages=_flag_page)
    return buf.getvalue()


def _voucher_pdf(v: dict, branch: dict) -> bytes:
    return _build_pdf(_voucher_flowables(v, branch), f"Payroll Voucher {v['voucher_ref']}")


def _batch_pdf(vouchers: list, branches: dict, period: str) -> bytes:
    from reportlab.lib.units import cm
    from reportlab.lib import colors as rc
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak

    green, grey, line = "#0A4A1E", "#525860", "#E2DFD6"
    h1 = ParagraphStyle("bh1", fontName="Helvetica-Bold", fontSize=20, textColor=rc.HexColor(green))
    sub = ParagraphStyle("bsub", fontName="Helvetica", fontSize=10, textColor=rc.HexColor(grey), leading=14)
    story = [
        Paragraph("MoF PAYMENT PACK", h1),
        Spacer(1, 4),
        Paragraph(f"Period <b>{period}</b> · {len(vouchers)} payment-authorized voucher(s) · "
                  f"Generated {iso(now_utc())[:16].replace('T', ' ')} UTC", sub),
        Spacer(1, 12),
    ]
    rows = [["Voucher", "Branch", "Employees", "Net (SLE)", "Authorized by"]]
    total_net = 0.0
    for v in vouchers:
        total_net += v["totals"]["net"]
        rows.append([v["voucher_ref"], f"{v['branch_name']} ({v['branch_code']})",
                     str(v["totals"]["employee_count"]), _money(v["totals"]["net"]),
                     v.get("authorized_by") or ""])
    rows.append(["TOTAL", "", str(sum(v["totals"]["employee_count"] for v in vouchers)),
                 _money(total_net), ""])
    t = Table(rows, colWidths=[3.6 * cm, 5.4 * cm, 2.2 * cm, 3.0 * cm, 3.7 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rc.HexColor(green)),
        ("TEXTCOLOR", (0, 0), (-1, 0), rc.white),
        ("BACKGROUND", (0, -1), (-1, -1), rc.HexColor("#E4F7E7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, rc.HexColor(line)),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    for v in vouchers:
        story.append(PageBreak())
        story.extend(_voucher_flowables(v, branches.get(v["branch_id"], {})))
    return _build_pdf(story, f"MoF Voucher Pack {period}")


@vouchers_router.get("/{vid}/export.pdf")
async def export_voucher_pdf(vid: str, user: dict = Depends(get_current_user)):
    v = await _get_voucher(vid, user)
    branch = await db.branches.find_one(
        {"id": v["branch_id"], **tenant_filter(user)},
        {"_id": 0, "supervisor_name": 1, "ministry": 1, "region": 1}) or {}
    pdf = _voucher_pdf(v, branch)
    await audit("voucher_export_pdf", f"payroll_vouchers/{vid}", user, {"voucher_ref": v["voucher_ref"]})
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{v["voucher_ref"]}.pdf"'})


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


async def _send_period_pack(user: dict, period: str, force: bool = False) -> dict:
    """Email the combined MoF pack when every branch's voucher for a period is
    payment-authorized. `force=True` (manual send-now) bypasses the once-only guard."""
    tf = tenant_filter(user)
    company = await db.companies.find_one(
        {"id": user["company_id"]}, {"_id": 0, "mof_pack_email": 1, "name": 1})
    to = (company or {}).get("mof_pack_email")
    if not to:
        return {"attempted": False, "reason": "No MoF pack email configured"}
    branches = await db.branches.find(tf, {"_id": 0}).to_list(200)
    vs = await db.payroll_vouchers.find({**tf, "period": period}, {"_id": 0}).sort("branch_name", 1).to_list(500)
    if not branches or not vs:
        return {"attempted": False, "reason": f"No vouchers for {period}"}
    pending = [x["voucher_ref"] for x in vs if x["status"] != "payment_authorized"]
    if pending:
        return {"attempted": False, "reason": f"Not all vouchers authorized yet ({len(pending)} pending)"}
    covered = {x["branch_id"] for x in vs}
    missing = [b["name"] for b in branches if b["id"] not in covered]
    if missing:
        return {"attempted": False,
                "reason": f"Period not closed — {len(missing)} branch(es) without a voucher: {', '.join(missing[:5])}"}
    if not force and await db.mof_pack_emails.find_one({**tf, "period": period, "status": "sent"}, {"_id": 1}):
        return {"attempted": False, "reason": "Pack already sent for this period"}
    from email_service import send_mof_pack
    pdf = _batch_pdf(vs, {b["id"]: b for b in branches}, period)
    total_net = round(sum(x["totals"]["net"] for x in vs), 2)
    res = await send_mof_pack(to, period, pdf, len(vs), total_net,
                              (company or {}).get("name") or "", company_id=user["company_id"])
    await db.mof_pack_emails.insert_one(with_tenant({
        "id": str(uuid.uuid4()), "period": period, "to": to,
        "status": "sent" if res.get("ok") else "failed",
        "error": res.get("error"), "voucher_count": len(vs),
        "sent_at": iso(now_utc()),
    }, user))
    await audit("voucher_pack_autoemail", "payroll_vouchers", user,
                {"period": period, "to": to, "ok": bool(res.get("ok"))})
    return {"attempted": True, "ok": bool(res.get("ok")), "to": to,
            "voucher_count": len(vs), "error": res.get("error")}


async def _maybe_send_period_pack(user: dict, period: str) -> Optional[dict]:
    try:
        return await _send_period_pack(user, period)
    except Exception as e:  # never block payment authorization on email problems
        import logging
        logging.getLogger("salonehcm.vouchers").warning("MoF pack auto-email failed for %s: %s", period, e)
        return None


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
    result = await _apply_transition(vid, user, "payment_authorized", "authorize", body.note,
                                     {"authorized_by": user["email"], "authorized_at": iso(now_utc())})
    pack = await _maybe_send_period_pack(user, v["period"])
    if pack and pack.get("attempted"):
        result["pack_email"] = pack
    return result
