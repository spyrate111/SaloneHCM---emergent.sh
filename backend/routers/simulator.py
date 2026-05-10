"""What-if payroll simulator — apply scenario rules and compare current vs projected."""
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core import db, require_admin
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
