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
async def list_positions(user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    positions = await db.establishment_positions.find(tf, {"_id": 0}).to_list(5000)
    filled = await _filled_counts(user["company_id"])
    return [_annotate(p, filled.get(p["id"], 0)) for p in positions]


@router.post("/positions", status_code=201)
async def create_position(body: PositionIn, user: dict = Depends(require_admin)):
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
    return _annotate({k: v for k, v in doc.items() if k != "_id"}, 0)


@router.patch("/positions/{pid}")
async def patch_position(pid: str, body: PositionPatch, user: dict = Depends(require_admin)):
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
    return _annotate(fresh, filled)


@router.delete("/positions/{pid}")
async def delete_position(pid: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    pos = await db.establishment_positions.find_one({"id": pid, **tf}, {"_id": 0, "position_title": 1})
    if not pos:
        raise HTTPException(404, "Position not found")
    filled = (await _filled_counts(user["company_id"])).get(pid, 0)
    if filled:
        raise HTTPException(409, f"Cannot delete — {filled} employee(s) still assigned. Unassign first.")
    await db.establishment_positions.delete_one({"id": pid, **tf})
    await audit("establishment_position_delete", f"establishment_positions/{pid}", user,
                {"title": pos["position_title"]})
    return {"ok": True}


# ---------- Hierarchy & analytics ----------

@router.get("/tree")
async def tree(user: dict = Depends(require_admin)):
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
async def vacancies(user: dict = Depends(require_admin)):
    positions = await list_positions(user)
    return [p for p in positions if p["vacancy_count"] > 0 and p["status"] == "active"]


@router.get("/overruns")
async def overruns(user: dict = Depends(require_admin)):
    """Positions where filled headcount exceeds approved — payroll-fraud signal."""
    positions = await list_positions(user)
    return [p for p in positions if p["overrun_count"] > 0]


# ---------- Assignment ----------

@router.post("/positions/{pid}/assign")
async def assign_employee(pid: str, body: AssignIn, user: dict = Depends(require_admin)):
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
    return {"ok": True, "position_id": pid, "employee_id": body.employee_id}


@router.post("/positions/{pid}/unassign")
async def unassign_employee(pid: str, body: AssignIn, user: dict = Depends(require_admin)):
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
    return {"ok": True}
