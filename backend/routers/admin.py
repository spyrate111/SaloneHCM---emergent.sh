"""Super-admin endpoints — manage companies and switch active tenant."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field

from core import db, require_superadmin, hash_password, audit, now_utc, iso, make_access, new_csrf_token, CSRF_COOKIE
from tiers import TIERS, features_for, tier_label

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_superadmin)])

Tier = Literal["lite", "professional", "enterprise", "gov"]


class CompanyCreateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    tin: str = Field("", max_length=40)
    nassit_employer: str = Field("", max_length=40)
    country: str = "Sierra Leone"
    currency: str = "SLE"
    tier: Tier = "professional"
    # Seed an initial admin user for this company
    admin_email: EmailStr
    admin_name: str = Field(..., min_length=2, max_length=120)
    admin_password: str = Field(..., min_length=8, max_length=128)


class TierUpdateIn(BaseModel):
    tier: Tier


@router.get("/companies")
async def list_companies(user: dict = Depends(require_superadmin)):
    companies = await db.companies.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    # Attach headcount per company
    for c in companies:
        c["active_headcount"] = await db.employees.count_documents(
            {"company_id": c["id"], "status": "active"}
        )
        c["user_count"] = await db.users.count_documents({"company_id": c["id"]})
    return companies


@router.post("/companies")
async def create_company(body: CompanyCreateIn, user: dict = Depends(require_superadmin)):
    # uniqueness on company name
    if await db.companies.find_one({"name": body.name}):
        raise HTTPException(409, "Company name already exists")
    if await db.users.find_one({"email": body.admin_email.lower()}):
        raise HTTPException(409, "Admin email is already in use")

    cid = str(uuid.uuid4())
    company_doc = {
        "id": cid,
        "name": body.name,
        "label": tier_label(body.tier),
        "tin": body.tin,
        "nassit_employer": body.nassit_employer,
        "country": body.country,
        "currency": body.currency,
        "tier": body.tier,
        "features": features_for(body.tier),
        "pay_frequency": "monthly",
        "created_at": iso(now_utc()),
        "created_by": user["email"],
    }
    await db.companies.insert_one(company_doc)
    admin_user = {
        "id": str(uuid.uuid4()),
        "email": body.admin_email.lower(),
        "name": body.admin_name,
        "role": "admin",
        "company_id": cid,
        "password_hash": hash_password(body.admin_password),
        "created_at": iso(now_utc()),
        "created_by": user["email"],
    }
    await db.users.insert_one(admin_user)
    company_doc.pop("_id", None)
    admin_user.pop("_id", None)
    admin_user.pop("password_hash", None)
    await audit("company_create", f"companies/{cid}", user,
                {"name": body.name, "tier": body.tier, "admin": body.admin_email})
    return {"company": company_doc, "admin": admin_user}


@router.patch("/companies/{cid}/tier")
async def update_tier(cid: str, body: TierUpdateIn, user: dict = Depends(require_superadmin)):
    company = await db.companies.find_one({"id": cid}, {"_id": 0})
    if not company:
        raise HTTPException(404, "Company not found")
    if company["tier"] == body.tier:
        return company
    await db.companies.update_one(
        {"id": cid},
        {"$set": {
            "tier": body.tier,
            "features": features_for(body.tier),
            "label": tier_label(body.tier),
        }},
    )
    await audit("company_tier_change", f"companies/{cid}", user,
                {"from": company["tier"], "to": body.tier, "name": company["name"]})
    return await db.companies.find_one({"id": cid}, {"_id": 0})


@router.post("/companies/{cid}/switch")
async def switch_company(cid: str, response: Response, user: dict = Depends(require_superadmin)):
    """Issue a new JWT scoped to the target company. Super-admin only."""
    company = await db.companies.find_one({"id": cid}, {"_id": 0})
    if not company:
        raise HTTPException(404, "Company not found")
    # Move the super-admin's user record to the target company (so all tenant_filter queries hit the new tenant)
    await db.users.update_one({"id": user["id"]}, {"$set": {"company_id": cid}})
    token = make_access(user["id"], user["email"], user["role"])
    # Refresh both cookies so subsequent cookie-authenticated requests use the new JWT.
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    csrf = new_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE, value=csrf, httponly=False, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    await audit("company_switch", f"companies/{cid}", user,
                {"to_company": company["name"]})
    return {
        "token": token,
        "csrf_token": csrf,
        "company": {
            "id": company["id"],
            "name": company["name"],
            "tier": company["tier"],
            "label": company.get("label"),
            "features": company.get("features", []),
        },
    }


@router.get("/tiers")
async def list_tiers(_: dict = Depends(require_superadmin)):
    return [
        {"id": t, "label": tier_label(t), "features": features_for(t), "rank": i}
        for i, t in enumerate(TIERS)
    ]


# ---------- Tier-features drift monitor ----------

@router.get("/companies/drift-check")
async def drift_check(_: dict = Depends(require_superadmin)):
    """Scan every company and report any whose `features` array doesn't match its tier."""
    drifted = []
    total = 0
    async for c in db.companies.find({}, {"_id": 0, "id": 1, "name": 1, "tier": 1, "features": 1}):
        total += 1
        expected = set(features_for(c.get("tier", "lite")))
        have = set(c.get("features") or [])
        if have != expected:
            drifted.append({
                "id": c["id"],
                "name": c.get("name", ""),
                "tier": c.get("tier", "lite"),
                "missing": sorted(expected - have),
                "extra": sorted(have - expected),
            })
    return {
        "ok": len(drifted) == 0,
        "total_companies": total,
        "drifted_count": len(drifted),
        "drifted": drifted,
    }


@router.post("/companies/drift-resync")
async def drift_resync(user: dict = Depends(require_superadmin)):
    """One-click resync — re-derive `features` from `tier` for every drifted company.
    Logs an audit entry per fixed company."""
    fixed = []
    async for c in db.companies.find({}, {"_id": 0, "id": 1, "name": 1, "tier": 1, "features": 1}):
        expected = features_for(c.get("tier", "lite"))
        if set(c.get("features") or []) != set(expected):
            await db.companies.update_one(
                {"id": c["id"]},
                {"$set": {"features": expected, "label": tier_label(c.get("tier", "lite"))}},
            )
            await audit("company_features_resync", f"companies/{c['id']}", user, {
                "tier": c.get("tier"), "feature_count": len(expected),
            })
            fixed.append({"id": c["id"], "name": c.get("name", ""), "tier": c.get("tier")})
    return {"ok": True, "fixed_count": len(fixed), "fixed": fixed}
