"""Test-account seeding: 70 accounts (10 per role) — callable from CLI or the
superadmin API endpoint. Idempotent; re-running resets passwords/roles.
CLI: cd /app/backend && python seed_test_accounts.py
"""
import asyncio
import uuid

from dotenv import load_dotenv
load_dotenv()

from core import db, hash_password, now_utc, iso  # noqa: E402

ROLES = [
    ("superadmin", "superadmin", "Test@SuperAdmin", "Super Admin"),
    ("hradmin",    "hr",         "Test@HRAdmin",    "HR Admin"),
    ("payroll",    "payroll",    "Test@Payroll",    "Payroll Officer"),
    ("manager",    "manager",    "Test@Manager",    "Manager"),
    ("employee",   "employee",   "Test@Employee",   "Employee"),
    ("auditor",    "auditor",    "Test@Auditor",    "Auditor"),
    ("admin",      "admin",      "Test@Admin",      "Admin"),
]


async def seed_accounts(company_id: str | None = None) -> dict:
    """Create/refresh all 70 test accounts on the given tenant (defaults to
    Demo Salone Ltd., falling back to any company). employee1..10 and
    manager1..10 get linked to real employee records so own-payslip and
    self-service flows work."""
    if not company_id:
        company = (await db.companies.find_one({"name": "Demo Salone Ltd."}, {"_id": 0, "id": 1})
                   or await db.companies.find_one({}, {"_id": 0, "id": 1}))
        if not company:
            return {"ok": False, "error": "No company/tenant exists to attach accounts to"}
        company_id = company["id"]
    emp_pool = [e["id"] for e in await db.employees.find(
        {"company_id": company_id, "status": "active"}, {"_id": 0, "id": 1}).to_list(50)]
    created = updated = 0
    for prefix, role, pw_prefix, label in ROLES:
        for n in range(1, 11):
            email = f"{prefix}{n}@salonehcm.com"
            pw_hash = await asyncio.to_thread(hash_password, f"{pw_prefix}{n}")
            employee_id = None
            if prefix in ("employee", "manager") and emp_pool:
                employee_id = emp_pool[(n - 1) % len(emp_pool)]
            doc = {
                "email": email,
                "name": f"{label} {n}",
                "role": role,
                "company_id": company_id,
                "employee_id": employee_id,
                "password_hash": pw_hash,
                "test_account": True,
                "created_by": "seed_test_accounts",
            }
            if prefix == "auditor":
                doc["auditor"] = True
            existing = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
            if existing:
                await db.users.update_one({"email": email}, {"$set": doc})
                updated += 1
            else:
                await db.users.insert_one({"id": str(uuid.uuid4()),
                                           "created_at": iso(now_utc()), **doc})
                created += 1
    return {"ok": True, "created": created, "updated": updated, "company_id": company_id}


if __name__ == "__main__":
    print(asyncio.run(seed_accounts()))
