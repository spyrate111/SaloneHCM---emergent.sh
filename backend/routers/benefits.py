"""Benefits administration: plans + enrollments."""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional

from core import db, get_current_user, require_admin, audit, now_utc, iso, tenant_filter, with_tenant, require_feature

router = APIRouter(prefix="/benefits", tags=["benefits"], dependencies=[Depends(require_feature("benefits"))])


class BenefitPlanIn(BaseModel):
    name: str
    type: Literal["health", "dental", "pension", "life", "transport", "housing"]
    monthly_cost_sle: float = Field(..., ge=0)
    employer_share_pct: float = Field(50, ge=0, le=100)
    description: Optional[str] = ""


class EnrollmentIn(BaseModel):
    plan_id: str
    employee_id: Optional[str] = None  # admin can set; employee implies self


@router.get("/plans")
async def list_plans(user: dict = Depends(get_current_user)):
    return await db.benefit_plans.find(tenant_filter(user), {"_id": 0}).sort("name", 1).to_list(200)


@router.post("/plans")
async def create_plan(body: BenefitPlanIn, user: dict = Depends(require_admin)):
    pid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": pid, "created_at": iso(now_utc())}, user)
    await db.benefit_plans.insert_one(doc)
    doc.pop("_id", None)
    await audit("create", f"benefit_plans/{pid}", user, {"name": body.name})
    return doc


@router.delete("/plans/{pid}")
async def delete_plan(pid: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    await db.benefit_plans.delete_one({"id": pid, **tf})
    await db.benefit_enrollments.delete_many({"plan_id": pid, **tf})
    await audit("delete", f"benefit_plans/{pid}", user)
    return {"ok": True}


@router.get("/enrollments")
async def list_enrollments(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    q = {**tf} if user["role"] == "admin" else {"employee_id": user.get("employee_id"), **tf}
    rows = await db.benefit_enrollments.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    plans = {p["id"]: p for p in await db.benefit_plans.find(tf, {"_id": 0}).to_list(200)}
    employees = {e["id"]: e for e in await db.employees.find(tf, {"_id": 0}).to_list(2000)}
    for r in rows:
        p = plans.get(r["plan_id"], {})
        e = employees.get(r["employee_id"], {})
        r["plan_name"] = p.get("name", "—")
        r["plan_type"] = p.get("type", "—")
        r["monthly_cost_sle"] = p.get("monthly_cost_sle", 0)
        r["employee_name"] = f'{e.get("first_name","")} {e.get("last_name","")}'.strip() or "—"
    return rows


@router.post("/enrollments")
async def enroll(body: EnrollmentIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] == "admin" else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    tf = tenant_filter(user)
    plan = await db.benefit_plans.find_one({"id": body.plan_id, **tf}, {"_id": 0})
    if not plan:
        raise HTTPException(404, "Plan not found")
    existing = await db.benefit_enrollments.find_one({"employee_id": eid, "plan_id": body.plan_id, **tf})
    if existing:
        raise HTTPException(409, "Already enrolled")
    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "plan_id": body.plan_id,
        "status": "active",
        "created_at": iso(now_utc()),
    }, user)
    await db.benefit_enrollments.insert_one(doc)
    doc.pop("_id", None)
    await audit("benefit_enroll", f"benefit_enrollments/{doc['id']}", user, {"plan": plan["name"]})
    return doc


@router.delete("/enrollments/{enr_id}")
async def unenroll(enr_id: str, user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    enr = await db.benefit_enrollments.find_one({"id": enr_id, **tf}, {"_id": 0})
    if not enr:
        raise HTTPException(404, "Not found")
    if user["role"] not in ("admin", "superadmin") and enr["employee_id"] != user.get("employee_id"):
        raise HTTPException(403, "Forbidden")
    await db.benefit_enrollments.delete_one({"id": enr_id, **tf})
    await audit("benefit_unenroll", f"benefit_enrollments/{enr_id}", user)
    return {"ok": True}
