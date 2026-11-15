"""Tenant-scoped project budgets and payroll cost allocation for donor-funded teams."""
import math
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import audit, db, iso, now_utc, require_feature, require_roles, tenant_filter

router = APIRouter(
    prefix="/project-costing",
    tags=["project-costing"],
    dependencies=[Depends(require_feature("project_costing"))],
)

ACCESS = require_roles("hr", "payroll")


def _period(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except (TypeError, ValueError):
        raise HTTPException(422, "period must be YYYY-MM")
    if parsed.strftime("%Y-%m") != value:
        raise HTTPException(422, "period must be YYYY-MM")
    return value


def _money(value: float) -> float:
    if not math.isfinite(float(value)) or float(value) < 0:
        raise HTTPException(422, "amounts must be finite and non-negative")
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _within_period(project: dict, period: str) -> bool:
    return period >= project["start_period"] and (
        not project.get("end_period") or period <= project["end_period"]
    )


async def _locked(company_id: str, period: str) -> bool:
    return bool(await db.payroll_runs.find_one(
        {"company_id": company_id, "period": period, "status": "completed"},
        {"_id": 1},
    ))


async def _latest(collection, user: dict, period: str, status: Optional[str] = None):
    query = {**tenant_filter(user), "period": period}
    if status:
        query["status"] = status
    rows = await collection.find(query, {"_id": 0, "company_id": 0}).sort(
        [("revision", -1), ("created_at", -1)]
    ).limit(1).to_list(1)
    return rows[0] if rows else None


class ProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    funder: str = Field(default="", max_length=120)
    start_period: str
    end_period: Optional[str] = None


class ProjectPatch(BaseModel):
    code: Optional[str] = Field(default=None, min_length=1, max_length=32)
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    funder: Optional[str] = Field(default=None, max_length=120)
    status: Optional[str] = None


class BudgetRow(BaseModel):
    project_id: str
    budget_sle: float = Field(ge=0)


class BudgetSetIn(BaseModel):
    period: str
    rows: list[BudgetRow]


class AllocationRow(BaseModel):
    employee_id: str
    project_id: str
    percentage: float = Field(gt=0, le=100)


class AllocationSetIn(BaseModel):
    period: str
    allocations: list[AllocationRow]


@router.get("/projects")
async def list_projects(user: dict = Depends(ACCESS)):
    return await db.project_costing_projects.find(
        tenant_filter(user), {"_id": 0, "company_id": 0}
    ).sort([("status", 1), ("code", 1)]).to_list(None)


@router.post("/projects")
async def create_project(body: ProjectCreate, user: dict = Depends(ACCESS)):
    start = _period(body.start_period)
    end = _period(body.end_period) if body.end_period else None
    if end and end < start:
        raise HTTPException(422, "end_period must be on or after start_period")
    code = body.code.strip().upper()
    name = body.name.strip()
    if not code or not name:
        raise HTTPException(422, "project code and name are required")
    tf = tenant_filter(user)
    if await db.project_costing_projects.find_one({**tf, "code": code}):
        raise HTTPException(409, "A project with this code already exists")
    project = {
        "id": str(uuid.uuid4()),
        "company_id": user["company_id"],
        "code": code,
        "name": name,
        "funder": body.funder.strip(),
        "start_period": start,
        "end_period": end,
        "currency": "SLE",
        "status": "active",
        "created_by": user["id"],
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    await db.project_costing_projects.insert_one(dict(project))
    await audit("project_costing_project_create", f"project_costing_projects/{project['id']}", user,
                {"code": code, "name": name, "funder": project["funder"], "currency": "SLE"})
    return {key: value for key, value in project.items() if key != "company_id"}


@router.patch("/projects/{project_id}")
async def patch_project(project_id: str, body: ProjectPatch, user: dict = Depends(ACCESS)):
    project = await db.project_costing_projects.find_one(
        {"id": project_id, **tenant_filter(user)}, {"_id": 0, "company_id": 0}
    )
    if not project:
        raise HTTPException(404, "Project not found")
    updates = {key: value for key, value in body.dict(exclude_unset=True).items()
               if value is not None}
    if not updates:
        return project
    if "status" in updates and updates["status"] not in ("active", "closed"):
        raise HTTPException(422, "status must be active or closed")
    if "code" in updates:
        updates["code"] = updates["code"].strip().upper()
        if not updates["code"]:
            raise HTTPException(422, "project code is required")
        other = await db.project_costing_projects.find_one(
            {"company_id": user["company_id"], "code": updates["code"], "id": {"$ne": project_id}}
        )
        if other:
            raise HTTPException(409, "A project with this code already exists")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
        if not updates["name"]:
            raise HTTPException(422, "project name is required")
    if "funder" in updates and updates["funder"] is not None:
        updates["funder"] = updates["funder"].strip()
    updates["updated_at"] = iso(now_utc())
    await db.project_costing_projects.update_one(
        {"id": project_id, **tenant_filter(user)}, {"$set": updates}
    )
    await audit("project_costing_project_update", f"project_costing_projects/{project_id}", user,
                {key: value for key, value in updates.items() if key != "updated_at"})
    return await db.project_costing_projects.find_one(
        {"id": project_id, **tenant_filter(user)}, {"_id": 0, "company_id": 0}
    )


@router.get("/employees")
async def list_project_employees(user: dict = Depends(ACCESS)):
    employees = await db.employees.find(
        {"status": "active", **tenant_filter(user)},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1,
         "employee_number": 1, "department": 1},
    ).sort([("last_name", 1), ("first_name", 1)]).to_list(5000)
    return [
        {
            "id": row["id"],
            "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
            "employee_number": row.get("employee_number"),
            "department": row.get("department"),
        }
        for row in employees
    ]


@router.get("/budget-sets")
async def get_budget_set(period: str, user: dict = Depends(ACCESS)):
    period = _period(period)
    return await _latest(db.project_budget_sets, user, period)


@router.post("/budget-sets")
async def save_budget_set(body: BudgetSetIn, user: dict = Depends(ACCESS)):
    period = _period(body.period)
    if await _locked(user["company_id"], period):
        raise HTTPException(409, "This payroll period is complete; project budgets are locked")
    if not body.rows:
        raise HTTPException(422, "Add at least one project budget")
    if len({row.project_id for row in body.rows}) != len(body.rows):
        raise HTTPException(422, "Each project can appear only once in a budget set")

    ids = {row.project_id for row in body.rows}
    projects = await db.project_costing_projects.find(
        {"company_id": user["company_id"], "id": {"$in": list(ids)}, "status": "active"},
        {"_id": 0, "id": 1, "code": 1, "name": 1, "funder": 1,
         "start_period": 1, "end_period": 1},
    ).to_list(None)
    by_id = {row["id"]: row for row in projects}
    if ids != set(by_id):
        raise HTTPException(422, "Every budget row must reference an active project in this company")

    rows = []
    for row in body.rows:
        amount = _money(row.budget_sle)
        project = by_id[row.project_id]
        if not _within_period(project, period):
            raise HTTPException(422, f"Project {project['code']} is not active in {period}")
        rows.append({
            "project_id": row.project_id,
            "project_code": project["code"],
            "project_name": project["name"],
            "funder": project.get("funder", ""),
            "budget_sle": amount,
        })

    latest = await _latest(db.project_budget_sets, user, period)
    now = iso(now_utc())
    if latest and latest["status"] == "draft":
        if latest["created_by"] != user["id"]:
            raise HTTPException(409, "Only the draft author can replace this budget draft")
        result = await db.project_budget_sets.update_one(
            {"id": latest["id"], "company_id": user["company_id"], "status": "draft",
             "created_by": user["id"]},
            {"$set": {"rows": rows, "updated_at": now}},
        )
        if not result.matched_count:
            raise HTTPException(409, "Budget draft changed; reload and try again")
        saved = await db.project_budget_sets.find_one({"id": latest["id"], **tenant_filter(user)}, {"_id": 0, "company_id": 0})
    else:
        saved = {
            "id": str(uuid.uuid4()),
            "company_id": user["company_id"],
            "period": period,
            "revision": (latest or {}).get("revision", 0) + 1,
            "status": "draft",
            "rows": rows,
            "created_by": user["id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.project_budget_sets.insert_one(dict(saved))
    saved.pop("company_id", None)
    await audit("project_costing_budget_draft", f"project_budget_sets/{saved['id']}", user,
                {"period": period, "revision": saved["revision"], "project_count": len(rows)})
    return saved


@router.post("/budget-sets/{set_id}/approve")
async def approve_budget_set(set_id: str, user: dict = Depends(ACCESS)):
    item = await db.project_budget_sets.find_one(
        {"id": set_id, **tenant_filter(user)}, {"_id": 0, "company_id": 0}
    )
    if not item:
        raise HTTPException(404, "Budget set not found")
    if item["status"] != "draft":
        raise HTTPException(409, "Only a draft budget can be approved")
    if item["created_by"] == user["id"]:
        raise HTTPException(403, "A different user must approve this budget")
    if await _locked(user["company_id"], item["period"]):
        raise HTTPException(409, "This payroll period is complete; project budgets are locked")
    now = iso(now_utc())
    result = await db.project_budget_sets.update_one(
        {"id": set_id, "company_id": user["company_id"], "status": "draft",
         "created_by": {"$ne": user["id"]}},
        {"$set": {"status": "approved", "approved_by": user["id"],
                  "approved_at": now, "updated_at": now}},
    )
    if not result.matched_count:
        raise HTTPException(409, "Budget draft changed; reload and try again")
    await audit("project_costing_budget_approve", f"project_budget_sets/{set_id}", user,
                {"period": item["period"], "revision": item["revision"]})
    return await db.project_budget_sets.find_one({"id": set_id, **tenant_filter(user)}, {"_id": 0, "company_id": 0})


@router.get("/allocation-sets")
async def get_allocation_set(period: str, user: dict = Depends(ACCESS)):
    period = _period(period)
    return await _latest(db.project_allocation_sets, user, period)


@router.post("/allocation-sets")
async def save_allocation_set(body: AllocationSetIn, user: dict = Depends(ACCESS)):
    period = _period(body.period)
    if await _locked(user["company_id"], period):
        raise HTTPException(409, "This payroll period is complete; employee allocations are locked")
    seen = set()
    by_employee = {}
    percentage_by_pair = {}
    for row in body.allocations:
        key = (row.employee_id, row.project_id)
        if key in seen:
            raise HTTPException(422, "An employee can have only one row per project")
        seen.add(key)
        percentage = Decimal(str(row.percentage))
        if not percentage.is_finite():
            raise HTTPException(422, "Allocation percentages must be finite")
        percentage = percentage.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        if percentage <= 0 or percentage > 100:
            raise HTTPException(422, "Allocation percentages must be above 0 and at most 100")
        percentage_by_pair[key] = percentage
        by_employee[row.employee_id] = by_employee.get(row.employee_id, Decimal("0")) + percentage
    if any(total > Decimal("100") for total in by_employee.values()):
        raise HTTPException(422, "An employee's project allocations cannot exceed 100%")

    project_ids = {row.project_id for row in body.allocations}
    employee_ids = {row.employee_id for row in body.allocations}
    projects = await db.project_costing_projects.find(
        {"company_id": user["company_id"], "id": {"$in": list(project_ids)}, "status": "active"},
        {"_id": 0, "id": 1, "code": 1, "name": 1, "funder": 1,
         "start_period": 1, "end_period": 1},
    ).to_list(None) if project_ids else []
    employees = await db.employees.find(
        {"company_id": user["company_id"], "id": {"$in": list(employee_ids)}, "status": "active"},
        {"_id": 0, "id": 1, "first_name": 1, "last_name": 1},
    ).to_list(None) if employee_ids else []
    project_by_id = {row["id"]: row for row in projects}
    employee_by_id = {row["id"]: row for row in employees}
    if project_ids != set(project_by_id):
        raise HTTPException(422, "Every allocation must reference an active project in this company")
    if any(not _within_period(project_by_id[project_id], period) for project_id in project_ids):
        raise HTTPException(422, "Project allocations must fall within each project's active period")
    if employee_ids != set(employee_by_id):
        raise HTTPException(422, "Every allocation must reference an active employee in this company")

    allocations = []
    for row in body.allocations:
        project = project_by_id[row.project_id]
        employee = employee_by_id[row.employee_id]
        allocations.append({
            "employee_id": row.employee_id,
            "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
            "project_id": row.project_id,
            "project_code": project["code"],
            "project_name": project["name"],
            "funder": project.get("funder", ""),
            "percentage": float(percentage_by_pair[(row.employee_id, row.project_id)]),
        })

    latest = await _latest(db.project_allocation_sets, user, period)
    now = iso(now_utc())
    if latest and latest["status"] == "draft":
        if latest["created_by"] != user["id"]:
            raise HTTPException(409, "Only the draft author can replace this allocation draft")
        result = await db.project_allocation_sets.update_one(
            {"id": latest["id"], "company_id": user["company_id"], "status": "draft",
             "created_by": user["id"]},
            {"$set": {"allocations": allocations, "updated_at": now}},
        )
        if not result.matched_count:
            raise HTTPException(409, "Allocation draft changed; reload and try again")
        saved = await db.project_allocation_sets.find_one({"id": latest["id"], **tenant_filter(user)}, {"_id": 0, "company_id": 0})
    else:
        saved = {
            "id": str(uuid.uuid4()),
            "company_id": user["company_id"],
            "period": period,
            "revision": (latest or {}).get("revision", 0) + 1,
            "status": "draft",
            "allocations": allocations,
            "created_by": user["id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.project_allocation_sets.insert_one(dict(saved))
    saved.pop("company_id", None)
    await audit("project_costing_allocation_draft", f"project_allocation_sets/{saved['id']}", user,
                {"period": period, "revision": saved["revision"], "row_count": len(allocations)})
    return saved


@router.post("/allocation-sets/{set_id}/approve")
async def approve_allocation_set(set_id: str, user: dict = Depends(ACCESS)):
    item = await db.project_allocation_sets.find_one(
        {"id": set_id, **tenant_filter(user)}, {"_id": 0, "company_id": 0}
    )
    if not item:
        raise HTTPException(404, "Allocation set not found")
    if item["status"] != "draft":
        raise HTTPException(409, "Only a draft allocation set can be approved")
    if item["created_by"] == user["id"]:
        raise HTTPException(403, "A different user must approve these allocations")
    if await _locked(user["company_id"], item["period"]):
        raise HTTPException(409, "This payroll period is complete; employee allocations are locked")
    now = iso(now_utc())
    result = await db.project_allocation_sets.update_one(
        {"id": set_id, "company_id": user["company_id"], "status": "draft",
         "created_by": {"$ne": user["id"]}},
        {"$set": {"status": "approved", "approved_by": user["id"],
                  "approved_at": now, "updated_at": now}},
    )
    if not result.matched_count:
        raise HTTPException(409, "Allocation draft changed; reload and try again")
    await audit("project_costing_allocation_approve", f"project_allocation_sets/{set_id}", user,
                {"period": item["period"], "revision": item["revision"]})
    return await db.project_allocation_sets.find_one({"id": set_id, **tenant_filter(user)}, {"_id": 0, "company_id": 0})


def _split_cents(amount: float, percentages: list[float]) -> list[int]:
    cents = int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    weights = [Decimal(str(value)) for value in percentages]
    raw = [Decimal(cents) * weight / Decimal(100) for weight in weights]
    shares = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in raw]
    remainder = cents - sum(shares)
    order = sorted(range(len(raw)), key=lambda idx: (raw[idx] - shares[idx], -idx), reverse=True)
    for idx in order[:remainder]:
        shares[idx] += 1
    return shares


@router.get("/report")
async def project_cost_report(period: str, user: dict = Depends(ACCESS)):
    period = _period(period)
    runs = await db.payroll_runs.find(
        {**tenant_filter(user), "period": period, "status": "completed"},
        {"_id": 0, "id": 1, "created_at": 1, "slips": 1, "project_costing_snapshot": 1},
    ).sort("created_at", -1).limit(1).to_list(1)
    run = runs[0] if runs else None
    snapshot = run.get("project_costing_snapshot") if run else None
    if snapshot:
        budget = snapshot.get("budget_set")
        allocations = snapshot.get("allocation_set")
    else:
        # Backward-compatible for runs created before payroll snapshots existed.
        budget = await _latest(db.project_budget_sets, user, period, "approved")
        allocations = await _latest(db.project_allocation_sets, user, period, "approved")

    rows = {}
    for source in (budget or {}).get("rows", []):
        rows[source["project_id"]] = {
            "project_id": source["project_id"], "project_code": source["project_code"],
            "project_name": source["project_name"], "funder": source.get("funder", ""),
            "budget_sle": float(source["budget_sle"]),
        }
    allocation_rows = (allocations or {}).get("allocations", [])
    for source in allocation_rows:
        rows.setdefault(source["project_id"], {
            "project_id": source["project_id"], "project_code": source["project_code"],
            "project_name": source["project_name"], "funder": source.get("funder", ""),
            "budget_sle": None,
        })
    for row in rows.values():
        row.update({
            "employees": 0, "gross_sle": 0.0, "employer_nassit_sle": 0.0,
            "employer_cost_sle": 0.0, "variance_sle": None,
        })

    allocation_by_employee = {}
    for allocation in allocation_rows:
        allocation_by_employee.setdefault(allocation["employee_id"], []).append(allocation)

    unallocated_cost = 0.0
    unallocated_headcount = 0
    if run:
        for slip in run.get("slips", []):
            employee_rows = allocation_by_employee.get(slip.get("employee_id"), [])
            employee_rows = sorted(employee_rows, key=lambda row: row["project_id"])
            percentages = [float(row["percentage"]) for row in employee_rows]
            residual = max(0.0, 100.0 - sum(percentages))
            weights = percentages + [residual]
            gross_parts = _split_cents(float(slip.get("gross") or 0), weights)
            nassit_parts = _split_cents(float(slip.get("nassit_employer") or 0), weights)
            employee_was_unallocated = residual > 0
            if not employee_rows:
                employee_was_unallocated = True
            for index, source in enumerate(employee_rows):
                row = rows[source["project_id"]]
                row["employees"] += 1
                row["gross_sle"] += gross_parts[index] / 100
                row["employer_nassit_sle"] += nassit_parts[index] / 100
            unallocated_cost += (gross_parts[-1] + nassit_parts[-1]) / 100
            if employee_was_unallocated:
                unallocated_headcount += 1

    for row in rows.values():
        row["gross_sle"] = round(row["gross_sle"], 2)
        row["employer_nassit_sle"] = round(row["employer_nassit_sle"], 2)
        row["employer_cost_sle"] = round(row["gross_sle"] + row["employer_nassit_sle"], 2)
        if run and allocations is not None and row["budget_sle"] is not None:
            row["variance_sle"] = round(row["employer_cost_sle"] - row["budget_sle"], 2)
    ordered = sorted(rows.values(), key=lambda row: (row["project_code"], row["project_name"]))
    total_budget = round(sum(row["budget_sle"] or 0 for row in ordered), 2) if budget else None
    allocated_actual = round(sum(row["employer_cost_sle"] for row in ordered), 2) if run else None
    total_actual = round(allocated_actual + unallocated_cost, 2) if run else None
    allocated_variance = (
        round(allocated_actual - total_budget, 2)
        if allocated_actual is not None and total_budget is not None and allocations is not None else None
    )

    return {
        "period": period,
        "currency": "SLE",
        "payroll_run_id": run.get("id") if run else None,
        "payroll_run_created_at": run.get("created_at") if run else None,
        "actuals_available": run is not None,
        "budget_status": budget.get("status") if budget else None,
        "budget_revision": budget.get("revision") if budget else None,
        "allocation_status": allocations.get("status") if allocations else None,
        "allocation_revision": allocations.get("revision") if allocations else None,
        "totals": {
            "approved_budget_sle": total_budget,
            "allocated_employer_cost_sle": allocated_actual,
            "actual_employer_cost_sle": total_actual,
            "variance_sle": allocated_variance,
            "unallocated_employer_cost_sle": round(unallocated_cost, 2) if run else None,
            "unallocated_headcount": unallocated_headcount if run else None,
        },
        "by_project": ordered,
    }
