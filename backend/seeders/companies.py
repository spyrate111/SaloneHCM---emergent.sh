"""Companies seeder — Demo Salone Ltd (Professional) + Sierra Leone Government (Gov)."""
import uuid
from core import db, now_utc, iso, logger
from tiers import features_for, tier_label


async def _ensure(name: str, tier: str, tin: str, nassit: str) -> str:
    existing = await db.companies.find_one({"name": name}, {"_id": 0})
    if existing:
        # Refresh feature list on each boot so tier changes take effect
        await db.companies.update_one(
            {"id": existing["id"]},
            {"$set": {"tier": tier, "features": features_for(tier), "label": tier_label(tier)}},
        )
        return existing["id"]
    cid = str(uuid.uuid4())
    await db.companies.insert_one({
        "id": cid,
        "name": name,
        "label": tier_label(tier),
        "tin": tin,
        "nassit_employer": nassit,
        "country": "Sierra Leone",
        "currency": "SLE",
        "tier": tier,
        "features": features_for(tier),
        "pay_frequency": "monthly",
        "created_at": iso(now_utc()),
    })
    logger.info("Seeded company: %s (%s)", name, tier)
    return cid


async def seed() -> tuple[str, str]:
    """Returns (demo_company_id, gov_company_id)."""
    demo = await _ensure("Demo Salone Ltd.", "enterprise", "TIN-100200300", "NS-EMP-001")
    gov = await _ensure("Government of Sierra Leone", "gov", "GOV-SL-001", "NS-GOV-001")
    return demo, gov
