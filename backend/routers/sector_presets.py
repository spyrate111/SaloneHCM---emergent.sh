"""Sector Allowance Presets — one-click industry templates.

The Civil Service module covers SL Government allowance schedules. For private-sector
SMEs and enterprises, this module ships **named allowance bundles** modeled on common
Sierra Leone industries:

  * `ngo` — Non-Governmental Organizations (per diem, field, hardship)
  * `mining` — Mining operations (housing, hazard, remote-site, family)
  * `banking` — Financial services (cash-handling, transport, performance)
  * `telecom` — Telecommunications (on-call, tower-climb, fuel)
  * `general` — Everyone else (housing, transport, communication, lunch)

Each preset can be APPLIED to a single employee or to a department in bulk.
Allowances are stored on the employee record itself (in a `sector_allowances` array)
so the payroll engine picks them up automatically alongside legacy + civil-service
allowance breakdowns.

Tier-gated behind `sector_presets` (professional + enterprise + gov).
"""
from __future__ import annotations
import uuid
from typing import Literal, Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import (
    db, get_current_user, require_admin, require_feature,
    tenant_filter, with_tenant, audit, now_utc, iso,
)

router = APIRouter(
    prefix="/sector-presets",
    tags=["sector-presets"],
    dependencies=[Depends(require_feature("sector_presets"))],
)

# ---------- Built-in catalog ----------
# Each allowance has: label, amount_sle (monthly), taxable (bool — affects PAYE calc).
# All amounts here are SLE per month. Tenants can override after applying.
SECTOR_CATALOG: dict[str, dict] = {
    "ngo": {
        "id": "ngo",
        "label": "Non-Governmental Organization",
        "description": "Per-diem-heavy structure for field workers and partner-funded NGOs.",
        "allowances": [
            {"label": "Field allowance", "amount_sle": 1500.0, "taxable": False},
            {"label": "Per-diem (domestic travel)", "amount_sle": 1200.0, "taxable": False},
            {"label": "Hardship allowance", "amount_sle": 800.0, "taxable": True},
            {"label": "Communication", "amount_sle": 300.0, "taxable": True},
        ],
    },
    "mining": {
        "id": "mining",
        "label": "Mining & Extractives",
        "description": "Mining sector — hazard, remote-site, family-support allowances.",
        "allowances": [
            {"label": "Housing allowance", "amount_sle": 2500.0, "taxable": True},
            {"label": "Hazard allowance", "amount_sle": 1800.0, "taxable": True},
            {"label": "Remote-site allowance", "amount_sle": 1200.0, "taxable": False},
            {"label": "Family separation", "amount_sle": 1000.0, "taxable": False},
            {"label": "Transport (4×4)", "amount_sle": 700.0, "taxable": True},
        ],
    },
    "banking": {
        "id": "banking",
        "label": "Banking & Financial Services",
        "description": "Cash-handling, market-rate performance, transport.",
        "allowances": [
            {"label": "Cash-handling allowance", "amount_sle": 800.0, "taxable": True},
            {"label": "Transport allowance", "amount_sle": 600.0, "taxable": True},
            {"label": "Communication", "amount_sle": 350.0, "taxable": True},
            {"label": "Performance allowance", "amount_sle": 1500.0, "taxable": True},
            {"label": "Lunch allowance", "amount_sle": 450.0, "taxable": False},
        ],
    },
    "telecom": {
        "id": "telecom",
        "label": "Telecommunications",
        "description": "On-call, tower-climb, fuel for field engineers.",
        "allowances": [
            {"label": "On-call allowance", "amount_sle": 700.0, "taxable": True},
            {"label": "Tower-climb hazard", "amount_sle": 1200.0, "taxable": False},
            {"label": "Fuel & transport", "amount_sle": 1000.0, "taxable": True},
            {"label": "Communication", "amount_sle": 400.0, "taxable": True},
            {"label": "Housing allowance", "amount_sle": 1500.0, "taxable": True},
        ],
    },
    "general": {
        "id": "general",
        "label": "General Private Sector",
        "description": "Baseline package for offices and small businesses.",
        "allowances": [
            {"label": "Housing allowance", "amount_sle": 1200.0, "taxable": True},
            {"label": "Transport allowance", "amount_sle": 500.0, "taxable": True},
            {"label": "Communication", "amount_sle": 250.0, "taxable": True},
            {"label": "Lunch allowance", "amount_sle": 300.0, "taxable": False},
        ],
    },
}


# ---------- Models ----------

class ApplyOneIn(BaseModel):
    preset_id: Literal["ngo", "mining", "banking", "telecom", "general"]
    override_amounts: Optional[dict] = Field(default=None, description="Optional {label: amount} dict to tweak before applying")


class ApplyBulkIn(BaseModel):
    preset_id: Literal["ngo", "mining", "banking", "telecom", "general"]
    department: Optional[str] = Field(None, max_length=120, description="If set, applies only to employees in this department")
    employee_ids: Optional[List[str]] = Field(None, description="If set, applies only to these IDs")
    override_amounts: Optional[dict] = None


class CustomAllowance(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    amount_sle: float = Field(..., ge=0, le=1_000_000)
    taxable: bool = True


# ---------- Helpers ----------

def _build_allowances(preset_id: str, overrides: dict | None) -> list[dict]:
    base = SECTOR_CATALOG[preset_id]["allowances"]
    overrides = overrides or {}
    out = []
    for a in base:
        amt = overrides.get(a["label"], a["amount_sle"])
        out.append({
            "label": a["label"],
            "amount_sle": round(float(amt), 2),
            "taxable": a["taxable"],
            "preset_id": preset_id,
        })
    return out


async def _apply_to_employee(eid: str, company_id: str, preset_id: str, overrides: dict | None) -> None:
    allowances = _build_allowances(preset_id, overrides)
    await db.employees.update_one(
        {"id": eid, "company_id": company_id},
        {"$set": {
            "sector_allowances": allowances,
            "sector_preset_id": preset_id,
            "sector_applied_at": iso(now_utc()),
        }},
    )


# ---------- Public endpoints ----------

@router.get("/catalog")
async def list_catalog(_: dict = Depends(get_current_user)):
    """Read-only list of available presets + their default amounts."""
    return {
        "presets": [
            {
                **p,
                "total_monthly_sle": round(sum(a["amount_sle"] for a in p["allowances"]), 2),
            }
            for p in SECTOR_CATALOG.values()
        ],
    }


@router.post("/apply/{eid}")
async def apply_one(eid: str, body: ApplyOneIn, user: dict = Depends(require_admin)):
    """Apply a preset to a single employee."""
    tf = tenant_filter(user)
    emp = await db.employees.find_one({"id": eid, **tf}, {"_id": 0, "first_name": 1, "last_name": 1})
    if not emp:
        raise HTTPException(404, "Employee not found")
    await _apply_to_employee(eid, user["company_id"], body.preset_id, body.override_amounts)
    await audit("sector_preset_apply", f"employees/{eid}", user, {
        "preset": body.preset_id,
        "employee": f"{emp.get('first_name','')} {emp.get('last_name','')}".strip(),
    })
    return {"ok": True, "employee_id": eid, "preset_id": body.preset_id}


@router.post("/apply-bulk")
async def apply_bulk(body: ApplyBulkIn, user: dict = Depends(require_admin)):
    """Apply a preset to a department or a list of employees."""
    tf = tenant_filter(user)
    q: dict = {**tf, "status": {"$ne": "terminated"}}
    if body.employee_ids:
        q["id"] = {"$in": body.employee_ids}
    elif body.department:
        q["department"] = body.department
    else:
        raise HTTPException(400, "Provide either department or employee_ids")
    employees = await db.employees.find(q, {"_id": 0, "id": 1}).to_list(5000)
    if not employees:
        raise HTTPException(404, "No matching employees found")
    for e in employees:
        await _apply_to_employee(e["id"], user["company_id"], body.preset_id, body.override_amounts)
    await audit("sector_preset_apply_bulk", "employees", user, {
        "preset": body.preset_id,
        "count": len(employees),
        "scope": body.department or f"{len(body.employee_ids or [])} ids",
    })
    return {"ok": True, "applied_to": len(employees), "preset_id": body.preset_id}


@router.delete("/clear/{eid}")
async def clear_employee(eid: str, user: dict = Depends(require_admin)):
    """Remove all sector allowances from an employee."""
    tf = tenant_filter(user)
    res = await db.employees.update_one(
        {"id": eid, **tf},
        {"$unset": {"sector_allowances": "", "sector_preset_id": "", "sector_applied_at": ""}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Employee not found")
    await audit("sector_preset_clear", f"employees/{eid}", user, {})
    return {"ok": True}


@router.get("/employee/{eid}")
async def get_employee_allowances(eid: str, user: dict = Depends(get_current_user)):
    """Inspect what sector preset is on an employee."""
    tf = tenant_filter(user)
    emp = await db.employees.find_one({"id": eid, **tf}, {
        "_id": 0, "sector_allowances": 1, "sector_preset_id": 1, "sector_applied_at": 1,
        "first_name": 1, "last_name": 1,
    })
    if not emp:
        raise HTTPException(404, "Employee not found")
    if user.get("role") not in ("admin", "superadmin") and eid != user.get("employee_id"):
        raise HTTPException(403, "Not allowed")
    return {
        "employee_id": eid,
        "preset_id": emp.get("sector_preset_id"),
        "applied_at": emp.get("sector_applied_at"),
        "allowances": emp.get("sector_allowances") or [],
        "total_monthly_sle": round(sum(a.get("amount_sle", 0) for a in (emp.get("sector_allowances") or [])), 2),
    }
