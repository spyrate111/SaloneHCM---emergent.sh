"""Sierra Leone Civil Service module — grades, steps, allowance schedules, MDA budget codes,
acting allowances, Ministry-of-Finance approval workflow, ghost-worker controls.

Gov tier-only. Feature flag: `civil_service`.
"""
import uuid
from datetime import datetime
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core import (
    db, get_current_user, require_admin, require_feature, audit,
    now_utc, iso, tenant_filter, with_tenant,
)

router = APIRouter(prefix="/civil-service", tags=["civil-service"])


# ============ Grade & Step structure ============

class GradeIn(BaseModel):
    code: str = Field(..., pattern=r"^[A-Z0-9-]{1,12}$")
    name: str = Field(..., min_length=2, max_length=120)
    cadre: Optional[str] = Field(default="General", max_length=60)
    notes: Optional[str] = Field(default="", max_length=500)


class StepIn(BaseModel):
    step_number: int = Field(..., ge=1, le=20)
    monthly_amount_sle: float = Field(..., ge=0)


@router.get("/grades")
async def list_grades(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    grades = await db.civil_service_grades.find(tf, {"_id": 0}).sort("code", 1).to_list(200)
    # Attach steps
    for g in grades:
        g["steps"] = await db.civil_service_steps.find(
            {"grade_code": g["code"], **tf}, {"_id": 0}
        ).sort("step_number", 1).to_list(50)
    return grades


@router.post("/grades")
async def create_grade(body: GradeIn, user: dict = Depends(require_admin)):
    existing = await db.civil_service_grades.find_one(
        {"code": body.code, **tenant_filter(user)}, {"_id": 0, "code": 1}
    )
    if existing:
        raise HTTPException(409, f"Grade {body.code} already exists")
    doc = with_tenant({**body.model_dump(), "id": str(uuid.uuid4()), "created_at": iso(now_utc())}, user)
    await db.civil_service_grades.insert_one(doc)
    doc.pop("_id", None)
    await audit("grade_create", f"civil_service_grades/{body.code}", user, {"code": body.code})
    return doc


@router.delete("/grades/{code}")
async def delete_grade(code: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    # Block delete if any employees still assigned
    using = await db.employees.count_documents({"grade_code": code, **tf})
    if using:
        raise HTTPException(409, f"Cannot delete — {using} employees still on grade {code}")
    await db.civil_service_grades.delete_one({"code": code, **tf})
    await db.civil_service_steps.delete_many({"grade_code": code, **tf})
    await audit("grade_delete", f"civil_service_grades/{code}", user)
    return {"ok": True}


@router.put("/grades/{code}/steps")
async def set_grade_steps(code: str, steps: list[StepIn], user: dict = Depends(require_admin)):
    """Replace the entire step schedule for a grade (atomic)."""
    tf = tenant_filter(user)
    grade = await db.civil_service_grades.find_one({"code": code, **tf}, {"_id": 0})
    if not grade:
        raise HTTPException(404, f"Grade {code} not found")
    await db.civil_service_steps.delete_many({"grade_code": code, **tf})
    docs = [
        with_tenant({
            "id": str(uuid.uuid4()),
            "grade_code": code,
            "step_number": s.step_number,
            "monthly_amount_sle": s.monthly_amount_sle,
            "updated_at": iso(now_utc()),
        }, user)
        for s in steps
    ]
    if docs:
        await db.civil_service_steps.insert_many(docs)
    await audit("grade_steps_set", f"civil_service_grades/{code}/steps", user, {"count": len(docs)})
    return {"ok": True, "count": len(docs)}


# ============ Allowance Schedule ============

ALLOWANCE_KINDS = Literal["housing", "transport", "responsibility", "hardship", "acting"]


class AllowanceRuleIn(BaseModel):
    kind: ALLOWANCE_KINDS
    label: str = Field(..., min_length=2, max_length=80)
    # Either flat or percentage-of-basic — never both
    flat_sle: Optional[float] = Field(default=None, ge=0)
    pct_of_basic: Optional[float] = Field(default=None, ge=0, le=2.0)
    # Optional grade restriction (e.g. responsibility only for GR1-GR4)
    applies_to_grades: list[str] = Field(default_factory=list)
    enabled: bool = True


@router.get("/allowance-rules")
async def list_allowance_rules(user: dict = Depends(get_current_user)):
    return await db.civil_service_allowance_rules.find(
        tenant_filter(user), {"_id": 0}
    ).sort("kind", 1).to_list(50)


@router.post("/allowance-rules")
async def create_allowance_rule(body: AllowanceRuleIn, user: dict = Depends(require_admin)):
    if (body.flat_sle is None) == (body.pct_of_basic is None):
        raise HTTPException(400, "Provide exactly one of `flat_sle` or `pct_of_basic`")
    doc = with_tenant({
        **body.model_dump(),
        "id": str(uuid.uuid4()),
        "created_at": iso(now_utc()),
    }, user)
    await db.civil_service_allowance_rules.insert_one(doc)
    doc.pop("_id", None)
    await audit("allowance_rule_create", f"civil_service_allowance_rules/{doc['id']}", user, {"kind": body.kind})
    return doc


@router.delete("/allowance-rules/{rid}")
async def delete_allowance_rule(rid: str, user: dict = Depends(require_admin)):
    await db.civil_service_allowance_rules.delete_one({"id": rid, **tenant_filter(user)})
    await audit("allowance_rule_delete", f"civil_service_allowance_rules/{rid}", user)
    return {"ok": True}


# ============ MDA Budget Codes ============

class BudgetCodeIn(BaseModel):
    code: str = Field(..., pattern=r"^[A-Z0-9.\-]{2,40}$")
    name: str = Field(..., min_length=2, max_length=160)
    ministry: Optional[str] = Field(default="")
    program: Optional[str] = Field(default="")
    fiscal_year: Optional[int] = Field(default=None, ge=2024, le=2100)


@router.get("/budget-codes")
async def list_budget_codes(user: dict = Depends(get_current_user)):
    return await db.civil_service_budget_codes.find(
        tenant_filter(user), {"_id": 0}
    ).sort("code", 1).to_list(500)


@router.post("/budget-codes")
async def create_budget_code(body: BudgetCodeIn, user: dict = Depends(require_admin)):
    if await db.civil_service_budget_codes.find_one({"code": body.code, **tenant_filter(user)}, {"_id": 0, "code": 1}):
        raise HTTPException(409, f"Budget code {body.code} already exists")
    doc = with_tenant({**body.model_dump(), "id": str(uuid.uuid4()), "created_at": iso(now_utc())}, user)
    await db.civil_service_budget_codes.insert_one(doc)
    doc.pop("_id", None)
    await audit("budget_code_create", f"civil_service_budget_codes/{body.code}", user, {"code": body.code})
    return doc


@router.delete("/budget-codes/{code}")
async def delete_budget_code(code: str, user: dict = Depends(require_admin)):
    using = await db.employees.count_documents({"budget_code": code, **tenant_filter(user)})
    if using:
        raise HTTPException(409, f"Cannot delete — {using} employees mapped to {code}")
    await db.civil_service_budget_codes.delete_one({"code": code, **tenant_filter(user)})
    await audit("budget_code_delete", f"civil_service_budget_codes/{code}", user)
    return {"ok": True}


# ============ Employee Civil-Service profile ============

class EmployeeCivilServicePatch(BaseModel):
    grade_code: Optional[str] = None
    step_number: Optional[int] = Field(default=None, ge=1, le=20)
    budget_code: Optional[str] = None
    mda_ministry: Optional[str] = None
    housing_allowance_enabled: Optional[bool] = None
    transport_allowance_enabled: Optional[bool] = None
    responsibility_allowance_enabled: Optional[bool] = None
    hardship_allowance_enabled: Optional[bool] = None


@router.patch("/employees/{eid}/profile")
async def patch_employee_cs(eid: str, body: EmployeeCivilServicePatch, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if not payload:
        return {"ok": True, "updated": 0}

    # If grade_code provided, validate it exists
    if "grade_code" in payload:
        g = await db.civil_service_grades.find_one({"code": payload["grade_code"], **tf}, {"_id": 0, "code": 1})
        if not g:
            raise HTTPException(404, f"Grade {payload['grade_code']} not found")
    if "step_number" in payload and "grade_code" in payload:
        s = await db.civil_service_steps.find_one(
            {"grade_code": payload["grade_code"], "step_number": payload["step_number"], **tf},
            {"_id": 0, "monthly_amount_sle": 1},
        )
        if not s:
            raise HTTPException(404, f"Step {payload['step_number']} not configured for grade {payload['grade_code']}")
        # Auto-sync basic salary to step amount
        payload["basic_salary_sle"] = float(s["monthly_amount_sle"])
    if "budget_code" in payload:
        bc = await db.civil_service_budget_codes.find_one({"code": payload["budget_code"], **tf}, {"_id": 0, "code": 1})
        if not bc:
            raise HTTPException(404, f"Budget code {payload['budget_code']} not found")

    r = await db.employees.update_one({"id": eid, **tf}, {"$set": payload})
    if not r.matched_count:
        raise HTTPException(404, "Employee not found")
    await audit("employee_cs_update", f"employees/{eid}", user, payload)
    return {"ok": True, "updated": payload}


# ============ Acting Allowances ============

class ActingIn(BaseModel):
    employee_id: str
    acting_role_title: str = Field(..., min_length=2, max_length=160)
    monthly_allowance_sle: float = Field(..., ge=0)
    start_date: str  # YYYY-MM-DD
    end_date: Optional[str] = None  # open-ended if null


@router.get("/actings")
async def list_actings(active_only: bool = False, user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    q = {**tf}
    if active_only:
        today = iso(now_utc())[:10]
        q["start_date"] = {"$lte": today}
        q["$or"] = [{"end_date": None}, {"end_date": {"$gte": today}}]
    rows = await db.civil_service_actings.find(q, {"_id": 0}).sort("start_date", -1).to_list(500)
    # Attach employee name
    emp_ids = [r["employee_id"] for r in rows]
    emps = {e["id"]: e for e in await db.employees.find({"id": {"$in": emp_ids}, **tf}, {"_id": 0}).to_list(500)}
    for r in rows:
        e = emps.get(r["employee_id"], {})
        r["employee_name"] = f'{e.get("first_name","")} {e.get("last_name","")}'.strip()
    return rows


@router.post("/actings")
async def create_acting(body: ActingIn, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    emp = await db.employees.find_one({"id": body.employee_id, **tf}, {"_id": 0, "id": 1})
    if not emp:
        raise HTTPException(404, "Employee not found")
    doc = with_tenant({**body.model_dump(), "id": str(uuid.uuid4()), "created_at": iso(now_utc())}, user)
    await db.civil_service_actings.insert_one(doc)
    doc.pop("_id", None)
    await audit("acting_create", f"civil_service_actings/{doc['id']}", user, {"employee_id": body.employee_id})
    return doc


@router.delete("/actings/{aid}")
async def delete_acting(aid: str, user: dict = Depends(require_admin)):
    await db.civil_service_actings.delete_one({"id": aid, **tenant_filter(user)})
    await audit("acting_delete", f"civil_service_actings/{aid}", user)
    return {"ok": True}


# ============ Helpers used by payroll engine ============

async def get_active_allowance_amounts(emp: dict, company_id: str, period: str) -> dict:
    """Returns {label: amount} for all enabled allowances applicable to this employee for the period."""
    rules = await db.civil_service_allowance_rules.find(
        {"company_id": company_id, "enabled": True}, {"_id": 0}
    ).to_list(50)
    out: dict[str, float] = {}
    basic = float(emp.get("basic_salary_sle", 0))
    for r in rules:
        # Per-kind employee toggle gate
        toggle_field = f"{r['kind']}_allowance_enabled"
        # housing & transport default on for all civil servants; responsibility/hardship default off
        default_on = r["kind"] in ("housing", "transport")
        if not emp.get(toggle_field, default_on):
            continue
        if r.get("applies_to_grades") and emp.get("grade_code") not in r["applies_to_grades"]:
            continue
        amount = float(r["flat_sle"]) if r.get("flat_sle") is not None else round(basic * float(r["pct_of_basic"]), 2)
        out[r["label"]] = round(out.get(r["label"], 0) + amount, 2)

    # Acting allowance — sum any active actings for this employee in this period
    pyear, pmonth = period.split("-")
    period_start = f"{period}-01"
    # Naive end-of-month
    from calendar import monthrange
    period_end = f"{period}-{monthrange(int(pyear), int(pmonth))[1]:02d}"
    active_actings = await db.civil_service_actings.find({
        "company_id": company_id,
        "employee_id": emp["id"],
        "start_date": {"$lte": period_end},
        "$or": [{"end_date": None}, {"end_date": {"$gte": period_start}}],
    }, {"_id": 0}).to_list(20)
    for a in active_actings:
        label = f"Acting: {a['acting_role_title']}"
        out[label] = round(out.get(label, 0) + float(a["monthly_allowance_sle"]), 2)
    return out


# ============ Reports ============

@router.get("/reports/by-budget-code/{run_id}")
async def spend_by_budget_code(run_id: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    run = await db.payroll_runs.find_one({"id": run_id, **tf}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    emps = {e["id"]: e for e in await db.employees.find(tf, {"_id": 0}).to_list(5000)}
    by_code: dict = {}
    for s in run.get("slips", []):
        emp = emps.get(s["employee_id"], {})
        code = emp.get("budget_code", "UNCODED")
        ministry = emp.get("mda_ministry", "—")
        bucket = by_code.setdefault(code, {
            "budget_code": code, "ministry": ministry, "employee_count": 0,
            "gross": 0.0, "paye": 0.0, "nassit_employer": 0.0, "net": 0.0,
        })
        bucket["employee_count"] += 1
        bucket["gross"] += s["gross"]
        bucket["paye"] += s["paye"]
        bucket["nassit_employer"] += s["nassit_employer"]
        bucket["net"] += s["net"]
    rows = sorted(by_code.values(), key=lambda r: -r["gross"])
    for r in rows:
        for k in ("gross", "paye", "nassit_employer", "net"):
            r[k] = round(r[k], 2)
    return {"period": run["period"], "rows": rows, "total_rows": len(rows)}


# ============ Ghost-worker detection / Payslip acknowledgement ============

class AcknowledgeIn(BaseModel):
    note: Optional[str] = None


@router.post("/payslip-ack/{run_id}")
async def acknowledge_my_payslip(run_id: str, body: AcknowledgeIn, user: dict = Depends(get_current_user)):
    """Employees confirm they received and reviewed their payslip — used for ghost-worker detection."""
    eid = user.get("employee_id")
    if not eid:
        raise HTTPException(400, "User has no linked employee_id")
    tf = tenant_filter(user)
    run = await db.payroll_runs.find_one({"id": run_id, **tf}, {"_id": 0, "period": 1, "slips": 1})
    if not run:
        raise HTTPException(404, "Payroll run not found")
    has_slip = any(s["employee_id"] == eid for s in run.get("slips", []))
    if not has_slip:
        raise HTTPException(404, "No payslip for you in this run")
    # Upsert acknowledgement
    await db.payslip_acks.update_one(
        {"run_id": run_id, "employee_id": eid, **tf},
        {"$set": with_tenant({
            "run_id": run_id, "employee_id": eid,
            "period": run["period"],
            "acknowledged_at": iso(now_utc()),
            "ack_note": (body.note or "")[:300],
        }, user)},
        upsert=True,
    )
    await audit("payslip_acknowledge", f"payroll_runs/{run_id}", user, {"period": run["period"]})
    return {"ok": True, "acknowledged_at": iso(now_utc())}


@router.get("/ghost-workers/{run_id}")
async def ghost_workers_report(run_id: str, user: dict = Depends(require_admin)):
    """List employees whose payslip was issued but never acknowledged → potential ghost workers."""
    tf = tenant_filter(user)
    run = await db.payroll_runs.find_one({"id": run_id, **tf}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    acked = set([a["employee_id"] for a in await db.payslip_acks.find(
        {"run_id": run_id, **tf}, {"_id": 0, "employee_id": 1}
    ).to_list(5000)])
    emps = {e["id"]: e for e in await db.employees.find(tf, {"_id": 0}).to_list(5000)}
    suspects = []
    for s in run.get("slips", []):
        if s["employee_id"] not in acked:
            e = emps.get(s["employee_id"], {})
            suspects.append({
                "employee_id": s["employee_id"],
                "employee_name": s["employee_name"],
                "department": e.get("department", ""),
                "ministry": e.get("mda_ministry", ""),
                "budget_code": e.get("budget_code", ""),
                "grade_code": e.get("grade_code", ""),
                "net_unacknowledged_sle": s["net"],
                "hire_date": e.get("hire_date"),
            })
    return {
        "period": run["period"],
        "total_slips": len(run.get("slips", [])),
        "acknowledged": len(acked),
        "ghost_suspects": len(suspects),
        "ghost_rate": round(len(suspects) / max(1, len(run.get("slips", []))), 3),
        "suspects": sorted(suspects, key=lambda r: -r["net_unacknowledged_sle"]),
    }


# ============ Ministry-of-Finance approval workflow ============

class MoFActionIn(BaseModel):
    note: Optional[str] = Field(default="", max_length=500)


@router.post("/runs/{run_id}/submit-for-approval")
async def submit_for_mof_approval(run_id: str, body: MoFActionIn, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    run = await db.payroll_runs.find_one({"id": run_id, **tf}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("mof_status") in ("approved", "released"):
        raise HTTPException(409, f"Run already {run['mof_status']}")
    await db.payroll_runs.update_one(
        {"id": run_id, **tf},
        {"$set": {
            "mof_status": "submitted",
            "mof_submitted_by": user["email"],
            "mof_submitted_at": iso(now_utc()),
            "mof_submitted_note": body.note,
        }},
    )
    await audit("mof_submit", f"payroll_runs/{run_id}", user, {"period": run["period"]})
    return {"ok": True, "mof_status": "submitted"}


@router.post("/runs/{run_id}/mof-approve")
async def mof_approve_run(run_id: str, body: MoFActionIn, user: dict = Depends(require_admin)):
    """Only users tagged with role-flag `mof_approver` (or superadmin) can approve."""
    if user["role"] != "superadmin" and not user.get("mof_approver"):
        raise HTTPException(403, "Only MoF approvers can approve runs")
    tf = tenant_filter(user)
    run = await db.payroll_runs.find_one({"id": run_id, **tf}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("mof_status") != "submitted":
        raise HTTPException(409, f"Run must be 'submitted' first, current: {run.get('mof_status','draft')}")
    await db.payroll_runs.update_one(
        {"id": run_id, **tf},
        {"$set": {
            "mof_status": "approved",
            "mof_approved_by": user["email"],
            "mof_approved_at": iso(now_utc()),
            "mof_approved_note": body.note,
        }},
    )
    await audit("mof_approve", f"payroll_runs/{run_id}", user, {"period": run["period"]})
    return {"ok": True, "mof_status": "approved"}


@router.post("/runs/{run_id}/mof-reject")
async def mof_reject_run(run_id: str, body: MoFActionIn, user: dict = Depends(require_admin)):
    if user["role"] != "superadmin" and not user.get("mof_approver"):
        raise HTTPException(403, "Only MoF approvers can reject runs")
    tf = tenant_filter(user)
    run = await db.payroll_runs.find_one({"id": run_id, **tf}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    if run.get("mof_status") != "submitted":
        raise HTTPException(409, "Run is not in submitted state")
    await db.payroll_runs.update_one(
        {"id": run_id, **tf},
        {"$set": {
            "mof_status": "rejected",
            "mof_rejected_by": user["email"],
            "mof_rejected_at": iso(now_utc()),
            "mof_rejected_note": body.note,
        }},
    )
    await audit("mof_reject", f"payroll_runs/{run_id}", user, {"period": run["period"], "note": body.note})
    return {"ok": True, "mof_status": "rejected"}
