"""Test-account seeding: 70 accounts (10 per role) — callable from CLI or the
superadmin API endpoint. Idempotent; re-running resets passwords/roles.
CLI: cd /app/backend && python seed_test_accounts.py
"""
import asyncio
import os
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
    """Create/refresh test accounts only when explicitly enabled and tenant-scoped."""
    enabled = os.environ.get("ENABLE_TEST_ACCOUNT_MANAGEMENT", "").strip().lower()
    if enabled not in {"1", "true", "yes"}:
        return {"ok": False, "error": "Test-account management is disabled"}
    if not company_id:
        return {"ok": False, "error": "A company_id is required; no default tenant is used"}
    # Preflight every fixed test email before changing any account. Never take over
    # a real user or move a seeded account from another tenant.
    existing_by_email = {}
    for prefix, _role, _pw_prefix, _label in ROLES:
        for n in range(1, 11):
            email = f"{prefix}{n}@salonehcm.com"
            existing = await db.users.find_one(
                {"email": email},
                {"_id": 0, "id": 1, "test_account": 1, "company_id": 1},
            )
            if existing and (
                existing.get("test_account") is not True
                or existing.get("company_id") != company_id
            ):
                return {"ok": False, "error": f"Refusing to overwrite non-test or cross-tenant account: {email}"}
            existing_by_email[email] = existing

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
            existing = existing_by_email[email]
            if existing:
                result = await db.users.update_one(
                    {
                        "id": existing["id"],
                        "company_id": company_id,
                        "test_account": True,
                    },
                    {"$set": doc},
                )
                if not result.matched_count:
                    return {"ok": False, "error": f"Test account changed during seeding: {email}"}
                updated += 1
            else:
                await db.users.insert_one({"id": str(uuid.uuid4()),
                                           "created_at": iso(now_utc()), **doc})
                created += 1
    return {"ok": True, "created": created, "updated": updated, "company_id": company_id}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python seed_test_accounts.py <company_id>")
    print(asyncio.run(seed_accounts(sys.argv[1])))
