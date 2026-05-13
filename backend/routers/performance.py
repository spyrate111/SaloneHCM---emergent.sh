"""Performance reviews — cycles with structured self-assessment + manager scoring + sign-off."""
import uuid
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core import db, get_current_user, require_admin, audit, now_utc, iso, tenant_filter, with_tenant


router = APIRouter(prefix="/performance", tags=["performance"])

ReviewStatus = Literal["pending_self", "pending_manager", "completed", "cancelled"]


class CycleCreateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    period: str = Field(..., min_length=2, max_length=40)  # e.g. "2026-H1"
    description: Optional[str] = ""
    employee_ids: list[str] = Field(default_factory=list)
    self_review_due: Optional[str] = None
    manager_review_due: Optional[str] = None


class SelfAssessmentIn(BaseModel):
    achievements: str = Field("", max_length=4000)
    challenges: str = Field("", max_length=4000)
    goals_next: str = Field("", max_length=4000)
    self_rating: int = Field(..., ge=1, le=5)


class ManagerScoreIn(BaseModel):
    manager_comments: str = Field("", max_length=4000)
    manager_rating: int = Field(..., ge=1, le=5)
    promotion_recommendation: Literal["none", "consider", "strong"] = "none"
    salary_action: Literal["none", "merit", "promotion"] = "none"


class AcknowledgeIn(BaseModel):
    employee_comments: Optional[str] = Field("", max_length=2000)


# ---------- Cycles (admin / manager driven) ----------

@router.post("/cycles")
async def create_cycle(body: CycleCreateIn, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    cid = str(uuid.uuid4())
    employees = await db.employees.find(
        {"id": {"$in": body.employee_ids}, **tf},
        {"_id": 0},
    ).to_list(500) if body.employee_ids else await db.employees.find(
        {"status": "active", **tf}, {"_id": 0}
    ).to_list(2000)

    cycle_doc = with_tenant({
        "id": cid,
        "name": body.name,
        "period": body.period,
        "description": body.description,
        "self_review_due": body.self_review_due,
        "manager_review_due": body.manager_review_due,
        "employee_count": len(employees),
        "created_by": user["email"],
        "created_at": iso(now_utc()),
        "status": "active",
    }, user)
    await db.review_cycles.insert_one(cycle_doc)

    # Create one PerformanceReview doc per employee, attached to this cycle
    reviews = []
    for e in employees:
        rid = str(uuid.uuid4())
        reviews.append(with_tenant({
            "id": rid,
            "cycle_id": cid,
            "cycle_name": body.name,
            "period": body.period,
            "employee_id": e["id"],
            "employee_name": f'{e.get("first_name","")} {e.get("last_name","")}'.strip(),
            "department": e.get("department", ""),
            "manager_id": e.get("manager_id"),
            "status": "pending_self",
            "self_assessment": None,
            "self_rating": None,
            "manager_score": None,
            "manager_rating": None,
            "promotion_recommendation": None,
            "salary_action": None,
            "acknowledged_at": None,
            "employee_comments": None,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        }, user))
    if reviews:
        await db.performance_reviews_v2.insert_many(reviews)

    await audit("perf_cycle_create", f"review_cycles/{cid}", user, {
        "name": body.name, "period": body.period, "employees": len(employees),
    })
    cycle_doc.pop("_id", None)
    return cycle_doc


@router.get("/cycles")
async def list_cycles(user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    cycles = await db.review_cycles.find(tf, {"_id": 0}).sort("created_at", -1).to_list(200)
    # Attach progress counts
    for c in cycles:
        agg = await db.performance_reviews_v2.aggregate([
            {"$match": {"cycle_id": c["id"], **tf}},
            {"$group": {"_id": "$status", "n": {"$sum": 1}}},
        ]).to_list(10)
        c["progress"] = {row["_id"]: row["n"] for row in agg}
    return cycles


@router.get("/cycles/{cid}/reviews")
async def cycle_reviews(cid: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    return await db.performance_reviews_v2.find(
        {"cycle_id": cid, **tf}, {"_id": 0}
    ).sort("employee_name", 1).to_list(2000)


# ---------- Per-employee actions ----------

@router.get("/my-reviews")
async def my_reviews(user: dict = Depends(get_current_user)):
    eid = user.get("employee_id")
    if not eid:
        return []
    return await db.performance_reviews_v2.find(
        {"employee_id": eid, **tenant_filter(user)}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)


@router.get("/reviews/as-manager")
async def reviews_for_my_reports(user: dict = Depends(get_current_user)):
    eid = user.get("employee_id")
    if not eid:
        return []
    return await db.performance_reviews_v2.find(
        {"manager_id": eid, **tenant_filter(user)}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)


async def _get_review(rid: str, user: dict) -> dict:
    r = await db.performance_reviews_v2.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Review not found")
    return r


@router.post("/reviews/{rid}/self-assessment")
async def submit_self_assessment(rid: str, body: SelfAssessmentIn, user: dict = Depends(get_current_user)):
    r = await _get_review(rid, user)
    if user.get("employee_id") != r["employee_id"] and user["role"] not in ("admin", "superadmin"):
        raise HTTPException(403, "Only the employee can submit their self-assessment")
    if r["status"] not in ("pending_self",):
        raise HTTPException(409, f"Self-assessment cannot be submitted in status '{r['status']}'")
    await db.performance_reviews_v2.update_one(
        {"id": rid, **tenant_filter(user)},
        {"$set": {
            "self_assessment": body.model_dump(exclude={"self_rating"}),
            "self_rating": body.self_rating,
            "status": "pending_manager",
            "self_submitted_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        }},
    )
    await audit("perf_self_submit", f"performance_reviews_v2/{rid}", user, {"self_rating": body.self_rating})
    return {"ok": True, "status": "pending_manager"}


@router.post("/reviews/{rid}/manager-score")
async def submit_manager_score(rid: str, body: ManagerScoreIn, user: dict = Depends(get_current_user)):
    r = await _get_review(rid, user)
    is_manager = user.get("employee_id") == r.get("manager_id")
    if not is_manager and user["role"] not in ("admin", "superadmin"):
        raise HTTPException(403, "Only the assigned manager can score this review")
    if r["status"] not in ("pending_manager",):
        raise HTTPException(409, f"Manager score cannot be submitted in status '{r['status']}'")
    await db.performance_reviews_v2.update_one(
        {"id": rid, **tenant_filter(user)},
        {"$set": {
            "manager_score": {
                "comments": body.manager_comments,
                "rating": body.manager_rating,
            },
            "manager_rating": body.manager_rating,
            "promotion_recommendation": body.promotion_recommendation,
            "salary_action": body.salary_action,
            "manager_submitted_at": iso(now_utc()),
            "manager_reviewer": user["email"],
            "status": "completed",
            "updated_at": iso(now_utc()),
        }},
    )
    await audit("perf_manager_score", f"performance_reviews_v2/{rid}", user, {"manager_rating": body.manager_rating})

    # Fire push notification to employee
    try:
        import push_service
        await push_service.fanout_to_employee(r["employee_id"], {
            "title": "Performance review completed",
            "body": f"Your {r['period']} review is ready to view.",
            "url": "/self-service",
            "kind": "perf_review",
        })
    except Exception:
        pass

    return {"ok": True, "status": "completed"}


@router.post("/reviews/{rid}/acknowledge")
async def acknowledge_review(rid: str, body: AcknowledgeIn, user: dict = Depends(get_current_user)):
    r = await _get_review(rid, user)
    if user.get("employee_id") != r["employee_id"]:
        raise HTTPException(403, "Only the employee can acknowledge")
    if r["status"] != "completed":
        raise HTTPException(409, "Review must be completed first")
    await db.performance_reviews_v2.update_one(
        {"id": rid, **tenant_filter(user)},
        {"$set": {
            "acknowledged_at": iso(now_utc()),
            "employee_comments": body.employee_comments or "",
            "updated_at": iso(now_utc()),
        }},
    )
    await audit("perf_acknowledge", f"performance_reviews_v2/{rid}", user, {})
    return {"ok": True}


@router.get("/cycles/{cid}/analytics")
async def cycle_analytics(cid: str, user: dict = Depends(require_admin)):
    """Aggregated metrics for a single review cycle: avg rating, distribution, completion."""
    tf = tenant_filter(user)
    cycle = await db.review_cycles.find_one({"id": cid, **tf}, {"_id": 0})
    if not cycle:
        raise HTTPException(404, "Cycle not found")
    reviews = await db.performance_reviews_v2.find(
        {"cycle_id": cid, **tf}, {"_id": 0}
    ).to_list(2000)
    total = len(reviews)
    completed = [r for r in reviews if r["status"] == "completed"]
    self_ratings = [r["self_rating"] for r in reviews if r.get("self_rating")]
    mgr_ratings = [r["manager_rating"] for r in completed if r.get("manager_rating")]
    avg_self = round(sum(self_ratings) / max(1, len(self_ratings)), 2) if self_ratings else 0
    avg_manager = round(sum(mgr_ratings) / max(1, len(mgr_ratings)), 2) if mgr_ratings else 0
    distribution = {str(i): 0 for i in range(1, 6)}
    for r in completed:
        if r.get("manager_rating"):
            key = str(int(r["manager_rating"]))
            if key in distribution:
                distribution[key] += 1
    promo = {"none": 0, "consider": 0, "strong": 0}
    salary = {"none": 0, "merit": 0, "promotion": 0}
    for r in completed:
        promo[r.get("promotion_recommendation") or "none"] = promo.get(r.get("promotion_recommendation") or "none", 0) + 1
        salary[r.get("salary_action") or "none"] = salary.get(r.get("salary_action") or "none", 0) + 1
    by_dept: dict = {}
    for r in completed:
        d = r.get("department", "—") or "—"
        by_dept.setdefault(d, []).append(r.get("manager_rating") or 0)
    dept_summary = [
        {"department": d, "count": len(v), "avg_rating": round(sum(v) / max(1, len(v)), 2)}
        for d, v in sorted(by_dept.items())
    ]
    acked = sum(1 for r in completed if r.get("acknowledged_at"))
    return {
        "cycle": {"id": cycle["id"], "name": cycle["name"], "period": cycle["period"]},
        "total_reviews": total,
        "completed": len(completed),
        "completion_rate": round(len(completed) / max(1, total), 3),
        "acknowledged": acked,
        "acknowledgement_rate": round(acked / max(1, len(completed)), 3),
        "avg_self_rating": avg_self,
        "avg_manager_rating": avg_manager,
        "rating_distribution": distribution,
        "promotion_recommendations": promo,
        "salary_actions": salary,
        "department_summary": dept_summary,
    }
