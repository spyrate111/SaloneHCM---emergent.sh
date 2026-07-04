"""SaloneHCM seed orchestrator — runs per-domain seeders in order."""
from core import db, logger
from tiers import features_for
from . import companies, users, employees, benefits, talent, gov, civil_service, establishment
from . import migrate
from . import marketing_videos


async def _resync_all_company_features() -> None:
    """Ensure every company's `features` array matches its current `tier`.

    Some admin paths (direct tier overrides, test fixtures) historically
    mutated `tier` without re-deriving `features`, causing `require_feature()`
    402s for routes that should be enabled. Re-deriving on every boot is
    cheap (~ms) and prevents drift.
    """
    n = 0
    async for c in db.companies.find({}, {"_id": 0, "id": 1, "tier": 1, "features": 1, "name": 1}):
        expected = features_for(c.get("tier", "lite"))
        if set(c.get("features") or []) != set(expected):
            await db.companies.update_one({"id": c["id"]}, {"$set": {"features": expected}})
            n += 1
    if n:
        logger.info("Re-synced features for %d company tier mismatch(es)", n)


async def seed() -> None:
    """Run all seeders idempotently on startup."""
    await db.users.create_index("email", unique=True)
    await db.employees.create_index("email", unique=True)

    # Backfill old data first (no company_id), then seed missing.
    demo_id, gov_id = await companies.seed()
    await migrate.backfill_company_id(default_company_id=demo_id)

    await users.seed_admin(company_id=demo_id)
    await employees.seed(company_id=demo_id)
    await employees.backfill_bank_and_managers()
    await benefits.seed(company_id=demo_id)
    await talent.seed(company_id=demo_id)

    # Gov of Sierra Leone tenant — populated so the Gov-tier features
    # (bulk SMS payslips, ministry reports) can be exercised end-to-end.
    await gov.seed_gov_admin(company_id=gov_id)
    await gov.seed(company_id=gov_id)

    # Civil-service config for the Gov tenant
    await civil_service.seed_civil_service(company_id=gov_id)
    await civil_service.upgrade_gov_employees(company_id=gov_id)

    # Establishment positions (Gov + Demo) — Ministry→Directorate→Unit→Position
    await establishment.seed_establishment(company_id=gov_id)

    # Auto-publish every vacant establishment_position to Talent ATS.
    # Idempotent — safe on every boot. Closes filled/frozen positions too.
    try:
        from establishment_ats_sync import sync_all_positions_for_tenant
        async for _c in db.companies.find({}, {"_id": 0, "id": 1}):
            await sync_all_positions_for_tenant(_c["id"])
    except Exception as e:
        logger.warning("establishment→ats sync failed on boot: %s", e)

    # Marketing video library (public training/walkthrough videos)
    await marketing_videos.seed_videos()

    # Final safety net: any company whose `features` array drifted from its
    # `tier` gets re-derived from tiers.py. Catches direct admin tier mutations.
    await _resync_all_company_features()
    logger.info("Seed complete")
