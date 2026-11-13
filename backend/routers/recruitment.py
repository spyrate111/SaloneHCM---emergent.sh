"""Recruitment / ATS: vacancies, public applications, stage pipeline, hire-to-employee."""
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

from core import (db, require_roles, audit, tenant_filter, with_tenant,
                  now_utc, iso)
from storage import put_object, get_object, APP_NAME
from routers.payroll_rails import assert_not_cutoff_locked
import email_service

router = APIRouter(prefix="/recruitment", tags=["recruitment"])
public_router = APIRouter(prefix="/careers", tags=["careers-public"])

STAGES = ["applied", "shortlisted", "interview", "offer", "hired", "rejected"]
CV_MIME = {"application/pdf": "pdf",
           "application/msword": "doc",
           "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"}
MAX_CV_BYTES = 5 * 1024 * 1024

_HR = require_roles("hr")


class VacancyIn(BaseModel):
    title: str
    department: str
    grade_level: str = ""
    closing_date: str  # YYYY-MM-DD
    description: str = ""


@router.post("/vacancies")
async def create_vacancy(body: VacancyIn, user: dict = Depends(_HR)):
    vid = str(uuid.uuid4())
    doc = with_tenant({**body.model_dump(), "id": vid, "status": "open",
                       "public_token": uuid.uuid4().hex,
                       "created_by": user["email"],
                       "created_at": iso(now_utc())}, user)
    await db.job_vacancies.insert_one(doc)
    doc.pop("_id", None)
    await audit("vacancy_created", f"job_vacancies/{vid}", user, {"title": body.title})
    return doc


@router.get("/vacancies")
async def list_vacancies(user: dict = Depends(_HR)):
    rows = await db.job_vacancies.find(
        tenant_filter(user), {"_id": 0}).sort("created_at", -1).to_list(500)
    counts = {}
    async for g in db.job_applications.aggregate([
            {"$match": tenant_filter(user)},
            {"$group": {"_id": "$vacancy_id", "n": {"$sum": 1}}}]):
        counts[g["_id"]] = g["n"]
    for r in rows:
        r["application_count"] = counts.get(r["id"], 0)
    return rows


@router.put("/vacancies/{vid}")
async def update_vacancy(vid: str, body: dict, user: dict = Depends(_HR)):
    allowed = {k: v for k, v in (body or {}).items()
               if k in ("title", "department", "grade_level", "closing_date",
                        "description", "status")}
    if allowed.get("status") not in (None, "open", "closed"):
        raise HTTPException(422, "status must be open or closed")
    r = await db.job_vacancies.update_one(
        {"id": vid, **tenant_filter(user)}, {"$set": allowed})
    if not r.matched_count:
        raise HTTPException(404, "Vacancy not found")
    await audit("vacancy_updated", f"job_vacancies/{vid}", user, allowed)
    return {"ok": True}


@router.get("/vacancies/{vid}/applications")
async def list_applications(vid: str, user: dict = Depends(_HR)):
    rows = await db.job_applications.find(
        {"vacancy_id": vid, **tenant_filter(user)}, {"_id": 0}).sort(
        "created_at", -1).to_list(1000)
    for r in rows:
        if r.get("cv"):
            r["cv"] = {"filename": r["cv"]["filename"]}
    return rows


@router.patch("/applications/{aid}/stage")
async def set_stage(aid: str, body: dict, bg: BackgroundTasks, user: dict = Depends(_HR)):
    stage = (body or {}).get("stage")
    if stage not in STAGES:
        raise HTTPException(422, f"stage must be one of: {', '.join(STAGES)}")
    app_doc = await db.job_applications.find_one({"id": aid, **tenant_filter(user)}, {"_id": 0})
    if not app_doc:
        raise HTTPException(404, "Application not found")
    await db.job_applications.update_one(
        {"id": aid}, {"$set": {"stage": stage, "stage_updated_at": iso(now_utc())}})
    await audit("application_stage", f"job_applications/{aid}", user,
                {"name": app_doc["name"], "stage": stage})
    if stage in email_service.STAGE_EMAIL_COPY:
        company = await db.companies.find_one(
            {"id": user["company_id"]}, {"_id": 0, "name": 1}) or {}
        bg.add_task(email_service.send_application_stage_update,
                    app_doc["email"], app_doc["name"], app_doc["vacancy_title"],
                    stage, company.get("name", "SaloneHCM"), user["company_id"])
    return {"ok": True, "stage": stage,
            "prompt_create_employee": stage == "hired" and not app_doc.get("hired_employee_id")}


class HireIn(BaseModel):
    job_title: str
    department: str
    basic_salary_sle: float
    hire_date: str
    allowances_sle: float = 0


@router.post("/applications/{aid}/create-employee")
async def create_employee_from_application(aid: str, body: HireIn, user: dict = Depends(_HR)):
    await assert_not_cutoff_locked(user, "hiring a new employee")
    app_doc = await db.job_applications.find_one({"id": aid, **tenant_filter(user)}, {"_id": 0})
    if not app_doc:
        raise HTTPException(404, "Application not found")
    if app_doc.get("hired_employee_id"):
        raise HTTPException(409, "An employee record was already created from this application")
    parts = (app_doc["name"] or "New Hire").strip().split(" ", 1)
    eid = str(uuid.uuid4())
    emp = with_tenant({
        "id": eid,
        "first_name": parts[0],
        "last_name": parts[1] if len(parts) > 1 else "",
        "email": app_doc["email"],
        "phone": app_doc.get("phone") or "",
        "job_title": body.job_title,
        "department": body.department,
        "location": "Freetown",
        "employment_type": "Full-time",
        "basic_salary_sle": round(float(body.basic_salary_sle), 2),
        "allowances_sle": round(float(body.allowances_sle), 2),
        "nassit_no": "", "tin": "",
        "bank_name": "Sierra Leone Commercial Bank", "bank_account": "",
        "status": "active",
        "hire_date": body.hire_date,
        "hired_from_application": aid,
        "created_at": iso(now_utc()),
    }, user)
    await db.employees.insert_one(emp)
    emp.pop("_id", None)
    await db.job_applications.update_one(
        {"id": aid}, {"$set": {"hired_employee_id": eid, "stage": "hired"}})
    await audit("hired_from_application", f"employees/{eid}", user,
                {"application_id": aid, "name": app_doc["name"]})
    return emp


@router.get("/applications/{aid}/cv")
async def download_cv(aid: str, user: dict = Depends(_HR)):
    app_doc = await db.job_applications.find_one({"id": aid, **tenant_filter(user)}, {"_id": 0})
    if not app_doc or not app_doc.get("cv"):
        raise HTTPException(404, "CV not found")
    data, ct = get_object(app_doc["cv"]["storage_path"])
    return Response(data, media_type=ct or app_doc["cv"]["content_type"],
                    headers={"Content-Disposition":
                             f'attachment; filename="{app_doc["cv"]["filename"]}"'})


# ---------------- public (no auth) ----------------

@public_router.get("")
async def public_open_vacancies():
    """All open, still-accepting vacancies across companies — powers /careers."""
    today = now_utc().strftime("%Y-%m-%d")
    rows = await db.job_vacancies.find(
        {"status": "open", "closing_date": {"$gte": today}},
        {"_id": 0, "title": 1, "department": 1, "grade_level": 1,
         "closing_date": 1, "public_token": 1, "company_id": 1,
         "created_at": 1}).sort("closing_date", 1).to_list(500)
    cids = list({r["company_id"] for r in rows})
    names = {c["id"]: c.get("name", "") async for c in db.companies.find(
        {"id": {"$in": cids}}, {"_id": 0, "id": 1, "name": 1})}
    for r in rows:
        r["company_name"] = names.get(r.pop("company_id"), "")
    return rows

def _public_vacancy(v: dict) -> dict:
    return {k: v.get(k) for k in ("title", "department", "grade_level",
                                  "closing_date", "description", "status")}


async def _open_vacancy(token: str) -> dict:
    v = await db.job_vacancies.find_one({"public_token": token}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Vacancy not found")
    return v


@public_router.get("/{token}")
async def public_vacancy(token: str):
    v = await _open_vacancy(token)
    company = await db.companies.find_one({"id": v["company_id"]}, {"_id": 0, "name": 1}) or {}
    today = now_utc().strftime("%Y-%m-%d")
    out = _public_vacancy(v)
    out["company_name"] = company.get("name", "")
    out["accepting"] = v["status"] == "open" and v["closing_date"] >= today
    return out


@public_router.post("/{token}/apply")
async def public_apply(
    token: str,
    bg: BackgroundTasks,
    name: str = Form(...),
    email: EmailStr = Form(...),
    phone: str = Form(""),
    cover_note: str = Form(""),
    cv: UploadFile = File(...),
):
    v = await _open_vacancy(token)
    today = now_utc().strftime("%Y-%m-%d")
    if v["status"] != "open" or v["closing_date"] < today:
        raise HTTPException(410, "This vacancy is no longer accepting applications")
    if cv.content_type not in CV_MIME:
        raise HTTPException(415, "CV must be a PDF, DOC or DOCX")
    data = await cv.read()
    if not data:
        raise HTTPException(400, "Empty CV file")
    if len(data) > MAX_CV_BYTES:
        raise HTTPException(413, "CV too large (max 5MB)")
    dup = await db.job_applications.find_one(
        {"vacancy_id": v["id"], "email": str(email).lower()})
    if dup:
        raise HTTPException(409, "You have already applied for this vacancy")
    ext = CV_MIME[cv.content_type]
    aid = str(uuid.uuid4())
    path = f"{APP_NAME}/{v['company_id']}/cvs/{v['id']}/{aid}.{ext}"
    try:
        res = put_object(path, data, cv.content_type)
    except Exception as e:
        raise HTTPException(502, f"CV upload failed: {e}") from e
    doc = {
        "id": aid,
        "company_id": v["company_id"],
        "vacancy_id": v["id"],
        "vacancy_title": v["title"],
        "name": name.strip()[:120],
        "email": str(email).lower(),
        "phone": phone.strip()[:40],
        "cover_note": cover_note.strip()[:2000],
        "cv": {"storage_path": res.get("path", path), "content_type": cv.content_type,
               "filename": cv.filename or f"cv.{ext}"},
        "stage": "applied",
        "hired_employee_id": None,
        "created_at": iso(now_utc()),
    }
    await db.job_applications.insert_one(doc)
    company = await db.companies.find_one(
        {"id": v["company_id"]}, {"_id": 0, "name": 1}) or {}
    bg.add_task(email_service.send_application_confirmation,
                doc["email"], doc["name"], v["title"],
                company.get("name", "SaloneHCM"), v["company_id"])
    return {"ok": True, "message": "Application received — HR will be in touch."}
