"""Company-scoped foreign exchange reference-rate register.

Rates are manually transcribed from an identified source document and require
second-person approval. This module records references only; it does not convert
payroll, statutory values, or mobile-money payouts.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError

from core import (
    audit, db, get_current_user, is_admin, iso, now_utc, require_feature,
    tenant_filter, with_tenant,
)

router = APIRouter(
    prefix="/fx-rates",
    tags=["fx-rates"],
    dependencies=[Depends(require_feature("analytics"))],
)


class FxRateSetIn(BaseModel):
    publication_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_type: Literal["bsl_reference", "manual_override"] = "bsl_reference"
    source_url: AnyHttpUrl
    rates_sle_per_unit: dict[str, float] = Field(..., min_length=1)
    notes: str = Field("", max_length=500)
    revision: int = Field(1, ge=1, le=100)

    @field_validator("rates_sle_per_unit")
    @classmethod
    def validate_rates(cls, values: dict[str, float]) -> dict[str, float]:
        normalized = {}
        for raw_code, raw_rate in values.items():
            code = str(raw_code).strip().upper()
            rate = float(raw_rate)
            if len(code) != 3 or not code.isalpha():
                raise ValueError("Currency codes must be three letters")
            if code in {"SLE", "SLL"}:
                raise ValueError("Reference rates must be for foreign currencies against SLE")
            if not math.isfinite(rate) or rate <= 0 or rate > 1_000_000_000:
                raise ValueError(f"Rate for {code} must be a positive finite number")
            if code in normalized:
                raise ValueError(f"Duplicate currency code: {code}")
            normalized[code] = round(rate, 8)
        return normalized


async def _require_fx_manager(user: dict = Depends(get_current_user)) -> dict:
    if not (
        is_admin(user)
        or user.get("role") == "payroll"
        or user.get("finance_officer")
    ):
        raise HTTPException(403, "Finance officer, payroll officer, or admin only")
    return user



@router.get("")
async def list_fx_rate_sets(user: dict = Depends(get_current_user)):
    """List this company's reference-rate sets, including approval provenance."""
    rows = await db.fx_rate_sets.find(
        tenant_filter(user), {"_id": 0},
    ).sort([("publication_date", -1), ("revision", -1), ("created_at", -1)]).to_list(250)
    return rows


@router.get("/{rate_set_id}")
async def get_fx_rate_set(rate_set_id: str, user: dict = Depends(get_current_user)):
    row = await db.fx_rate_sets.find_one(
        {"id": rate_set_id, **tenant_filter(user)}, {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "FX rate set not found")
    return row


@router.post("", status_code=201)
async def create_fx_rate_set(
    body: FxRateSetIn,
    user: dict = Depends(_require_fx_manager),
):
    source_url = str(body.source_url)
    parsed = urlsplit(source_url)
    if parsed.scheme != "https":
        raise HTTPException(422, "FX source links must use HTTPS")
    if body.source_type == "bsl_reference" and parsed.hostname not in {"bsl.gov.sl", "www.bsl.gov.sl"}:
        raise HTTPException(422, "BSL reference rates must link to an official bsl.gov.sl document")
    if body.source_type == "manual_override" and not body.notes.strip():
        raise HTTPException(422, "Manual overrides require a reason")

    key_parts = (
        user["company_id"], body.publication_date, body.source_type, str(body.revision),
    )
    rate_set_id = hashlib.sha256("|".join(key_parts).encode("utf-8")).hexdigest()
    base_filter = {
        **tenant_filter(user),
        "publication_date": body.publication_date,
        "source_type": body.source_type,
    }
    latest = await db.fx_rate_sets.find_one(
        base_filter, {"_id": 0, "revision": 1}, sort=[("revision", -1)],
    )
    expected_revision = int((latest or {}).get("revision", 0)) + 1
    if body.revision != expected_revision:
        raise HTTPException(409, f"Next revision for this date and source must be {expected_revision}")

    doc = with_tenant({
        "id": rate_set_id,
        "publication_date": body.publication_date,
        "base_currency": "SLE",
        "rate_direction": "SLE per one unit of foreign currency",
        "source_type": body.source_type,
        "source_url": source_url,
        "rates_sle_per_unit": body.rates_sle_per_unit,
        "notes": body.notes.strip(),
        "revision": body.revision,
        "status": "pending",
        "created_at": iso(now_utc()),
        "created_by_user_id": user.get("id"),
        "created_by": user.get("email"),
        "retrieved_at": iso(now_utc()),
    }, user)
    try:
        await db.fx_rate_sets.insert_one({**doc, "_id": rate_set_id})
    except DuplicateKeyError:
        raise HTTPException(409, "This rate-set revision already exists")

    await audit("fx_rate_set_created", f"fx_rate_sets/{rate_set_id}", user, {
        "publication_date": body.publication_date,
        "source_type": body.source_type,
        "revision": body.revision,
        "currency_count": len(body.rates_sle_per_unit),
    })
    return doc


@router.post("/{rate_set_id}/approve")
async def approve_fx_rate_set(
    rate_set_id: str,
    user: dict = Depends(_require_fx_manager),
):
    query = {"id": rate_set_id, **tenant_filter(user)}
    row = await db.fx_rate_sets.find_one(query, {"_id": 0})
    if not row:
        raise HTTPException(404, "FX rate set not found")
    if row.get("status") != "pending":
        raise HTTPException(409, "Only pending FX rate sets can be approved")
    if row.get("created_by_user_id") == user.get("id"):
        raise HTTPException(403, "A different finance user must approve this rate set")

    updated = await db.fx_rate_sets.update_one(
        {**query, "status": "pending"},
        {"$set": {
            "status": "approved",
            "approved_at": iso(now_utc()),
            "approved_by_user_id": user.get("id"),
            "approved_by": user.get("email"),
        }},
    )
    if updated.modified_count != 1:
        raise HTTPException(409, "This FX rate set was approved by another user")
    await audit("fx_rate_set_approved", f"fx_rate_sets/{rate_set_id}", user, {
        "publication_date": row["publication_date"],
        "source_type": row["source_type"],
        "revision": row["revision"],
    })
    return await db.fx_rate_sets.find_one(query, {"_id": 0})
