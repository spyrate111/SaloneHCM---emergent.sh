"""Sierra Leone civil-service seed — grades, steps, allowance rules, MDA budget codes.
Idempotent; only inserts if collections are empty for the given company."""
import uuid
from core import db, now_utc, iso, logger

# Sierra Leone civil-service grade structure (representative ranges)
# Format: (code, name, cadre, step_amounts[1..N] monthly SLE)
GRADES = [
    ("GR1", "Permanent Secretary / Senior Director", "Senior Management", [13500, 14200, 14900, 15600, 16300, 17000]),
    ("GR2", "Director", "Senior Management", [10500, 11000, 11500, 12000, 12500, 13000]),
    ("GR3", "Deputy Director", "Senior Management", [8500, 8900, 9300, 9700, 10100, 10500]),
    ("GR4", "Principal Officer", "Professional", [6800, 7100, 7400, 7700, 8000, 8300]),
    ("GR5", "Senior Officer", "Professional", [5400, 5650, 5900, 6150, 6400, 6650]),
    ("GR6", "Officer", "Professional", [4200, 4400, 4600, 4800, 5000, 5200]),
    ("GR7", "Assistant Officer", "Sub-Professional", [3200, 3350, 3500, 3650, 3800, 3950]),
    ("GR8", "Senior Clerk / Technician", "Sub-Professional", [2400, 2520, 2640, 2760, 2880, 3000]),
    ("GR9", "Clerk / Administrative Assistant", "Support", [1800, 1890, 1980, 2070, 2160, 2250]),
    ("GR10", "Junior Clerk / Messenger", "Support", [1200, 1260, 1320, 1380, 1440, 1500]),
]

# Allowance rule schedule (Gov tier default)
ALLOWANCE_RULES = [
    {"kind": "housing", "label": "Housing allowance", "pct_of_basic": 0.15, "applies_to_grades": [], "enabled": True},
    {"kind": "transport", "label": "Transport allowance", "flat_sle": 450, "applies_to_grades": [], "enabled": True},
    {"kind": "responsibility", "label": "Responsibility allowance", "pct_of_basic": 0.20,
     "applies_to_grades": ["GR1", "GR2", "GR3", "GR4"], "enabled": True},
    {"kind": "hardship", "label": "Hardship-posting allowance", "flat_sle": 800,
     "applies_to_grades": [], "enabled": True},
]

# Sample MDA budget codes (Vote.Programme.Sub-Programme)
BUDGET_CODES = [
    ("110.01.001", "Ministry of Finance — Treasury Operations", "Ministry of Finance", "Treasury", 2026),
    ("110.02.001", "Ministry of Finance — NRA Tax Administration", "Ministry of Finance", "NRA", 2026),
    ("110.02.002", "Ministry of Finance — NASSIT Pensions", "Ministry of Finance", "NASSIT", 2026),
    ("120.01.001", "Ministry of Labour — Workforce Policy", "Ministry of Labour", "Policy", 2026),
    ("310.01.001", "Ministry of Health — Hospitals & Clinics", "Ministry of Health", "Healthcare", 2026),
    ("310.01.002", "Ministry of Health — Primary Care", "Ministry of Health", "Primary Care", 2026),
]


async def seed_civil_service(company_id: str) -> None:
    """Seed default grades/steps/allowance rules/budget codes for a Gov-tier tenant."""
    existing = await db.civil_service_grades.count_documents({"company_id": company_id})
    if existing:
        return
    now = iso(now_utc())

    # Grades + steps
    for code, name, cadre, steps in GRADES:
        await db.civil_service_grades.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "code": code, "name": name, "cadre": cadre, "notes": "",
            "created_at": now,
        })
        for i, amount in enumerate(steps, start=1):
            await db.civil_service_steps.insert_one({
                "id": str(uuid.uuid4()),
                "company_id": company_id,
                "grade_code": code,
                "step_number": i,
                "monthly_amount_sle": amount,
                "updated_at": now,
            })

    # Allowance rules
    for rule in ALLOWANCE_RULES:
        await db.civil_service_allowance_rules.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            **rule,
            "flat_sle": rule.get("flat_sle"),
            "pct_of_basic": rule.get("pct_of_basic"),
            "created_at": now,
        })

    # Budget codes
    for code, name, ministry, program, fy in BUDGET_CODES:
        await db.civil_service_budget_codes.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": company_id,
            "code": code, "name": name, "ministry": ministry,
            "program": program, "fiscal_year": fy,
            "created_at": now,
        })

    logger.info("Seeded civil-service config for company %s (%d grades, %d allowance rules, %d budget codes)",
                company_id, len(GRADES), len(ALLOWANCE_RULES), len(BUDGET_CODES))


async def upgrade_gov_employees(company_id: str) -> None:
    """One-time migration: assign existing Gov employees to grades/steps + budget codes.
    Idempotent — only runs if employees still lack a grade_code.
    """
    untouched = await db.employees.count_documents({
        "company_id": company_id,
        "grade_code": {"$exists": False},
    })
    if not untouched:
        return

    # Map seed job titles → grade codes
    title_to_grade = {
        "Permanent Secretary": ("GR1", 4),
        "Director General": ("GR2", 5),
        "Senior Officer": ("GR5", 3),
        "Accountant": ("GR6", 2),
        "Payroll Analyst": ("GR6", 4),
        "IT Support": ("GR7", 2),
    }
    # Map departments → MDA budget codes
    dept_to_budget = {
        "Ministry of Finance": ("110.01.001", "Ministry of Finance"),
        "Ministry of Labour": ("120.01.001", "Ministry of Labour"),
        "NRA": ("110.02.001", "Ministry of Finance"),
        "NASSIT": ("110.02.002", "Ministry of Finance"),
        "Ministry of Health": ("310.01.001", "Ministry of Health"),
    }

    emps = await db.employees.find({"company_id": company_id}, {"_id": 0}).to_list(2000)
    updated = 0
    for e in emps:
        if e.get("grade_code"):
            continue
        title = e.get("job_title", "")
        dept = e.get("department", "")
        grade_step = title_to_grade.get(title)
        budget = dept_to_budget.get(dept)
        patch = {}
        if grade_step:
            grade_code, step = grade_step
            step_doc = await db.civil_service_steps.find_one(
                {"company_id": company_id, "grade_code": grade_code, "step_number": step},
                {"_id": 0, "monthly_amount_sle": 1},
            )
            patch["grade_code"] = grade_code
            patch["step_number"] = step
            if step_doc:
                patch["basic_salary_sle"] = float(step_doc["monthly_amount_sle"])
        if budget:
            patch["budget_code"] = budget[0]
            patch["mda_ministry"] = budget[1]
        # Sensible allowance defaults
        patch.setdefault("housing_allowance_enabled", True)
        patch.setdefault("transport_allowance_enabled", True)
        if grade_step and grade_step[0] in ("GR1", "GR2", "GR3", "GR4"):
            patch["responsibility_allowance_enabled"] = True
        if patch:
            await db.employees.update_one({"id": e["id"]}, {"$set": patch})
            updated += 1
    logger.info("Upgraded %d Gov employees with civil-service profile (company %s)", updated, company_id)
