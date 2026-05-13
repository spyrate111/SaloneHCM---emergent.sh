"""Web Push / VAPID — encrypt + dispatch browser notifications to subscribed clients."""
import asyncio
import json
import logging
import os
from typing import Optional

from pywebpush import webpush, WebPushException

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.push")

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_CONTACT = os.environ.get("VAPID_CONTACT", "mailto:admin@salonehcm.sl")


def is_configured() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def public_key() -> Optional[str]:
    return VAPID_PUBLIC_KEY


def _vapid_claims():
    return {"sub": VAPID_CONTACT}


def _send_sync(subscription: dict, payload: dict) -> dict:
    webpush(
        subscription_info=subscription,
        data=json.dumps(payload),
        vapid_private_key=VAPID_PRIVATE_KEY,
        vapid_claims=_vapid_claims(),
    )
    return {"ok": True}


async def _send_one(sub_doc: dict, payload: dict) -> dict:
    sub = {
        "endpoint": sub_doc["endpoint"],
        "keys": sub_doc["keys"],
    }
    try:
        await asyncio.to_thread(_send_sync, sub, payload)
        return {"ok": True}
    except WebPushException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        # 404/410 = expired or unregistered — drop the subscription
        if status in (404, 410):
            try:
                await db.push_subscriptions.delete_one({"id": sub_doc.get("id")})
            except Exception:
                pass
            return {"ok": False, "error": f"expired_{status}", "dropped": True}
        return {"ok": False, "error": str(e)[:200], "status": status}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def fanout_to_user(user_id: str, payload: dict) -> dict:
    """Dispatch a push to every subscription belonging to a user."""
    if not is_configured():
        return {"sent": 0, "failed": 0, "skipped": "vapid_not_configured"}
    subs = await db.push_subscriptions.find({"user_id": user_id}, {"_id": 0}).to_list(50)
    if not subs:
        return {"sent": 0, "failed": 0, "skipped": "no_subscriptions"}
    results = await asyncio.gather(*[_send_one(s, payload) for s in subs])
    sent = sum(1 for r in results if r.get("ok"))
    failed = len(results) - sent
    try:
        await db.push_logs.insert_one({
            "user_id": user_id,
            "payload": payload,
            "sent": sent,
            "failed": failed,
            "ts": iso(now_utc()),
        })
    except Exception:
        pass
    return {"sent": sent, "failed": failed}


async def fanout_to_employee(employee_id: str, payload: dict) -> dict:
    """Translate employee_id → user_id then fanout."""
    user = await db.users.find_one({"employee_id": employee_id}, {"_id": 0, "id": 1})
    if not user:
        return {"sent": 0, "failed": 0, "skipped": "no_user_for_employee"}
    return await fanout_to_user(user["id"], payload)
