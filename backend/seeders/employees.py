"""Employee records, accounts, and reporting hierarchy."""
import uuid
from core import db, hash_password, now_utc, iso, logger

SEED_EMPLOYEES = [
    ("Aminata", "Kamara", "Senior HR Manager", "Human Resources", 8500, 1200, True),
    ("Mohamed", "Sesay", "Software Engineer", "Engineering", 6200, 800, False),
    ("Fatmata", "Bangura", "Accountant", "Finance", 4800, 600, False),
    ("Ibrahim", "Conteh", "Operations Lead", "Operations", 5500, 700, True),
    ("Hawa", "Turay", "Marketing Specialist", "Marketing", 3800, 500, False),
    ("Abdul", "Jalloh", "Sales Executive", "Sales", 3200, 1000, False),
    ("Isatu", "Mansaray", "Customer Support", "Support", 2400, 300, False),
    ("Sahr", "Koroma", "DevOps Engineer", "Engineering", 7200, 900, True),
    ("Mariama", "Fofanah", "Junior Accountant", "Finance", 2800, 400, False),
    ("Alhaji", "Bah", "Office Administrator", "Operations", 2100, 250, False),
]


async def seed(company_id: str) -> None:
    if await db.employees.count_documents({"company_id": company_id}) > 0:
        return
    for fn, ln, title, dept, basic, allow, is_mgr in SEED_EMPLOYEES:
        eid = str(uuid.uuid4())
        email = f"{fn.lower()}.{ln.lower()}@salonehcm.sl"
        await db.employees.insert_one({
            "id": eid,
            "company_id": company_id,
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
            "is_manager": is_mgr,
            "manager_id": None,
            "created_at": iso(now_utc()),
        })
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": email,
            "name": f"{fn} {ln}",
            "role": "employee",
            "company_id": company_id,
            "employee_id": eid,
            "password_hash": hash_password("Employee@2026"),
            "created_at": iso(now_utc()),
        })
    # Wire reporting lines: managers within each department
    all_emps = await db.employees.find({"company_id": company_id}, {"_id": 0}).to_list(500)
    managers = {e["department"]: e["id"] for e in all_emps if e.get("is_manager")}
    for e in all_emps:
        if e.get("is_manager"):
            continue
        mgr_id = managers.get(e["department"])
        if mgr_id:
            await db.employees.update_one({"id": e["id"]}, {"$set": {"manager_id": mgr_id}})
    logger.info("Seeded %d employees in company %s", len(SEED_EMPLOYEES), company_id)


async def backfill_bank_and_managers() -> None:
    # Backfill bank fields
    async for e in db.employees.find({"bank_account": {"$in": [None, ""]}}):
        eid = e["id"]
        await db.employees.update_one(
            {"id": eid},
            {"$set": {
                "bank_name": e.get("bank_name") or "Sierra Leone Commercial Bank",
                "bank_account": f"00{eid.replace('-', '')[:10]}",
            }},
        )

    # Backfill is_manager + manager_id on docs that pre-date the field
    if await db.employees.count_documents({"is_manager": {"$exists": True}}) == 0:
        all_emps = await db.employees.find({}, {"_id": 0}).to_list(500)
        by_dept = {}
        for e in all_emps:
            d = e["department"]
            if d not in by_dept or e.get("basic_salary_sle", 0) > by_dept[d].get("basic_salary_sle", 0):
                by_dept[d] = e
        for e in all_emps:
            is_mgr = by_dept.get(e["department"], {}).get("id") == e["id"]
            mgr_id = None if is_mgr else by_dept.get(e["department"], {}).get("id")
            await db.employees.update_one(
                {"id": e["id"]},
                {"$set": {"is_manager": is_mgr, "manager_id": mgr_id}},
            )
        logger.info("Backfilled manager hierarchy across %d employees", len(all_emps))
