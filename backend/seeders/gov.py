"""Gov of Sierra Leone seed — sample ministerial employees so SMS flow is testable."""
import uuid
from core import db, hash_password, now_utc, iso, logger

# 6 representative civil servants. Phone numbers use Sierra Leone +232 76 prefix.
GOV_EMPLOYEES = [
    ("Adama", "Sankoh", "Permanent Secretary", "Ministry of Finance", 12000, 2000, True, "+23276111001"),
    ("Foday", "Massaquoi", "Director General", "Ministry of Labour", 11000, 1800, True, "+23276111002"),
    ("Sia", "Kallon", "Senior Officer", "Ministry of Finance", 6500, 800, False, "+23276111003"),
    ("Kabba", "Lansana", "Accountant", "NRA", 5500, 700, False, "+23276111004"),
    ("Memuna", "Tucker", "Payroll Analyst", "NASSIT", 5000, 600, False, "+23276111005"),
    ("Joseph", "Williams", "IT Support", "Ministry of Health", 3500, 400, False, ""),  # missing phone — tests skip
]


async def seed(company_id: str) -> None:
    if await db.employees.count_documents({"company_id": company_id}) > 0:
        return
    for fn, ln, title, dept, basic, allow, is_mgr, phone in GOV_EMPLOYEES:
        eid = str(uuid.uuid4())
        email = f"{fn.lower()}.{ln.lower()}@gov.sl"
        await db.employees.insert_one({
            "id": eid,
            "company_id": company_id,
            "first_name": fn,
            "last_name": ln,
            "email": email,
            "phone": phone,
            "job_title": title,
            "department": dept,
            "location": "Freetown",
            "employment_type": "Full-time",
            "basic_salary_sle": basic,
            "allowances_sle": allow,
            "nassit_no": f"NSGOV-{eid[:8].upper()}",
            "tin": f"TIN-GOV-{eid[:6].upper()}",
            "bank_name": "Bank of Sierra Leone",
            "bank_account": f"GOV{eid[:10].replace('-', '')[:10]}",
            "hire_date": "2023-01-01",
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

    # Wire reporting lines by department
    all_emps = await db.employees.find({"company_id": company_id}, {"_id": 0}).to_list(500)
    managers = {e["department"]: e["id"] for e in all_emps if e.get("is_manager")}
    for e in all_emps:
        if e.get("is_manager"):
            continue
        mgr_id = managers.get(e["department"])
        if mgr_id:
            await db.employees.update_one({"id": e["id"]}, {"$set": {"manager_id": mgr_id}})
    logger.info("Seeded %d Gov employees in company %s", len(GOV_EMPLOYEES), company_id)


async def seed_gov_admin(company_id: str) -> None:
    """Plant a dedicated Gov tenant admin so super-admin isn't the only entry."""
    email = "admin@gov.sl"
    existing = await db.users.find_one({"email": email})
    if existing:
        # Ensure mof_approver flag exists on the seed gov admin
        if not existing.get("mof_approver"):
            await db.users.update_one({"email": email}, {"$set": {"mof_approver": True}})
        return
    await db.users.insert_one({
        "id": str(uuid.uuid4()),
        "email": email,
        "name": "Gov Administrator",
        "role": "admin",
        "company_id": company_id,
        "password_hash": hash_password("GovAdmin@2026"),
        "mof_approver": True,
        "created_at": iso(now_utc()),
    })
    logger.info("Seeded Gov admin: %s", email)
