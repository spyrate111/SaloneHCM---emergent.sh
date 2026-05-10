"""What-if payroll simulator + saved scenarios."""
import uuid
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_user, require_admin, audit, now_utc, iso
from payroll_engine import calc_payslip

router = APIRouter(prefix="/payroll", tags=["payroll-sim"])


class SimRule(BaseModel):
    name: Optional[str] = None
    target: Literal["all", "department", "employee"] = "all"
    department: Optional[str] = None
    employee_id: Optional[str] = None
    basic_pct_change: float = 0
    basic_flat_add: float = 0
    allowances_pct_change: float = 0
    allowances_flat_add: float = 0


class SimIn(BaseModel):
    rules: List[SimRule] = Field(..., min_length=1, max_length=20)


def _matches(rule: SimRule, emp: dict) -> bool:
    if rule.target == "all":
        return True
    if rule.target == "department":
        return rule.department and emp.get("department") == rule.department
    if rule.target == "employee":
        return rule.employee_id and emp.get("id") == rule.employee_id
    return False


def _apply(rules: List[SimRule], emp: dict) -> dict:
    basic = float(emp.get("basic_salary_sle", 0))
    allow = float(emp.get("allowances_sle", 0))
    for r in rules:
        if _matches(r, emp):
            basic = basic * (1 + r.basic_pct_change / 100) + r.basic_flat_add
            allow = allow * (1 + r.allowances_pct_change / 100) + r.allowances_flat_add
    return {**emp, "basic_salary_sle": max(0, round(basic, 2)),
            "allowances_sle": max(0, round(allow, 2))}


def _totals(slips: List[dict]) -> dict:
    return {
        "gross": round(sum(s["gross"] for s in slips), 2),
        "paye": round(sum(s["paye"] for s in slips), 2),
        "nassit_employee": round(sum(s["nassit_employee"] for s in slips), 2),
        "nassit_employer": round(sum(s["nassit_employer"] for s in slips), 2),
        "net": round(sum(s["net"] for s in slips), 2),
        "employer_total_cost": round(sum(s["gross"] + s["nassit_employer"] for s in slips), 2),
        "employee_count": len(slips),
    }


@router.post("/simulate")
async def simulate(body: SimIn, _: dict = Depends(require_admin)):
    return await _do_simulate(body)


async def _do_simulate(body: SimIn) -> dict:
    """Pure simulation — callable from both the API route and the AI executor."""
    emps = await db.employees.find({"status": "active"}, {"_id": 0}).to_list(2000)
    cur_slips = [calc_payslip(e) for e in emps]
    proj_slips = [calc_payslip(_apply(body.rules, e)) for e in emps]

    cur = _totals(cur_slips)
    proj = _totals(proj_slips)
    delta = {k: round(proj[k] - cur[k], 2) for k in cur if k != "employee_count"}

    affected_ids = {e["id"] for e in emps if any(_matches(r, e) for r in body.rules)}

    rows = []
    for e, cs, ps in zip(emps, cur_slips, proj_slips):
        if e["id"] not in affected_ids:
            continue
        rows.append({
            "id": e["id"],
            "name": f'{e["first_name"]} {e["last_name"]}',
            "department": e["department"],
            "job_title": e["job_title"],
            "current_gross": cs["gross"],
            "projected_gross": ps["gross"],
            "delta_gross": round(ps["gross"] - cs["gross"], 2),
            "current_net": cs["net"],
            "projected_net": ps["net"],
            "delta_net": round(ps["net"] - cs["net"], 2),
        })
    rows.sort(key=lambda r: -r["delta_gross"])

    # By-department comparison
    by_dept = {}
    for e, cs, ps in zip(emps, cur_slips, proj_slips):
        d = by_dept.setdefault(e["department"], {"name": e["department"], "current": 0, "projected": 0})
        d["current"] += cs["gross"]
        d["projected"] += ps["gross"]
    for d in by_dept.values():
        d["current"] = round(d["current"], 2)
        d["projected"] = round(d["projected"], 2)
        d["delta"] = round(d["projected"] - d["current"], 2)

    return {
        "current": cur,
        "projected": proj,
        "delta": delta,
        "annualized_delta_employer_cost": round(delta["employer_total_cost"] * 12, 2),
        "affected_employees_count": len(rows),
        "employees": rows,
        "by_department": sorted(by_dept.values(), key=lambda x: -x["delta"]),
    }


# ---------- Saved scenarios ----------
class ScenarioIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    description: Optional[str] = ""
    rules: List[SimRule] = Field(..., min_length=1, max_length=20)
    approver_email: Optional[str] = None


class ScenarioDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    notes: Optional[str] = ""


@router.post("/scenarios")
async def save_scenario(body: ScenarioIn, user: dict = Depends(require_admin)):
    sid = str(uuid.uuid4())
    doc = {
        "id": sid,
        "title": body.title,
        "description": body.description,
        "rules": [r.model_dump() for r in body.rules],
        "approver_email": (body.approver_email or "").strip().lower() or None,
        "approval_status": "pending" if body.approver_email else "draft",
        "approval_notes": "",
        "approved_by": None,
        "approved_at": None,
        "applied": False,
        "applied_at": None,
        "applied_run_id": None,
        "created_by": user["email"],
        "created_at": iso(now_utc()),
    }
    await db.payroll_scenarios.insert_one(doc)
    doc.pop("_id", None)
    await audit("scenario_save", f"payroll_scenarios/{sid}", user, {"title": body.title})
    return doc


@router.get("/scenarios")
async def list_scenarios(_: dict = Depends(require_admin)):
    return await db.payroll_scenarios.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/scenarios/{sid}")
async def get_scenario(sid: str, _: dict = Depends(require_admin)):
    s = await db.payroll_scenarios.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Not found")
    rules = [SimRule(**r) for r in s["rules"]]
    sim = await _do_simulate(SimIn(rules=rules))
    return {"scenario": s, "simulation": sim}


@router.patch("/scenarios/{sid}/decide")
async def decide_scenario(sid: str, body: ScenarioDecision, user: dict = Depends(require_admin)):
    s = await db.payroll_scenarios.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Not found")
    if s.get("approval_status") in ("approved", "rejected"):
        raise HTTPException(409, f"Already {s['approval_status']}")
    # Tighten: if a specific approver_email was set, only that user (or no-approver scenarios)
    approver_email = (s.get("approver_email") or "").lower()
    if approver_email and user["email"].lower() != approver_email:
        raise HTTPException(403, f"Only {approver_email} can decide this scenario")
    await db.payroll_scenarios.update_one(
        {"id": sid},
        {"$set": {
            "approval_status": body.decision,
            "approval_notes": body.notes or "",
            "approved_by": user["email"],
            "approved_at": iso(now_utc()),
        }},
    )
    await audit(f"scenario_{body.decision}", f"payroll_scenarios/{sid}", user,
                {"title": s["title"], "approver": user["email"]})
    return {"ok": True, "status": body.decision, "approved_by": user["email"]}


async def _do_apply_scenario(sid: str, user: dict) -> dict:
    """Apply scenario rules to employee records. Reusable from API + AI executor."""
    s = await db.payroll_scenarios.find_one({"id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Not found")
    if s.get("approval_status") != "approved":
        raise HTTPException(409, "Scenario must be approved before applying")
    if s.get("applied"):
        raise HTTPException(409, "Scenario already applied")

    rules = [SimRule(**r) for r in s["rules"]]
    emps = await db.employees.find({"status": "active"}, {"_id": 0}).to_list(2000)
    changed = []
    for e in emps:
        new_e = _apply(rules, e)
        if (new_e["basic_salary_sle"] != e["basic_salary_sle"]
                or new_e["allowances_sle"] != e["allowances_sle"]):
            await db.employees.update_one(
                {"id": e["id"]},
                {"$set": {
                    "basic_salary_sle": new_e["basic_salary_sle"],
                    "allowances_sle": new_e["allowances_sle"],
                }},
            )
            changed.append({
                "id": e["id"],
                "name": f'{e["first_name"]} {e["last_name"]}',
                "old_basic": e["basic_salary_sle"],
                "new_basic": new_e["basic_salary_sle"],
                "old_allowances": e["allowances_sle"],
                "new_allowances": new_e["allowances_sle"],
            })

    await db.payroll_scenarios.update_one(
        {"id": sid},
        {"$set": {"applied": True, "applied_at": iso(now_utc())}},
    )
    await audit("scenario_apply", f"payroll_scenarios/{sid}", user,
                {"title": s["title"], "employees_changed": len(changed)})
    return {"ok": True, "scenario_title": s["title"], "employees_changed": len(changed), "changes": changed}


@router.post("/scenarios/{sid}/apply")
async def apply_scenario(sid: str, user: dict = Depends(require_admin)):
    return await _do_apply_scenario(sid, user)


@router.delete("/scenarios/{sid}")
async def delete_scenario(sid: str, user: dict = Depends(require_admin)):
    res = await db.payroll_scenarios.delete_one({"id": sid})
    if not res.deleted_count:
        raise HTTPException(404, "Not found")
    await audit("scenario_delete", f"payroll_scenarios/{sid}", user)
    return {"ok": True}
