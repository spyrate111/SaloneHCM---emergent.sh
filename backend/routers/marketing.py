"""Public marketing lead-capture endpoint (no auth)."""
from __future__ import annotations
import uuid
from typing import Optional
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
