"""Admin user seeding."""
import os
import uuid
from core import db, hash_password, verify_password, now_utc, iso, logger


async def seed_admin(company_id: str) -> None:
    admin_email = os.environ["ADMIN_EMAIL"].lower()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "System Administrator",
            "role": "superadmin",
            "company_id": company_id,
            "password_hash": hash_password(admin_password),
            "created_at": iso(now_utc()),
        })
        logger.info("Seeded superadmin: %s", admin_email)
        return
    # Make sure password matches current env and company_id is set
    updates = {}
    if not verify_password(admin_password, existing["password_hash"]):
        updates["password_hash"] = hash_password(admin_password)
    if not existing.get("company_id"):
        updates["company_id"] = company_id
    # Auto-promote seed admin to superadmin (idempotent)
    if existing.get("role") != "superadmin":
        updates["role"] = "superadmin"
    if updates:
        await db.users.update_one({"email": admin_email}, {"$set": updates})
