"""Talent: job postings, applicants, performance reviews, training programs + completions."""
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional

from core import db, get_current_user, require_admin, audit, now_utc, iso, tenant_filter, with_tenant, require_feature

router = APIRouter(prefix="/talent", tags=["talent"], dependencies=[Depends(require_feature("talent"))])


# ---- Job postings + applicants ----
class JobPostingIn(BaseModel):
    title: str
    department: str
    location: str = "Freetown"
    employment_type: Literal["Full-time", "Part-time", "Contract", "Intern"] = "Full-time"
    salary_min_sle: float = 0
    salary_max_sle: float = 0
    description: Optional[str] = ""
    status: Literal["open", "closed"] = "open"


class ApplicantIn(BaseModel):
    posting_id: str
    name: str
    email: str
    phone: Optional[str] = ""
    resume_summary: Optional[str] = ""
    stage: Literal["applied", "screening", "interview", "offer", "hired", "rejected"] = "applied"


class ApplicantStageUpdate(BaseModel):
    stage: Literal["applied", "screening", "interview", "offer", "hired", "rejected"]


class ApplicantNoteIn(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


@router.get("/postings")
async def list_postings(user: dict = Depends(get_current_user)):
    return await db.job_postings.find(tenant_filter(user), {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/postings")
async def create_posting(body: JobPostingIn, user: dict = Depends(require_admin)):
    pid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": pid, "created_at": iso(now_utc())}, user)
    await db.job_postings.insert_one(doc)
    doc.pop("_id", None)
    await audit("create", f"job_postings/{pid}", user, {"title": body.title})
    return doc


@router.delete("/postings/{pid}")
async def delete_posting(pid: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    await db.job_postings.delete_one({"id": pid, **tf})
    await db.applicants.delete_many({"posting_id": pid, **tf})
    await audit("delete", f"job_postings/{pid}", user)
    return {"ok": True}


@router.get("/applicants")
async def list_applicants(user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    rows = await db.applicants.find(tf, {"_id": 0}).sort("created_at", -1).to_list(1000)
    postings = {p["id"]: p["title"] for p in await db.job_postings.find(tf, {"_id": 0}).to_list(500)}
    for r in rows:
        r["posting_title"] = postings.get(r["posting_id"], "—")
    return rows


@router.post("/applicants")
async def create_applicant(body: ApplicantIn, user: dict = Depends(require_admin)):
    aid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": aid, "created_at": iso(now_utc())}, user)
    await db.applicants.insert_one(doc)
    doc.pop("_id", None)
    await audit("create", f"applicants/{aid}", user, {"name": body.name})
    return doc


@router.patch("/applicants/{aid}/stage")
async def update_stage(aid: str, body: ApplicantStageUpdate, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    existing = await db.applicants.find_one({"id": aid, **tf}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Not found")
    history_entry = {
        "from": existing.get("stage", "applied"),
        "to": body.stage,
        "by": user["email"],
        "ts": iso(now_utc()),
    }
    await db.applicants.update_one(
        {"id": aid, **tf},
        {
            "$set": {"stage": body.stage, "stage_updated_at": iso(now_utc())},
            "$push": {"stage_history": history_entry},
        },
    )
    await audit("applicant_stage", f"applicants/{aid}", user, {"stage": body.stage})
    return {"ok": True, "stage": body.stage}


@router.post("/applicants/{aid}/notes")
async def add_applicant_note(aid: str, body: ApplicantNoteIn, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    note = {
        "id": str(uuid.uuid4()),
        "note": body.note,
        "by": user["email"],
        "ts": iso(now_utc()),
    }
    res = await db.applicants.update_one(
        {"id": aid, **tf}, {"$push": {"notes": note}}
    )
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    await audit("applicant_note", f"applicants/{aid}", user, {"len": len(body.note)})
    return note


@router.get("/applicants/pipeline")
async def applicants_pipeline(user: dict = Depends(require_admin)):
    """Return applicants grouped by stage — used by the Kanban UI."""
    tf = tenant_filter(user)
    rows = await db.applicants.find(tf, {"_id": 0}).sort("created_at", -1).to_list(2000)
    postings = {p["id"]: p["title"] for p in await db.job_postings.find(tf, {"_id": 0}).to_list(500)}
    stages = ["applied", "screening", "interview", "offer", "hired", "rejected"]
    grouped: dict = {s: [] for s in stages}
    for r in rows:
        r["posting_title"] = postings.get(r.get("posting_id"), "—")
        grouped.setdefault(r.get("stage", "applied"), []).append(r)
    return {"stages": stages, "grouped": grouped, "total": len(rows)}


# ---- Performance reviews ----
class ReviewIn(BaseModel):
    employee_id: str
    period: str  # e.g. "2026-Q1"
    rating: int = Field(..., ge=1, le=5)
    notes: Optional[str] = ""
    reviewer: Optional[str] = ""


@router.get("/reviews")
async def list_reviews(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    q = {**tf} if user["role"] == "admin" else {"employee_id": user.get("employee_id"), **tf}
    rows = await db.performance_reviews.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    employees = {e["id"]: e for e in await db.employees.find(tf, {"_id": 0}).to_list(2000)}
    for r in rows:
        e = employees.get(r["employee_id"], {})
        r["employee_name"] = f'{e.get("first_name","")} {e.get("last_name","")}'.strip() or "—"
    return rows


@router.post("/reviews")
async def create_review(body: ReviewIn, user: dict = Depends(require_admin)):
    rid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": rid, "reviewer": body.reviewer or user["email"], "created_at": iso(now_utc())}, user)
    await db.performance_reviews.insert_one(doc)
    doc.pop("_id", None)
    await audit("create", f"performance_reviews/{rid}", user, {"period": body.period, "rating": body.rating})
    return doc


# ---- Learning & Development ----
class ProgramIn(BaseModel):
    title: str
    provider: Optional[str] = ""
    hours: int = Field(..., ge=0)
    skill_area: str
    description: Optional[str] = ""


class CompletionIn(BaseModel):
    program_id: str
    employee_id: Optional[str] = None
    completed_on: str  # YYYY-MM-DD
    score: Optional[int] = Field(None, ge=0, le=100)


@router.get("/programs")
async def list_programs(user: dict = Depends(get_current_user)):
    return await db.training_programs.find(tenant_filter(user), {"_id": 0}).sort("title", 1).to_list(500)


@router.post("/programs")
async def create_program(body: ProgramIn, user: dict = Depends(require_admin)):
    pid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": pid, "created_at": iso(now_utc())}, user)
    await db.training_programs.insert_one(doc)
    doc.pop("_id", None)
    await audit("create", f"training_programs/{pid}", user, {"title": body.title})
    return doc


@router.delete("/programs/{pid}")
async def delete_program(pid: str, user: dict = Depends(require_admin)):
    await db.training_programs.delete_one({"id": pid, **tenant_filter(user)})
    await audit("delete", f"training_programs/{pid}", user)
    return {"ok": True}


@router.get("/completions")
async def list_completions(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    q = {**tf} if user["role"] == "admin" else {"employee_id": user.get("employee_id"), **tf}
    rows = await db.training_completions.find(q, {"_id": 0}).sort("completed_on", -1).to_list(1000)
    progs = {p["id"]: p for p in await db.training_programs.find(tf, {"_id": 0}).to_list(500)}
    employees = {e["id"]: e for e in await db.employees.find(tf, {"_id": 0}).to_list(2000)}
    for r in rows:
        p = progs.get(r["program_id"], {})
        e = employees.get(r["employee_id"], {})
        r["program_title"] = p.get("title", "—")
        r["program_skill_area"] = p.get("skill_area", "—")
        r["employee_name"] = f'{e.get("first_name","")} {e.get("last_name","")}'.strip() or "—"
    return rows


@router.post("/completions")
async def add_completion(body: CompletionIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] == "admin" else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    cid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": cid, "employee_id": eid, "created_at": iso(now_utc())}, user)
    await db.training_completions.insert_one(doc)
    doc.pop("_id", None)
    await audit("training_completed", f"training_completions/{cid}", user)
    return doc
