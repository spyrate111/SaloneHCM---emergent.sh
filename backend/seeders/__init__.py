"""SaloneHCM seed orchestrator — runs per-domain seeders in order."""
from core import db, logger
from . import companies, users, employees, benefits, talent, gov, civil_service
from . import migrate


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
    logger.info("Seed complete")
