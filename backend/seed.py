"""Startup seeding: admin user + 10 demo employees + bank backfill."""
import os
import uuid

from core import db, hash_password, verify_password, now_utc, iso, logger

SEED_EMPLOYEES = [
    ("Aminata", "Kamara", "Senior HR Manager", "Human Resources", 8500, 1200),
    ("Mohamed", "Sesay", "Software Engineer", "Engineering", 6200, 800),
    ("Fatmata", "Bangura", "Accountant", "Finance", 4800, 600),
    ("Ibrahim", "Conteh", "Operations Lead", "Operations", 5500, 700),
    ("Hawa", "Turay", "Marketing Specialist", "Marketing", 3800, 500),
    ("Abdul", "Jalloh", "Sales Executive", "Sales", 3200, 1000),
    ("Isatu", "Mansaray", "Customer Support", "Support", 2400, 300),
    ("Sahr", "Koroma", "DevOps Engineer", "Engineering", 7200, 900),
    ("Mariama", "Fofanah", "Junior Accountant", "Finance", 2800, 400),
    ("Alhaji", "Bah", "Office Administrator", "Operations", 2100, 250),
]


async def seed():
    await db.users.create_index("email", unique=True)
    await db.employees.create_index("email", unique=True)

    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "System Administrator",
            "role": "admin",
            "password_hash": hash_password(admin_password),
            "created_at": iso(now_utc()),
        })
        logger.info("Seeded admin: %s", admin_email)
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )

    if await db.employees.count_documents({}) == 0:
        for fn, ln, title, dept, basic, allow in SEED_EMPLOYEES:
            eid = str(uuid.uuid4())
            email = f"{fn.lower()}.{ln.lower()}@salonehcm.sl"
            await db.employees.insert_one({
                "id": eid,
                "first_name": fn,
                "last_name": ln,
                "email": email,
                "phone": "+232 76 000 000",
                "job_title": title,
                "department": dept,
                "location": "Freetown",
                "employment_type": "Full-time",
                "basic_salary_sle": basic,
                "allowances_sle": allow,
                "nassit_no": f"NS{eid[:8].upper()}",
                "tin": f"TIN{eid[:6].upper()}",
                "bank_name": "Sierra Leone Commercial Bank",
                "bank_account": f"00{eid[:10].replace('-', '')[:10]}",
                "hire_date": "2024-01-15",
                "status": "active",
                "created_at": iso(now_utc()),
            })
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "name": f"{fn} {ln}",
                "role": "employee",
                "employee_id": eid,
                "password_hash": hash_password("Employee@2026"),
                "created_at": iso(now_utc()),
            })
        logger.info("Seeded employees and employee accounts")

    # Backfill bank fields for any employee missing them
    async for e in db.employees.find({"bank_account": {"$in": [None, ""]}}):
        eid = e["id"]
        await db.employees.update_one(
            {"id": eid},
            {"$set": {
                "bank_name": e.get("bank_name") or "Sierra Leone Commercial Bank",
                "bank_account": f"00{eid.replace('-', '')[:10]}",
            }},
        )

    # Seed benefit plans
    if await db.benefit_plans.count_documents({}) == 0:
        for name, t, cost, share, desc in [
            ("Premium Health Cover", "health", 350, 70, "Comprehensive medical for employee + family"),
            ("Standard Health Cover", "health", 180, 50, "Basic medical, outpatient + emergency"),
            ("Group Life Insurance", "life", 80, 100, "2× annual salary cover, employer-paid"),
            ("Dental Plan", "dental", 60, 50, "Routine + major dental"),
            ("Pension Top-up", "pension", 200, 50, "Voluntary top-up beyond NASSIT"),
            ("Transport Allowance", "transport", 250, 100, "Monthly fuel/transit stipend"),
        ]:
            await db.benefit_plans.insert_one({
                "id": str(uuid.uuid4()), "name": name, "type": t,
                "monthly_cost_sle": cost, "employer_share_pct": share,
                "description": desc, "created_at": iso(now_utc()),
            })
        logger.info("Seeded benefit plans")

    # Seed job postings
    if await db.job_postings.count_documents({}) == 0:
        for title, dept, mn, mx in [
            ("Senior React Engineer", "Engineering", 5500, 8500),
            ("Payroll Analyst", "Finance", 3500, 5500),
            ("Customer Success Manager", "Support", 3000, 5000),
        ]:
            await db.job_postings.insert_one({
                "id": str(uuid.uuid4()), "title": title, "department": dept,
                "location": "Freetown", "employment_type": "Full-time",
                "salary_min_sle": mn, "salary_max_sle": mx,
                "description": f"Looking for an experienced {title} in our {dept} team.",
                "status": "open", "created_at": iso(now_utc()),
            })

    # Seed training programs
    if await db.training_programs.count_documents({}) == 0:
        for title, prov, hrs, skill in [
            ("Sierra Leone Tax Compliance 2026", "NRA Academy", 16, "Compliance"),
            ("Advanced Excel for Payroll", "Internal", 12, "Tools"),
            ("Leadership Fundamentals", "African Mgmt Inst.", 24, "Leadership"),
            ("Cybersecurity Awareness", "Internal", 4, "Security"),
        ]:
            await db.training_programs.insert_one({
                "id": str(uuid.uuid4()), "title": title, "provider": prov,
                "hours": hrs, "skill_area": skill, "description": "",
                "created_at": iso(now_utc()),
            })
