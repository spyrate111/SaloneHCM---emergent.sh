"""One-off idempotent seeder: 70 test accounts (10 per role) on Demo Salone Ltd.
Run: cd /app/backend && python seed_test_accounts.py
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


async def main():
    company = await db.companies.find_one({"name": "Demo Salone Ltd."}, {"_id": 0, "id": 1})
    assert company, "Demo Salone Ltd. tenant not found"
    cid = company["id"]
    created = updated = 0
    for prefix, role, pw_prefix, label in ROLES:
        for n in range(1, 11):
            email = f"{prefix}{n}@salonehcm.com"
            doc = {
                "email": email,
                "name": f"{label} {n}",
                "role": role,
                "company_id": cid,
                "employee_id": None,
                "password_hash": hash_password(f"{pw_prefix}{n}"),
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
    print(f"done — created={created} updated={updated} tenant={cid}")


if __name__ == "__main__":
    asyncio.run(main())
