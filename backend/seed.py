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
