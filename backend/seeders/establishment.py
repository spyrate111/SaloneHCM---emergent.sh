"""Seed sample establishment positions for the Government of Sierra Leone tenant.

Realistic but minimal — a slice of MoF + Health + Education positions.
Auto-assigns existing Gov employees to roughly matching positions so the
tree page shows non-zero filled counts on first load.
"""
import uuid
from core import db, logger, now_utc, iso


SAMPLE_POSITIONS = [
    # Ministry of Finance
    ("Ministry of Finance", "Office of the Permanent Secretary", "Executive", "Permanent Secretary", "GS15", 1, 1, "110.01.001"),
    ("Ministry of Finance", "Office of the Permanent Secretary", "Executive", "Director of Administration", "GS13", 1, 1, "110.01.001"),
    ("Ministry of Finance", "Office of the Permanent Secretary", "Executive", "Senior Personal Assistant", "GS09", 1, 1, "110.01.001"),
    ("Ministry of Finance", "Budget Bureau", "Budget Operations", "Budget Director", "GS13", 1, 1, "110.02.001"),
    ("Ministry of Finance", "Budget Bureau", "Budget Operations", "Budget Analyst", "GS10", 1, 5, "110.02.001"),
    ("Ministry of Finance", "Budget Bureau", "Budget Operations", "Junior Budget Officer", "GS07", 1, 3, "110.02.001"),
    ("Ministry of Finance", "Accountant General's Department", "Payroll Operations", "Payroll Manager", "GS12", 1, 1, "110.02.002"),
    ("Ministry of Finance", "Accountant General's Department", "Payroll Operations", "Payroll Officer", "GS09", 1, 4, "110.02.002"),

    # Ministry of Health
    ("Ministry of Health and Sanitation", "Directorate of Primary Healthcare", "Maternal Health Unit", "Senior Midwifery Coordinator", "GS11", 1, 2, "120.03.001"),
    ("Ministry of Health and Sanitation", "Directorate of Primary Healthcare", "Maternal Health Unit", "Community Health Officer", "GS08", 1, 12, "120.03.001"),
    ("Ministry of Health and Sanitation", "Directorate of Disease Prevention", "Surveillance Unit", "Epidemiologist", "GS11", 1, 4, "120.04.002"),

    # Ministry of Basic and Senior Secondary Education
    ("Ministry of Basic and Senior Secondary Education", "Directorate of Inspectorate", "Western Area Inspectorate", "Senior School Inspector", "GS11", 1, 6, "130.05.001"),
    ("Ministry of Basic and Senior Secondary Education", "Directorate of Inspectorate", "Western Area Inspectorate", "Assistant Inspector", "GS08", 1, 15, "130.05.001"),
    ("Ministry of Basic and Senior Secondary Education", "Directorate of Teacher Development", "TVET Unit", "TVET Coordinator", "GS10", 1, 3, "130.06.002"),
]


async def seed_establishment(company_id: str) -> None:
    existing = await db.establishment_positions.count_documents({"company_id": company_id})
    if existing:
        logger.info("Establishment positions already seeded for %s (%d existing)", company_id, existing)
        return
    docs = []
    now_iso = iso(now_utc())
    for ministry, directorate, unit, title, grade, step, approved, budget_code in SAMPLE_POSITIONS:
        docs.append({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "ministry": ministry,
            "directorate": directorate,
            "unit": unit,
            "position_title": title,
            "grade_code": grade,
            "step_number": step,
            "approved_count": approved,
            "budget_code": budget_code,
            "status": "active",
            "created_at": now_iso,
            "created_by": "seed",
        })
    if docs:
        await db.establishment_positions.insert_many(docs)
        logger.info("Seeded %d establishment positions for tenant %s", len(docs), company_id)

    # Best-effort: assign existing Gov employees to MoF positions so the tree
    # page is not empty on first load. We don't try to match titles — just
    # round-robin assign to whichever positions still have capacity.
    employees = await db.employees.find(
        {"company_id": company_id, "status": "active", "position_id": {"$exists": False}},
        {"_id": 0, "id": 1, "department": 1},
    ).to_list(500)
    positions = await db.establishment_positions.find(
        {"company_id": company_id}, {"_id": 0},
    ).to_list(500)
    pos_capacity = {p["id"]: p["approved_count"] for p in positions}
    pos_filled: dict[str, int] = {p["id"]: 0 for p in positions}
    assigned = 0
    for e in employees:
        # Prefer positions with matching directorate, else any with capacity
        choices = [p for p in positions if pos_filled[p["id"]] < pos_capacity[p["id"]]]
        if not choices:
            break
        # Prefer same department/directorate match
        match = next((p for p in choices if p["directorate"].lower() == (e.get("department") or "").lower()), None)
        chosen = match or choices[0]
        # The establishment registry is the authoritative source for which
        # MDA budget code an employee bills against. Set it here so payroll
        # reflects the position structure. Grade is NOT overridden — that
        # comes from the civil-service grades collection, which already ran.
        update = {
            "position_id": chosen["id"],
            "mda_ministry": chosen["ministry"],
            "department": chosen["directorate"],
        }
        if chosen.get("budget_code") and not e.get("budget_code"):
            update["budget_code"] = chosen["budget_code"]
        await db.employees.update_one({"id": e["id"]}, {"$set": update})
        pos_filled[chosen["id"]] += 1
        assigned += 1
    logger.info("Auto-assigned %d Gov employees to establishment positions", assigned)
