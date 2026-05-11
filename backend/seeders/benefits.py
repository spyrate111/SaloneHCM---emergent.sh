"""Benefit plans seeder."""
import uuid
from core import db, now_utc, iso, logger


async def seed(company_id: str) -> None:
    if await db.benefit_plans.count_documents({"company_id": company_id}) > 0:
        return
    plans = [
        ("Premium Health Cover", "health", 350, 70, "Comprehensive medical for employee + family"),
        ("Standard Health Cover", "health", 180, 50, "Basic medical, outpatient + emergency"),
        ("Group Life Insurance", "life", 80, 100, "2× annual salary cover, employer-paid"),
        ("Dental Plan", "dental", 60, 50, "Routine + major dental"),
        ("Pension Top-up", "pension", 200, 50, "Voluntary top-up beyond NASSIT"),
        ("Transport Allowance", "transport", 250, 100, "Monthly fuel/transit stipend"),
    ]
    for name, t, cost, share, desc in plans:
        await db.benefit_plans.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "name": name,
            "type": t,
            "monthly_cost_sle": cost,
            "employer_share_pct": share,
            "description": desc,
            "created_at": iso(now_utc()),
        })
    logger.info("Seeded %d benefit plans for company %s", len(plans), company_id)
