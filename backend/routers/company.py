"""Company / tier management endpoints."""
from fastapi import APIRouter, Depends

from core import db, get_current_user
from tiers import TIERS, features_for, tier_label

router = APIRouter(prefix="/company", tags=["company"])


@router.get("")
async def my_company(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    if not company:
        return None
    headcount = await db.employees.count_documents({"company_id": company["id"], "status": "active"})
    return {**company, "active_headcount": headcount}


@router.get("/tiers")
async def list_tiers(_: dict = Depends(get_current_user)):
    return [
        {
            "id": t,
            "label": tier_label(t),
            "features": features_for(t),
            "rank": i,
        }
        for i, t in enumerate(TIERS)
    ]
