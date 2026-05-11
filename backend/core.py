"""Shared core: db, auth, audit, time helpers."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import HTTPException, Depends, Request
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("salonehcm")

# ---- DB ----
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

# ---- JWT ----
JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def make_access(uid: str, email: str, role: str) -> str:
    payload = {
        "sub": uid,
        "email": email,
        "role": role,
        "type": "access",
        "exp": now_utc() + timedelta(hours=12),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        ah = request.headers.get("Authorization", "")
        if ah.startswith("Bearer "):
            token = ah[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "User not found")
    if not user.get("company_id"):
        raise HTTPException(401, "User has no company assigned")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return user


def tenant_filter(user: dict) -> dict:
    """Return a Mongo filter clause that scopes a query to the user's company."""
    return {"company_id": user["company_id"]}


def with_tenant(doc: dict, user: dict) -> dict:
    """Stamp company_id onto a doc before insert."""
    doc["company_id"] = user["company_id"]
    return doc


async def get_company(user: dict) -> dict:
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    if not company:
        raise HTTPException(404, "Company not found")
    return company


def require_feature(feature: str):
    """FastAPI dependency that 402s if the user's company tier doesn't include `feature`."""
    async def _dep(user: dict = Depends(get_current_user)) -> dict:
        company = await get_company(user)
        if feature not in (company.get("features") or []):
            raise HTTPException(
                402,
                f"Feature '{feature}' is not available on the {company.get('tier', 'lite')} tier. "
                f"Upgrade your plan in Settings → Organization.",
            )
        return user
    return _dep


async def audit(action: str, resource: str, user: dict, meta: Optional[dict] = None):
    """Fire-and-forget audit log entry. Never raises to caller."""
    try:
        await db.audit_logs.insert_one({
            "id": str(uuid.uuid4()),
            "company_id": user.get("company_id"),
            "action": action,
            "resource": resource,
            "user_id": user.get("id"),
            "user_email": user.get("email"),
            "user_role": user.get("role"),
            "meta": meta or {},
            "ts": iso(now_utc()),
        })
    except Exception as e:
        logger.warning("audit insert failed: %s", e)


# ---- Rate limiter (shared singleton across routers) ----
from slowapi import Limiter
from slowapi.util import get_remote_address


def _client_ip(request) -> str:
    """Prefer X-Forwarded-For first hop (for k8s ingress / proxy setups), else peer addr."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip, default_limits=[])
