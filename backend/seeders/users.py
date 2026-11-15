"""Admin user seeding."""
import os
import uuid
from core import db, hash_password, verify_password, now_utc, iso, logger

# Deterministic TOTP seed for the platform superadmin (read from env so secret
# is configurable without code changes). The default is a known dev-only value
# used by the in-repo test suite; production deployments MUST override it via
# the SUPERADMIN_TOTP_SECRET environment variable.
SUPERADMIN_TOTP_SECRET = os.environ.get(
    "SUPERADMIN_TOTP_SECRET",
    "KRSXG5BANFXSAYTBORQXG43LMR2A",
)


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
            "twofa_enabled": True,
            "twofa_secret": SUPERADMIN_TOTP_SECRET,
            "twofa_enabled_at": iso(now_utc()),
            "created_at": iso(now_utc()),
        })
        logger.info("Seeded superadmin (2FA enabled): %s", admin_email)
        return
    # Make sure password matches current env and company_id is set
    updates = {}
    if not verify_password(admin_password, existing["password_hash"]):
        updates["password_hash"] = hash_password(admin_password)
    if not existing.get("company_id"):
        updates["company_id"] = company_id
    if existing.get("role") != "superadmin":
        updates["role"] = "superadmin"
    # Ensure 2FA stays enabled on the seed superadmin with the deterministic secret
    if not existing.get("twofa_enabled") or existing.get("twofa_secret") != SUPERADMIN_TOTP_SECRET:
        updates["twofa_enabled"] = True
        updates["twofa_secret"] = SUPERADMIN_TOTP_SECRET
        if not existing.get("twofa_enabled_at"):
            updates["twofa_enabled_at"] = iso(now_utc())
    if updates:
        await db.users.update_one({"email": admin_email}, {"$set": updates})
