"""Public marketing lead-capture endpoints (no auth)."""
from __future__ import annotations
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from core import db, now_utc, iso, logger

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
