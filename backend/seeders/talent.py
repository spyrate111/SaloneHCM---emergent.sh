"""Talent seeders — job postings + training programs."""
import uuid
from core import db, now_utc, iso, logger


async def seed(company_id: str) -> None:
    await _seed_jobs(company_id)
    await _seed_training(company_id)


async def _seed_jobs(company_id: str) -> None:
    if await db.job_postings.count_documents({"company_id": company_id}) > 0:
        return
    jobs = [
        ("Senior React Engineer", "Engineering", 5500, 8500),
        ("Payroll Analyst", "Finance", 3500, 5500),
        ("Customer Success Manager", "Support", 3000, 5000),
    ]
    for title, dept, mn, mx in jobs:
        await db.job_postings.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "title": title,
            "department": dept,
            "location": "Freetown",
            "employment_type": "Full-time",
            "salary_min_sle": mn,
            "salary_max_sle": mx,
            "description": f"Looking for an experienced {title} in our {dept} team.",
            "status": "open",
            "created_at": iso(now_utc()),
        })
    logger.info("Seeded %d job postings for company %s", len(jobs), company_id)


async def _seed_training(company_id: str) -> None:
    if await db.training_programs.count_documents({"company_id": company_id}) > 0:
        return
    programs = [
        ("Sierra Leone Tax Compliance 2026", "NRA Academy", 16, "Compliance"),
        ("Advanced Excel for Payroll", "Internal", 12, "Tools"),
        ("Leadership Fundamentals", "African Mgmt Inst.", 24, "Leadership"),
        ("Cybersecurity Awareness", "Internal", 4, "Security"),
    ]
    for title, prov, hrs, skill in programs:
        await db.training_programs.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "title": title,
            "provider": prov,
            "hours": hrs,
            "skill_area": skill,
            "description": "",
            "created_at": iso(now_utc()),
        })
    logger.info("Seeded %d training programs for company %s", len(programs), company_id)
