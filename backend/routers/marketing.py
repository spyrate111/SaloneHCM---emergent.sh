"""Public marketing lead-capture endpoints (no auth)."""
from __future__ import annotations
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import db, now_utc, iso, logger, require_superadmin

router = APIRouter(prefix="/marketing", tags=["marketing"])


class LeadIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    company: str = Field(..., min_length=1, max_length=200)
    employees: int = Field(..., ge=1, le=1_000_000)
    message: Optional[str] = Field("", max_length=2000)


@router.post("/leads", status_code=201)
async def create_lead(body: LeadIn):
    """Capture a marketing lead from the public landing page."""
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "name": body.name.strip(),
            "email": body.email.lower(),
            "company": body.company.strip(),
            "employees": int(body.employees),
            "message": (body.message or "").strip(),
            "source": "landing_page",
            "status": "new",
            "created_at": iso(now_utc()),
        }
        await db.marketing_leads.insert_one(doc)
        logger.info("Marketing lead captured: %s (%s, %d emp)", doc["email"], doc["company"], doc["employees"])
        return {"ok": True, "id": doc["id"]}
    except Exception as e:
        logger.warning("Lead capture failed: %s", e)
        raise HTTPException(500, "Could not save your details. Please call sales.")


# ---------- Demo request (multi-step wizard at /demo) ----------

ALLOWED_INDUSTRIES = {"ngo", "mining", "banking", "telecom", "government", "manufacturing", "retail", "other"}
ALLOWED_SIZES = {"1-9", "10-49", "50-249", "250-999", "1000+"}
ALLOWED_TOPICS = {"payroll", "hr", "compliance", "ai", "civil_service", "ifmis", "loans", "talent", "self_service"}


class DemoRequestIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=40)
    company: str = Field(..., min_length=1, max_length=200)
    industry: str
    size: str
    topics: List[str] = Field(..., min_length=1, max_length=20)
    message: Optional[str] = Field(None, max_length=2000)


@router.post("/demo-requests", status_code=201)
async def create_demo_request(body: DemoRequestIn):
    """Capture a multi-step demo-wizard submission."""
    if body.industry not in ALLOWED_INDUSTRIES:
        raise HTTPException(422, f"Invalid industry '{body.industry}'. Allowed: {sorted(ALLOWED_INDUSTRIES)}")
    if body.size not in ALLOWED_SIZES:
        raise HTTPException(422, f"Invalid size '{body.size}'. Allowed: {sorted(ALLOWED_SIZES)}")
    bad = [t for t in body.topics if t not in ALLOWED_TOPICS]
    if bad:
        raise HTTPException(422, f"Invalid topic(s): {bad}. Allowed: {sorted(ALLOWED_TOPICS)}")
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "name": body.name.strip(),
            "email": body.email.lower(),
            "phone": (body.phone or "").strip() or None,
            "company": body.company.strip(),
            "industry": body.industry,
            "size": body.size,
            "topics": list(body.topics),
            "message": (body.message or "").strip() or None,
            "source": "demo_wizard",
            "status": "new",
            "created_at": iso(now_utc()),
        }
        await db.marketing_demo_requests.insert_one(doc)
        logger.info(
            "Demo request captured: %s (%s, industry=%s, size=%s, topics=%s)",
            doc["email"], doc["company"], doc["industry"], doc["size"], doc["topics"],
        )
        return {"ok": True, "id": doc["id"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Demo request capture failed: %s", e)
        raise HTTPException(500, "Could not save your demo request. Please call sales.")


# ---------- Marketing videos (training / walkthrough library) ----------

ALLOWED_VIDEO_CATEGORIES = {"getting_started", "by_persona", "deep_dive", "training"}
ALLOWED_VIDEO_PERSONAS = {"small_business", "midsize", "enterprise", "government", "ngo", "mining", "banking", "general"}


class VideoIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=160)
    summary: str = Field(..., min_length=2, max_length=480)
    src: str = Field(..., min_length=8, max_length=600, description="MP4 URL, YouTube URL, or Vimeo URL")
    poster: Optional[str] = Field(None, max_length=600)
    duration_s: int = Field(..., ge=10, le=14_400)
    category: str
    persona: str = "general"
    chapters: List[dict] = Field(default_factory=list)
    sort: int = 0
    published: bool = True


def _validate_video(v: VideoIn) -> None:
    if v.category not in ALLOWED_VIDEO_CATEGORIES:
        raise HTTPException(422, f"Invalid category '{v.category}'. Allowed: {sorted(ALLOWED_VIDEO_CATEGORIES)}")
    if v.persona not in ALLOWED_VIDEO_PERSONAS:
        raise HTTPException(422, f"Invalid persona '{v.persona}'. Allowed: {sorted(ALLOWED_VIDEO_PERSONAS)}")


@router.get("/videos")
async def list_videos(category: Optional[str] = None, persona: Optional[str] = None, limit: int = 60):
    """Public — list published walkthrough/training videos for the marketing site."""
    q = {"published": True}
    if category:
        q["category"] = category
    if persona:
        q["persona"] = persona
    cursor = db.marketing_videos.find(q, {"_id": 0}).sort([("sort", 1), ("created_at", 1)]).limit(limit)
    return [doc async for doc in cursor]


@router.get("/videos/{vid}")
async def get_video(vid: str):
    doc = await db.marketing_videos.find_one({"id": vid, "published": True}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Video not found")
    return doc


# ---- Super-admin CRUD (mounted under /marketing/admin/videos for consistency) ----

@router.post("/admin/videos", status_code=201)
async def create_video(body: VideoIn, _: dict = Depends(require_superadmin)):
    _validate_video(body)
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = iso(now_utc())
    doc["updated_at"] = doc["created_at"]
    await db.marketing_videos.insert_one(doc)
    logger.info("Marketing video created: %s (%s)", doc["title"], doc["id"])
    doc.pop("_id", None)
    return doc


@router.patch("/admin/videos/{vid}")
async def update_video(vid: str, body: VideoIn, _: dict = Depends(require_superadmin)):
    _validate_video(body)
    update = body.model_dump()
    update["updated_at"] = iso(now_utc())
    r = await db.marketing_videos.update_one({"id": vid}, {"$set": update})
    if not r.matched_count:
        raise HTTPException(404, "Video not found")
    doc = await db.marketing_videos.find_one({"id": vid}, {"_id": 0})
    return doc


@router.delete("/admin/videos/{vid}", status_code=204)
async def delete_video(vid: str, _: dict = Depends(require_superadmin)):
    r = await db.marketing_videos.delete_one({"id": vid})
    if not r.deleted_count:
        raise HTTPException(404, "Video not found")
    return None


@router.get("/admin/videos")
async def admin_list_videos(_: dict = Depends(require_superadmin)):
    """Super-admin sees ALL videos (published + drafts)."""
    cursor = db.marketing_videos.find({}, {"_id": 0}).sort([("sort", 1), ("created_at", 1)])
    return [doc async for doc in cursor]
