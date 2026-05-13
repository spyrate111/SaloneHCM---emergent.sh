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
    is_recurring: bool = False
    frequency: Optional[Literal["monthly", "quarterly", "biannual", "annual"]] = None
    next_due_at: Optional[str] = None  # ISO date


class CompletionIn(BaseModel):
    program_id: str
    employee_id: Optional[str] = None
    completed_on: str  # YYYY-MM-DD
    score: Optional[int] = Field(None, ge=0, le=100)


@router.get("/programs")
async def list_programs(user: dict = Depends(get_current_user)):
    return await db.training_programs.find(tenant_filter(user), {"_id": 0}).sort("title", 1).to_list(500)


def _next_due(frequency: str, from_iso: Optional[str]) -> str:
    from datetime import datetime as _dt, timedelta as _td
    base = _dt.fromisoformat((from_iso or iso(now_utc())).replace("Z", "+00:00"))
    days = {"monthly": 30, "quarterly": 90, "biannual": 182, "annual": 365}.get(frequency, 365)
    return iso(base + _td(days=days))


@router.post("/programs")
async def create_program(body: ProgramIn, user: dict = Depends(require_admin)):
    pid = str(uuid.uuid4())
    data = body.model_dump()
    # If recurring but no next_due_at, compute one
    if data.get("is_recurring") and data.get("frequency") and not data.get("next_due_at"):
        data["next_due_at"] = _next_due(data["frequency"], None)
    doc = with_tenant({**data, "id": pid, "created_at": iso(now_utc())}, user)
    await db.training_programs.insert_one(doc)
    doc.pop("_id", None)
    await audit("create", f"training_programs/{pid}", user, {"title": body.title, "recurring": body.is_recurring})
    return doc


@router.patch("/programs/{pid}")
async def update_program(pid: str, body: ProgramIn, user: dict = Depends(require_admin)):
    data = body.model_dump()
    if data.get("is_recurring") and data.get("frequency") and not data.get("next_due_at"):
        data["next_due_at"] = _next_due(data["frequency"], None)
    r = await db.training_programs.update_one(
        {"id": pid, **tenant_filter(user)},
        {"$set": data},
    )
    if not r.matched_count:
        raise HTTPException(404, "Program not found")
    await audit("update", f"training_programs/{pid}", user, {"title": body.title})
    return {"ok": True}


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
        r["program_is_recurring"] = bool(p.get("is_recurring"))
        r["employee_name"] = f'{e.get("first_name","")} {e.get("last_name","")}'.strip() or "—"
    return rows


@router.post("/completions")
async def add_completion(body: CompletionIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if user["role"] in ("admin", "superadmin") else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    cid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": cid, "employee_id": eid, "created_at": iso(now_utc())}, user)
    await db.training_completions.insert_one(doc)
    doc.pop("_id", None)

    # Advance next_due_at on recurring programs
    program = await db.training_programs.find_one({"id": body.program_id, **tenant_filter(user)}, {"_id": 0})
    if program and program.get("is_recurring") and program.get("frequency"):
        await db.training_programs.update_one(
            {"id": body.program_id, **tenant_filter(user)},
            {"$set": {"next_due_at": _next_due(program["frequency"], body.completed_on)}},
        )

    await audit("training_completed", f"training_completions/{cid}", user)
    return doc


@router.get("/completions/{cid}/certificate.pdf")
async def completion_certificate(cid: str, user: dict = Depends(get_current_user)):
    """Generate a PDF certificate of completion."""
    from fastapi.responses import StreamingResponse
    import io as _io
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as pdf_canvas

    tf = tenant_filter(user)
    completion = await db.training_completions.find_one({"id": cid, **tf}, {"_id": 0})
    if not completion:
        raise HTTPException(404, "Completion not found")
    # Employees can only download their own; admins can download any.
    if user["role"] not in ("admin", "superadmin") and completion["employee_id"] != user.get("employee_id"):
        raise HTTPException(403, "Not allowed")

    program = await db.training_programs.find_one({"id": completion["program_id"], **tf}, {"_id": 0}) or {}
    employee = await db.employees.find_one({"id": completion["employee_id"], **tf}, {"_id": 0}) or {}
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}

    buf = _io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=landscape(A4))
    W, H = landscape(A4)

    # Ornamental border
    c.setStrokeColor(colors.HexColor("#133326"))
    c.setLineWidth(4)
    c.rect(1.2 * cm, 1.2 * cm, W - 2.4 * cm, H - 2.4 * cm)
    c.setLineWidth(0.8)
    c.rect(1.6 * cm, 1.6 * cm, W - 3.2 * cm, H - 3.2 * cm)

    # Header
    c.setFillColor(colors.HexColor("#133326"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2.4 * cm, H - 2.4 * cm, "SaloneHCM · " + (company.get("name") or "SaloneHCM"))

    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(W / 2, H - 5.5 * cm, "CERTIFICATE OF COMPLETION")

    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#525860"))
    c.drawCentredString(W / 2, H - 7.2 * cm, "This is to certify that")

    full_name = f"{employee.get('first_name','')} {employee.get('last_name','')}".strip() or "—"
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#1A1C1E"))
    c.drawCentredString(W / 2, H - 9.0 * cm, full_name)

    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#525860"))
    c.drawCentredString(W / 2, H - 10.4 * cm, "has successfully completed the training program")

    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.HexColor("#26547C"))
    c.drawCentredString(W / 2, H - 12.0 * cm, program.get("title", "Training"))

    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#525860"))
    skill = program.get("skill_area", "—")
    hours = program.get("hours", 0)
    c.drawCentredString(W / 2, H - 13.0 * cm, f"Skill area: {skill}  ·  {hours} training hours")

    if completion.get("score") is not None:
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.HexColor("#2D7A5D"))
        c.drawCentredString(W / 2, H - 14.2 * cm, f"Final score: {completion['score']}%")

    # Footer
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#686D76"))
    c.drawString(2.4 * cm, 2.2 * cm, f"Completed on: {completion.get('completed_on','—')}")
    c.drawRightString(W - 2.4 * cm, 2.2 * cm, f"Certificate ID: {cid}")

    c.showPage()
    c.save()
    buf.seek(0)

    await audit("training_certificate_download", f"training_completions/{cid}", user, {})
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificate-{cid[:8]}.pdf"'},
    )
