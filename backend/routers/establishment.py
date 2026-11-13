"""Establishment Control — Ministry → Directorate → Unit → Position hierarchy.

Tracks the approved headcount per position vs. who's actually filling it.
Surfaces vacancies (filled < approved) and overruns (filled > approved — usually
a payroll-fraud red flag).

Tier-gated behind `establishment_control` (enterprise + gov).
"""
from __future__ import annotations
import uuid
from collections import defaultdict
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, tenant_filter, with_tenant, require_admin, require_feature, audit, now_utc, iso
from establishment_ats_sync import (
    sync_position_to_posting,
    close_position_posting,
    sync_all_positions_for_tenant,
)

from core import require_roles

router = APIRouter(
    prefix="/establishment",
    tags=["establishment"],
    dependencies=[Depends(require_feature("establishment_control"))],
)


# ---------- Pydantic models ----------

class PositionIn(BaseModel):
    ministry: str = Field(..., min_length=1, max_length=160)
    directorate: str = Field(..., min_length=1, max_length=160)
    unit: str = Field(..., min_length=1, max_length=160)
    position_title: str = Field(..., min_length=1, max_length=160)
    grade_code: Optional[str] = Field(None, max_length=32)
    step_number: Optional[int] = Field(None, ge=1, le=30)
    approved_count: int = Field(..., ge=0, le=10000)
    budget_code: Optional[str] = Field(None, max_length=64)
    status: Literal["active", "frozen"] = "active"


class PositionPatch(BaseModel):
    ministry: Optional[str] = None
    directorate: Optional[str] = None
    unit: Optional[str] = None
    position_title: Optional[str] = None
    grade_code: Optional[str] = None
    step_number: Optional[int] = Field(None, ge=1, le=30)
    approved_count: Optional[int] = Field(None, ge=0, le=10000)
    budget_code: Optional[str] = None
    status: Optional[Literal["active", "frozen"]] = None


class AssignIn(BaseModel):
    employee_id: str = Field(..., min_length=1)


# ---------- Helpers ----------

async def _filled_counts(company_id: str) -> dict[str, int]:
    """Return {position_id: filled_count} for one tenant."""
    counts: dict[str, int] = defaultdict(int)
    cursor = db.employees.find(
        {"company_id": company_id, "position_id": {"$exists": True, "$ne": None},
         "status": {"$ne": "terminated"}},
        {"_id": 0, "position_id": 1},
    )
    async for e in cursor:
        if e.get("position_id"):
            counts[e["position_id"]] += 1
    return counts


def _annotate(pos: dict, filled: int) -> dict:
    approved = pos.get("approved_count", 0)
    vacancy = max(0, approved - filled)
    overrun = max(0, filled - approved)
    return {
        **pos,
        "filled_count": filled,
        "vacancy_count": vacancy,
        "overrun_count": overrun,
        "utilisation": round(filled / approved, 3) if approved else (1.0 if filled else 0),
    }


# ---------- CRUD ----------

@router.get("/positions")
async def list_positions(user: dict = Depends(require_roles("hr"))):
    tf = tenant_filter(user)
    positions = await db.establishment_positions.find(tf, {"_id": 0}).to_list(5000)
    filled = await _filled_counts(user["company_id"])
    return [_annotate(p, filled.get(p["id"], 0)) for p in positions]


@router.post("/positions", status_code=201)
async def create_position(body: PositionIn, user: dict = Depends(require_roles("hr"))):
    pid = str(uuid.uuid4())
    doc = with_tenant({
        "id": pid,
        **body.model_dump(exclude_none=True),
        "created_at": iso(now_utc()),
        "created_by": user["email"],
    }, user)
    await db.establishment_positions.insert_one(doc)
    await audit("establishment_position_create", f"establishment_positions/{pid}", user,
                {"title": body.position_title, "approved": body.approved_count})
    clean = {k: v for k, v in doc.items() if k != "_id"}
    await sync_position_to_posting(clean, 0, user)
    return _annotate(clean, 0)


@router.patch("/positions/{pid}")
async def patch_position(pid: str, body: PositionPatch, user: dict = Depends(require_roles("hr"))):
    tf = tenant_filter(user)
    pos = await db.establishment_positions.find_one({"id": pid, **tf}, {"_id": 0})
    if not pos:
        raise HTTPException(404, "Position not found")
    updates = body.model_dump(exclude_none=True)
    # If lowering approved_count below current filled, raise 409 — must unassign first
    if "approved_count" in updates:
        filled = (await _filled_counts(user["company_id"])).get(pid, 0)
        if updates["approved_count"] < filled:
            raise HTTPException(409, f"Cannot reduce approved count below filled headcount ({filled}). Unassign employees first.")
    if updates:
        updates["updated_at"] = iso(now_utc())
        await db.establishment_positions.update_one({"id": pid, **tf}, {"$set": updates})
    await audit("establishment_position_patch", f"establishment_positions/{pid}", user, updates)
    fresh = await db.establishment_positions.find_one({"id": pid, **tf}, {"_id": 0})
    filled = (await _filled_counts(user["company_id"])).get(pid, 0)
    await sync_position_to_posting(fresh, filled, user)
    return _annotate(fresh, filled)


@router.delete("/positions/{pid}")
async def delete_position(pid: str, user: dict = Depends(require_roles("hr"))):
    tf = tenant_filter(user)
    pos = await db.establishment_positions.find_one({"id": pid, **tf}, {"_id": 0, "position_title": 1})
    if not pos:
        raise HTTPException(404, "Position not found")
    filled = (await _filled_counts(user["company_id"])).get(pid, 0)
    if filled:
        raise HTTPException(409, f"Cannot delete — {filled} employee(s) still assigned. Unassign first.")
    await db.establishment_positions.delete_one({"id": pid, **tf})
    await close_position_posting(pid, user)
    await audit("establishment_position_delete", f"establishment_positions/{pid}", user,
                {"title": pos["position_title"]})
    return {"ok": True}


# ---------- Hierarchy & analytics ----------

@router.get("/tree")
async def tree(user: dict = Depends(require_roles("hr"))):
    """Return Ministry → Directorate → Unit → Positions nested structure."""
    positions = await list_positions(user)
    out: dict = {}
    for p in positions:
        m = out.setdefault(p["ministry"], {"name": p["ministry"], "directorates": {}})
        d = m["directorates"].setdefault(p["directorate"], {"name": p["directorate"], "units": {}})
        u = d["units"].setdefault(p["unit"], {"name": p["unit"], "positions": []})
        u["positions"].append(p)
    # Flatten nested dicts to lists for the UI
    def _flatten(node, child_key):
        node[child_key] = sorted(node[child_key].values(), key=lambda x: x["name"])
        return node

    result = []
    for m in sorted(out.values(), key=lambda x: x["name"]):
        m = _flatten(m, "directorates")
        for d in m["directorates"]:
            d = _flatten(d, "units")
            for u in d["units"]:
                u["positions"].sort(key=lambda p: p["position_title"])
        result.append(m)
    # Roll up counts
    for m in result:
        m_approved = m_filled = 0
        for d in m["directorates"]:
            d_approved = d_filled = 0
            for u in d["units"]:
                u_a = sum(p["approved_count"] for p in u["positions"])
                u_f = sum(p["filled_count"] for p in u["positions"])
                u["approved_count"] = u_a
                u["filled_count"] = u_f
                u["vacancy_count"] = max(0, u_a - u_f)
                d_approved += u_a
                d_filled += u_f
            d["approved_count"] = d_approved
            d["filled_count"] = d_filled
            d["vacancy_count"] = max(0, d_approved - d_filled)
            m_approved += d_approved
            m_filled += d_filled
        m["approved_count"] = m_approved
        m["filled_count"] = m_filled
        m["vacancy_count"] = max(0, m_approved - m_filled)
    return {"ministries": result}


@router.get("/vacancies")
async def vacancies(user: dict = Depends(require_roles("hr"))):
    positions = await list_positions(user)
    return [p for p in positions if p["vacancy_count"] > 0 and p["status"] == "active"]


@router.get("/overruns")
async def overruns(user: dict = Depends(require_roles("hr"))):
    """Positions where filled headcount exceeds approved — payroll-fraud signal."""
    positions = await list_positions(user)
    return [p for p in positions if p["overrun_count"] > 0]


@router.get("/costs")
async def cost_tracking(period: str, user: dict = Depends(require_roles("hr"))):
    """Compare approved posts and IFMIS allocations with the latest completed payroll."""
    if (len(period) != 7 or period[4] != "-" or not period[:4].isdigit()
            or not period[5:].isdigit() or not 1 <= int(period[5:]) <= 12):
        raise HTTPException(422, "period must be YYYY-MM")

    tf = tenant_filter(user)
    company_id = user["company_id"]
    positions = await db.establishment_positions.find(
        tf,
        {"_id": 0, "id": 1, "ministry": 1, "directorate": 1,
         "approved_count": 1, "budget_code": 1},
    ).to_list(5000)
    filled_by_position = await _filled_counts(company_id)

    def _code(value):
        return str(value).strip().upper() if value is not None and str(value).strip() else None

    def _org_key(ministry, directorate):
        return (str(ministry or "").strip().casefold(),
                str(directorate or "").strip().casefold())

    orgs = {}
    code_orgs = defaultdict(set)
    by_code = defaultdict(lambda: {
        "approved_headcount": 0, "filled_headcount": 0,
        "position_count": 0, "organization_units": set(),
    })

    for pos in positions:
        ministry = str(pos.get("ministry") or "Unassigned ministry").strip()
        directorate = str(pos.get("directorate") or "Unassigned directorate").strip()
        org_key = _org_key(ministry, directorate)
        org = orgs.setdefault(org_key, {
            "ministry": ministry, "directorate": directorate,
            "approved_headcount": 0, "filled_headcount": 0,
            "payroll_headcount": 0, "actual_gross_sle": 0.0,
            "budget_codes": set(), "shared_budget_codes": set(),
            "missing_allocation_codes": set(),
        })
        approved = int(pos.get("approved_count") or 0)
        filled = int(filled_by_position.get(pos.get("id"), 0))
        org["approved_headcount"] += approved
        org["filled_headcount"] += filled

        code = _code(pos.get("budget_code"))
        row = by_code[code]
        row["approved_headcount"] += approved
        row["filled_headcount"] += filled
        row["position_count"] += 1
        row["organization_units"].add(org_key)
        org["budget_codes"].add(code)
        if code:
            code_orgs[code].add(org_key)

    # Use the newest saved balance per code if old duplicate rows exist.
    balance_rows = await db.budget_balances.find(
        {**tf, "period": period},
        {"_id": 0, "budget_code": 1, "allocated_sle": 1, "updated_at": 1},
    ).sort("updated_at", -1).to_list(2000)
    allocations = {}
    for balance in balance_rows:
        code = _code(balance.get("budget_code"))
        if code and code not in allocations:
            allocations[code] = round(float(balance.get("allocated_sle") or 0), 2)

    latest_runs = await db.payroll_runs.find(
        {**tf, "period": period, "status": "completed"},
        {"_id": 0, "id": 1, "created_at": 1, "slips": 1},
    ).sort("created_at", -1).limit(1).to_list(1)
    latest_run = latest_runs[0] if latest_runs else None
    actual_by_code = defaultdict(lambda: {"gross": 0.0, "headcount": 0})
    actual_by_org = defaultdict(lambda: {"gross": 0.0, "headcount": 0})

    if latest_run:
        for slip in latest_run.get("slips", []):
            gross = round(float(slip.get("gross") or 0), 2)
            code = _code(slip.get("budget_code"))
            actual_by_code[code]["gross"] += gross
            actual_by_code[code]["headcount"] += 1

            ministry = str(slip.get("mda_ministry") or "Unassigned ministry").strip()
            directorate = str(slip.get("department") or "Unspecified directorate").strip()
            org_key = _org_key(ministry, directorate)
            org = orgs.setdefault(org_key, {
                "ministry": ministry, "directorate": directorate,
                "approved_headcount": 0, "filled_headcount": 0,
                "payroll_headcount": 0, "actual_gross_sle": 0.0,
                "budget_codes": set(), "shared_budget_codes": set(),
                "missing_allocation_codes": set(),
            })
            actual_by_org[org_key]["gross"] += gross
            actual_by_org[org_key]["headcount"] += 1

    for code, org_keys in code_orgs.items():
        for org_key in org_keys:
            org = orgs[org_key]
            if code not in allocations:
                org["missing_allocation_codes"].add(code)
            elif len(org_keys) > 1:
                org["shared_budget_codes"].add(code)
            else:
                org.setdefault("allocated_sle", 0.0)
                org["allocated_sle"] += allocations[code]

    for org_key, org in orgs.items():
        org.update(actual_by_org.get(org_key, {"gross": 0.0, "headcount": 0}))
        org["actual_gross_sle"] = round(org["gross"], 2) if latest_run else None
        org["payroll_headcount"] = org["headcount"] if latest_run else None
        org.pop("gross", None)
        org.pop("headcount", None)
        if None in org["budget_codes"]:
            org["missing_allocation_codes"].add("No budget code")
        org["allocation_complete"] = bool(org["budget_codes"]) and not (
            org["shared_budget_codes"] or org["missing_allocation_codes"]
        )
        org["allocated_sle"] = round(org.get("allocated_sle", 0.0), 2)
        org["variance_sle"] = (
            round(org["actual_gross_sle"] - org["allocated_sle"], 2)
            if latest_run and org["allocation_complete"] else None
        )
        org["shared_budget_codes"] = sorted(org["shared_budget_codes"])
        org["missing_allocation_codes"] = sorted(org["missing_allocation_codes"])
        org["budget_codes"] = sorted(code for code in org["budget_codes"] if code)

    all_codes = set(by_code) | set(allocations) | set(actual_by_code)
    code_rows = []
    for code in all_codes:
        planned = by_code.get(code, {
            "approved_headcount": 0, "filled_headcount": 0,
            "position_count": 0, "organization_units": set(),
        })
        actual = actual_by_code.get(code, {"gross": 0.0, "headcount": 0})
        allocation = allocations.get(code)
        actual_gross = round(actual["gross"], 2) if latest_run else None
        code_rows.append({
            "budget_code": code,
            "approved_headcount": planned["approved_headcount"],
            "filled_headcount": planned["filled_headcount"],
            "position_count": planned["position_count"],
            "payroll_headcount": actual["headcount"] if latest_run else None,
            "actual_gross_sle": actual_gross,
            "allocated_sle": allocation,
            "utilization_pct": (
                round(actual_gross / allocation * 100, 1)
                if actual_gross is not None and allocation else None
            ),
            "variance_sle": (
                round(actual_gross - allocation, 2)
                if actual_gross is not None and allocation is not None else None
            ),
            "shared_across_org_units": len(code_orgs.get(code, set())) > 1,
            "organization_units": [
                {"ministry": orgs[key]["ministry"], "directorate": orgs[key]["directorate"]}
                for key in sorted(planned["organization_units"])
            ],
        })

    code_rows.sort(key=lambda row: (row["budget_code"] is None, row["budget_code"] or ""))
    org_rows = [
        {key: value for key, value in org.items()
         if key not in ("budget_codes",)}
        for org in orgs.values()
    ]
    org_rows.sort(key=lambda row: (row["ministry"].casefold(), row["directorate"].casefold()))

    total_actual = round(sum(row["gross"] for row in actual_by_code.values()), 2) if latest_run else None
    return {
        "period": period,
        "currency": "SLE",
        "payroll_run_id": latest_run.get("id") if latest_run else None,
        "payroll_run_created_at": latest_run.get("created_at") if latest_run else None,
        "actuals_available": latest_run is not None,
        "totals": {
            "approved_headcount": sum(int(pos.get("approved_count") or 0) for pos in positions),
            "filled_headcount": sum(int(filled_by_position.get(pos.get("id"), 0)) for pos in positions),
            "payroll_headcount": sum(row["headcount"] for row in actual_by_code.values()) if latest_run else None,
            "actual_gross_sle": total_actual,
            "allocated_sle": round(sum(allocations.values()), 2),
        },
        "by_org_unit": org_rows,
        "by_budget_code": code_rows,
    }


# ---------- Assignment ----------

@router.post("/positions/{pid}/assign")
async def assign_employee(pid: str, body: AssignIn, user: dict = Depends(require_roles("hr"))):
    tf = tenant_filter(user)
    pos = await db.establishment_positions.find_one({"id": pid, **tf}, {"_id": 0})
    if not pos:
        raise HTTPException(404, "Position not found")
    if pos.get("status") == "frozen":
        raise HTTPException(409, "Position is frozen — unfreeze before assigning")
    emp = await db.employees.find_one(
        {"id": body.employee_id, **tf},
        {"_id": 0, "first_name": 1, "last_name": 1,
         "mda_ministry": 1, "department": 1, "budget_code": 1, "grade_code": 1},
    )
    if not emp:
        raise HTTPException(404, "Employee not found")
    filled = (await _filled_counts(user["company_id"])).get(pid, 0)
    if filled >= pos["approved_count"]:
        raise HTTPException(409, f"Position is at capacity ({pos['approved_count']}). Increase approved count first.")

    # Snapshot the employee's pre-assignment fields so unassign can restore them.
    # Only set the snapshot if it doesn't already exist (preserves the *original*
    # pre-first-assignment state across multiple assign/unassign cycles).
    snapshot_fields = ("mda_ministry", "department", "budget_code", "grade_code")
    set_doc = {
        "position_id": pid,
        "mda_ministry": pos["ministry"],
        "department": pos["directorate"],
        "budget_code": pos.get("budget_code"),
        "grade_code": pos.get("grade_code") or None,
        "updated_at": iso(now_utc()),
    }
    setOnInsert = {f"_pre_position_{k}": emp.get(k) for k in snapshot_fields}
    # Use a manual conditional update — only seed the snapshot when none exists yet.
    if not any(k.startswith("_pre_position_") for k in (emp or {})):
        existing_snapshot = await db.employees.find_one(
            {"id": body.employee_id, "_pre_position_mda_ministry": {"$exists": True}},
        )
        if not existing_snapshot:
            await db.employees.update_one(
                {"id": body.employee_id, **tf},
                {"$set": {**set_doc, **setOnInsert}},
            )
        else:
            await db.employees.update_one({"id": body.employee_id, **tf}, {"$set": set_doc})
    else:
        await db.employees.update_one({"id": body.employee_id, **tf}, {"$set": set_doc})

    await audit("establishment_assign", f"establishment_positions/{pid}", user,
                {"employee_id": body.employee_id,
                 "name": f"{emp.get('first_name','')} {emp.get('last_name','')}".strip()})
    new_filled = (await _filled_counts(user["company_id"])).get(pid, 0)
    await sync_position_to_posting(pos, new_filled, user)
    return {"ok": True, "position_id": pid, "employee_id": body.employee_id}


@router.post("/positions/{pid}/unassign")
async def unassign_employee(pid: str, body: AssignIn, user: dict = Depends(require_roles("hr"))):
    tf = tenant_filter(user)
    emp = await db.employees.find_one(
        {"id": body.employee_id, "position_id": pid, **tf},
        {"_id": 0,
         "_pre_position_mda_ministry": 1, "_pre_position_department": 1,
         "_pre_position_budget_code": 1, "_pre_position_grade_code": 1},
    )
    if not emp:
        raise HTTPException(404, "Employee not assigned to this position")

    # Restore the pre-assignment snapshot if present, else just clear position_id.
    unset_doc = {"position_id": ""}
    set_doc = {"updated_at": iso(now_utc())}
    for field in ("mda_ministry", "department", "budget_code", "grade_code"):
        key = f"_pre_position_{field}"
        if key in emp:
            val = emp[key]
            if val is None:
                unset_doc[field] = ""
            else:
                set_doc[field] = val
            unset_doc[key] = ""

    await db.employees.update_one(
        {"id": body.employee_id, **tf},
        {"$set": set_doc, "$unset": unset_doc},
    )
    await audit("establishment_unassign", f"establishment_positions/{pid}", user,
                {"employee_id": body.employee_id})
    fresh_pos = await db.establishment_positions.find_one({"id": pid, **tf}, {"_id": 0})
    if fresh_pos:
        new_filled = (await _filled_counts(user["company_id"])).get(pid, 0)
        await sync_position_to_posting(fresh_pos, new_filled, user)
    return {"ok": True}



# ---------- Talent ATS sync (batch backfill) ----------

@router.post("/sync-vacancies")
async def sync_vacancies_to_ats(user: dict = Depends(require_roles("hr"))):
    """Idempotent batch: reconcile every establishment_position → job_posting for this tenant.
    Useful after bulk imports or as a super-admin audit tool. Returns counts of
    postings created / updated / closed."""
    result = await sync_all_positions_for_tenant(user["company_id"], actor_email=user["email"])
    await audit("establishment_sync_vacancies", "establishment/sync-vacancies", user, result)
    return result
