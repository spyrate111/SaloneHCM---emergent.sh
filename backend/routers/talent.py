"""Talent: job postings, applicants, performance reviews, training programs + completions."""
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional

from core import db, get_current_user, require_admin, audit, now_utc, iso, tenant_filter, with_tenant, require_feature, is_admin

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
    q = {**tf} if is_admin(user) else {"employee_id": user.get("employee_id"), **tf}
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
    q = {**tf} if is_admin(user) else {"employee_id": user.get("employee_id"), **tf}
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
        # Talent → Performance cross-link: 3+ recurring completions ⇒ auto-flag a review
        try:
            await _maybe_trigger_perf_review(eid, body.program_id, program, user)
        except Exception:
            pass

    await audit("training_completed", f"training_completions/{cid}", user)
    return doc


async def _maybe_trigger_perf_review(employee_id: str, program_id: str, program: dict, user: dict) -> None:
    """When an employee has completed THIS recurring program ≥ THRESHOLD times,
    auto-create a one-off performance review tied to it.
    """
    THRESHOLD = 3
    tf = tenant_filter(user)
    count = await db.training_completions.count_documents({
        "employee_id": employee_id, "program_id": program_id, **tf,
    })
    if count < THRESHOLD:
        return
    # Already triggered for this employee/program combo?
    already = await db.performance_reviews_v2.find_one({
        "employee_id": employee_id,
        "source": "auto_recurring_training",
        "source_program_id": program_id,
        **tf,
    }, {"_id": 0, "id": 1})
    if already:
        return
    emp = await db.employees.find_one({"id": employee_id, **tf}, {"_id": 0})
    if not emp:
        return
    rid = str(uuid.uuid4())
    cycle_name = f"Auto-review · {program.get('title', 'recurring program')}"
    period = now_utc().strftime("%Y-%m")
    doc = with_tenant({
        "id": rid,
        "cycle_id": f"auto_{program_id}",
        "cycle_name": cycle_name,
        "period": period,
        "employee_id": employee_id,
        "employee_name": f'{emp.get("first_name","")} {emp.get("last_name","")}'.strip(),
        "department": emp.get("department", ""),
        "manager_id": emp.get("manager_id"),
        "status": "pending_self",
        "source": "auto_recurring_training",
        "source_program_id": program_id,
        "source_count": count,
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
    }, user)
    await db.performance_reviews_v2.insert_one(doc)

    # Notify the employee via push
    try:
        import push_service
        await push_service.fanout_to_employee(employee_id, {
            "title": "Performance review opened",
            "body": f"Auto-triggered by {count} completions of '{program.get('title','')}'.",
            "url": "/performance",
            "kind": "perf_auto_review",
        })
    except Exception:
        pass


def _cert_border(c, W: float, H: float, cm: float) -> None:
    """Draw the ornamental double-line border on the certificate."""
    from reportlab.lib import colors
    c.setStrokeColor(colors.HexColor("#0A4A1E"))
    c.setLineWidth(4)
    c.rect(1.2 * cm, 1.2 * cm, W - 2.4 * cm, H - 2.4 * cm)
    c.setLineWidth(0.8)
    c.rect(1.6 * cm, 1.6 * cm, W - 3.2 * cm, H - 3.2 * cm)


def _cert_body(c, W: float, H: float, cm: float, *, company_name: str, full_name: str, program: dict, completion: dict) -> None:
    """Render the textual content of the certificate."""
    from reportlab.lib import colors
    c.setFillColor(colors.HexColor("#0A4A1E"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2.4 * cm, H - 2.4 * cm, "SaloneHCM · " + company_name)

    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(W / 2, H - 5.5 * cm, "CERTIFICATE OF COMPLETION")

    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#525860"))
    c.drawCentredString(W / 2, H - 7.2 * cm, "This is to certify that")

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
        c.setFillColor(colors.HexColor("#17A035"))
        c.drawCentredString(W / 2, H - 14.2 * cm, f"Final score: {completion['score']}%")


def _cert_footer(c, W: float, cm: float, *, cid: str, completed_on: str) -> None:
    """Render the bottom-left date + bottom-right certificate ID."""
    from reportlab.lib import colors
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#686D76"))
    c.drawString(2.4 * cm, 2.2 * cm, f"Completed on: {completed_on}")
    c.drawRightString(W - 2.4 * cm, 2.2 * cm, f"Certificate ID: {cid}")


def _cert_qr(c, W: float, cm: float, cid: str) -> None:
    """Draw a QR code linking to the public verify URL."""
    try:
        import qrcode as _qr
        from reportlab.lib.utils import ImageReader
        from reportlab.lib import colors
        import io as _io2
        frontend_url = os.environ.get("FRONTEND_URL", "")
        verify_url = f"{frontend_url}/verify/{cid}" if frontend_url else f"/verify/{cid}"
        q = _qr.QRCode(border=1, box_size=4)
        q.add_data(verify_url)
        q.make(fit=True)
        img = q.make_image(fill_color="#0A4A1E", back_color="#FFFFFF").convert("RGB")
        b = _io2.BytesIO()
        img.save(b, format="PNG")
        b.seek(0)
        size = 2.6 * cm
        c.drawImage(ImageReader(b), W - 2.4 * cm - size, 2.6 * cm, width=size, height=size)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#A1A5AB"))
        c.drawRightString(W - 2.4 * cm - size - 0.2 * cm, 3.6 * cm, "Scan to verify")
    except Exception:
        pass


@router.get("/completions/{cid}/certificate.pdf")
async def completion_certificate(cid: str, user: dict = Depends(get_current_user)):
    """Generate a PDF certificate of completion."""
    from fastapi.responses import StreamingResponse
    import io as _io
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as pdf_canvas

    tf = tenant_filter(user)
    completion = await db.training_completions.find_one({"id": cid, **tf}, {"_id": 0})
    if not completion:
        raise HTTPException(404, "Completion not found")
    if user["role"] not in ("admin", "superadmin") and completion["employee_id"] != user.get("employee_id"):
        raise HTTPException(403, "Not allowed")

    program = await db.training_programs.find_one({"id": completion["program_id"], **tf}, {"_id": 0}) or {}
    employee = await db.employees.find_one({"id": completion["employee_id"], **tf}, {"_id": 0}) or {}
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    full_name = f"{employee.get('first_name','')} {employee.get('last_name','')}".strip() or "—"

    buf = _io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=landscape(A4))
    W, H = landscape(A4)

    _cert_border(c, W, H, cm)
    _cert_body(c, W, H, cm, company_name=company.get("name") or "SaloneHCM",
               full_name=full_name, program=program, completion=completion)
    _cert_footer(c, W, cm, cid=cid, completed_on=completion.get("completed_on", "—"))
    _cert_qr(c, W, cm, cid)

    c.showPage()
    c.save()
    buf.seek(0)

    await audit("training_certificate_download", f"training_completions/{cid}", user, {})
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="certificate-{cid[:8]}.pdf"'},
    )
