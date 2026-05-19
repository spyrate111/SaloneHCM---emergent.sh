"""Web push subscription management + admin tools for VAPID-based notifications."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core import db, get_current_user, audit, now_utc, iso, with_tenant
import push_service

router = APIRouter(prefix="/push", tags=["push"])


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubIn(BaseModel):
    endpoint: str
    keys: PushKeys
    user_agent: Optional[str] = None


@router.get("/public-key")
async def public_key(_: dict = Depends(get_current_user)):
    return {
        "vapid_public_key": push_service.public_key(),
        "configured": push_service.is_configured(),
    }


@router.post("/subscribe")
async def subscribe(body: PushSubIn, user: dict = Depends(get_current_user)):
    # Replace existing subscription with same endpoint (browser may re-register)
    await db.push_subscriptions.delete_many({"endpoint": body.endpoint})
    sid = str(uuid.uuid4())
    doc = with_tenant({
        "id": sid,
        "user_id": user["id"],
        "employee_id": user.get("employee_id"),
        "endpoint": body.endpoint,
        "keys": body.keys.model_dump(),
        "user_agent": (body.user_agent or "")[:200],
        "created_at": iso(now_utc()),
    }, user)
    await db.push_subscriptions.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "subscription_id": sid}


@router.post("/unsubscribe")
async def unsubscribe(body: PushSubIn, user: dict = Depends(get_current_user)):
    res = await db.push_subscriptions.delete_many({"endpoint": body.endpoint, "user_id": user["id"]})
    return {"ok": True, "deleted": res.deleted_count}


@router.get("/status")
async def status(user: dict = Depends(get_current_user)):
    count = await db.push_subscriptions.count_documents({"user_id": user["id"]})
    return {
        "configured": push_service.is_configured(),
        "subscription_count": count,
    }


class TestPushIn(BaseModel):
    title: Optional[str] = "SaloneHCM"
    body: Optional[str] = "This is a test notification."
    url: Optional[str] = "/dashboard"


@router.post("/test")
async def send_test(body: TestPushIn, user: dict = Depends(get_current_user)):
    payload = {"title": body.title, "body": body.body, "url": body.url, "kind": "test"}
    res = await push_service.fanout_to_user(user["id"], payload)
    await audit("push_test", f"users/{user['id']}", user, res)
    return res
