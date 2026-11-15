"""Companies seeder — Demo Salone Ltd (Professional) + Sierra Leone Government (Gov)."""
import uuid
from core import db, now_utc, iso, logger
from tiers import features_for, tier_label


async def _ensure(name: str, tier: str, tin: str, nassit: str, ifmis_org_code: str | None = None) -> str:
    existing = await db.companies.find_one({"name": name}, {"_id": 0})
    if existing:
        # Refresh feature list + ifmis_org_code on each boot so tier changes take effect.
        updates = {
            "tier": tier,
            "features": features_for(tier),
            "label": tier_label(tier),
        }
        if ifmis_org_code and not existing.get("ifmis_org_code"):
            updates["ifmis_org_code"] = ifmis_org_code
        await db.companies.update_one({"id": existing["id"]}, {"$set": updates})
        return existing["id"]
    cid = str(uuid.uuid4())
    doc = {
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
    }
    if ifmis_org_code:
        doc["ifmis_org_code"] = ifmis_org_code
    await db.companies.insert_one(doc)
    logger.info("Seeded company: %s (%s)", name, tier)
    return cid


async def seed() -> tuple[str, str]:
    """Returns (demo_company_id, gov_company_id)."""
    demo = await _ensure("Demo Salone Ltd.", "enterprise", "TIN-100200300", "NS-EMP-001",
                         ifmis_org_code="ENT-DEMO-001")
    gov = await _ensure("Government of Sierra Leone", "gov", "GOV-SL-001", "NS-GOV-001",
                        ifmis_org_code="GoSL-CONS-FUND")
    return demo, gov
