"""Seed baseline budget balances for Gov tenant so pre-payroll budget check
works out of the box. Idempotent — only inserts for a (company, code, period)
tuple that doesn't yet have a row."""
import logging
from datetime import datetime, timezone

from core import db, iso, now_utc

logger = logging.getLogger(__name__)


async def seed_current_period_balances(company_id: str) -> None:
    """Provision a per-budget-code allocation of SLE 50M for the current period.
    Real admins should override via the /payroll-budget/balances UI."""
    now = datetime.now(timezone.utc)
    period = f"{now.year}-{now.month:02d}"

    codes = await db.civil_service_budget_codes.find(
        {"company_id": company_id}, {"_id": 0, "code": 1},
    ).to_list(500)
    if not codes:
        return

    default_alloc = 50_000_000.0  # SLE 50 million per code — generous seed for demo
    inserted = 0
    for c in codes:
        result = await db.budget_balances.update_one(
            {"company_id": company_id, "budget_code": c["code"], "period": period},
            {
                "$setOnInsert": {
                    "company_id": company_id,
                    "budget_code": c["code"],
                    "period": period,
                    "allocated_sle": default_alloc,
                    "note": "Seeded — replace with actual IFMIS allocation via admin UI",
                    "created_at": iso(now_utc()),
                    "updated_at": iso(now_utc()),
                    "updated_by": "system",
                },
            },
            upsert=True,
        )
        if result.upserted_id is not None:
            inserted += 1
    if inserted:
        logger.info("[budget_balances] company=%s period=%s seeded %d balances",
                    company_id, period, inserted)
