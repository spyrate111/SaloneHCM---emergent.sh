"""Backfill helpers — migrate pre-multitenant data forward."""
from core import db, logger

# Collections that need company_id stamped on existing docs
TENANT_COLLECTIONS = [
    "users", "employees", "payroll_runs", "leave_requests", "attendance",
    "benefit_plans", "benefit_enrollments",
    "job_postings", "candidates", "training_programs", "training_enrollments",
    "performance_reviews",
    "documents", "payroll_scenarios", "audit_logs", "assistant_sessions",
    "assistant_messages",
]


async def backfill_company_id(default_company_id: str) -> None:
    """Stamp company_id on every existing doc that doesn't have one yet."""
    total = 0
    for col in TENANT_COLLECTIONS:
        # Skip non-existent collections silently
        res = await db[col].update_many(
            {"company_id": {"$exists": False}},
            {"$set": {"company_id": default_company_id}},
        )
        if res.modified_count:
            logger.info("Backfilled company_id on %s: %d docs", col, res.modified_count)
            total += res.modified_count
    if total:
        logger.info("Total backfilled docs: %d", total)
