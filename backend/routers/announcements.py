"""Company announcements / notice board — HR/admin post, all staff see, push on publish."""
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from core import (db, get_current_user, require_roles, can_role, audit,
                  tenant_filter, with_tenant, now_utc, iso)
import push_service

router = APIRouter(prefix="/announcements", tags=["announcements"])

PRIORITIES = {"normal", "urgent"}


class AnnouncementIn(BaseModel):
    title: str
    body: str
    priority: str = "normal"
    expires_at: Optional[str] = None  # YYYY-MM-DD, inclusive


def _is_expired(row: dict, today: str) -> bool:
    return bool(row.get("expires_at")) and row["expires_at"] < today


@router.post("")
async def create_announcement(body: AnnouncementIn, bg: BackgroundTasks,
                              user: dict = Depends(require_roles("hr"))):
    title = body.title.strip()
    text = body.body.strip()
    if not title or not text:
        raise HTTPException(422, "Title and body are required")
    if body.priority not in PRIORITIES:
        raise HTTPException(422, "Priority must be 'normal' or 'urgent'")
    expires = (body.expires_at or "").strip() or None
    if expires:
        if len(expires) != 10 or expires[4] != "-" or expires[7] != "-":
            raise HTTPException(422, "Expiry date must be YYYY-MM-DD")
        if expires < iso(now_utc())[:10]:
            raise HTTPException(422, "Expiry date cannot be in the past")

    aid = str(uuid.uuid4())
    doc = with_tenant({
        "id": aid,
        "title": title[:150],
        "body": text[:3000],
        "priority": body.priority,
        "expires_at": expires,
        "posted_by": user.get("name") or user["email"],
        "created_at": iso(now_utc()),
    }, user)
    await db.announcements.insert_one(doc)
    doc.pop("_id", None)
    await audit("announcement_posted", f"announcements/{aid}", user,
                {"title": doc["title"], "priority": doc["priority"]})
    bg.add_task(push_service.fanout_to_company, user["company_id"], {
        "title": "Urgent announcement" if doc["priority"] == "urgent" else "New announcement",
        "body": doc["title"],
        "url": "/dashboard",
        "kind": "announcement",
    })
    doc["expired"] = False
    return doc


@router.get("")
async def list_announcements(include_expired: bool = False,
                             user: dict = Depends(get_current_user)):
    """Active announcements for everyone; archive (expired) only for HR/admin/auditor."""
    today = iso(now_utc())[:10]
    rows = await db.announcements.find(
        tenant_filter(user), {"_id": 0}).sort("created_at", -1).to_list(500)
    for r in rows:
        r["expired"] = _is_expired(r, today)
    if can_role(user, "hr", "auditor"):
        total_staff = await db.users.count_documents(
            {**tenant_filter(user), "disabled": {"$ne": True}})
        counts = {}
        async for g in db.announcement_reads.aggregate([
                {"$match": tenant_filter(user)},
                {"$group": {"_id": "$announcement_id", "n": {"$sum": 1}}}]):
            counts[g["_id"]] = g["n"]
        for r in rows:
            r["read_count"] = counts.get(r["id"], 0)
            r["total_staff"] = total_staff
        if include_expired:
            return rows
    return [r for r in rows if not r["expired"]]


class SeenIn(BaseModel):
    ids: list[str]


@router.post("/mark-seen")
async def mark_seen(body: SeenIn, user: dict = Depends(get_current_user)):
    """Called when a user's dashboard renders announcements — records read receipts."""
    valid = await db.announcements.find(
        {"id": {"$in": body.ids[:100]}, **tenant_filter(user)}, {"_id": 0, "id": 1}).to_list(100)
    now = iso(now_utc())
    for v in valid:
        await db.announcement_reads.update_one(
            {"announcement_id": v["id"], "user_id": user["id"]},
            {"$setOnInsert": {
                "announcement_id": v["id"],
                "user_id": user["id"],
                "user_name": user.get("name") or user["email"],
                "role": user.get("role"),
                "company_id": user["company_id"],
                "seen_at": now,
            }},
            upsert=True)
    return {"ok": True, "marked": len(valid)}


@router.get("/{aid}/unread")
async def unread_staff(aid: str, user: dict = Depends(require_roles("hr", "auditor"))):
    """Staff who have NOT yet seen an announcement — follow-up list for urgent notices."""
    ann = await db.announcements.find_one({"id": aid, **tenant_filter(user)}, {"_id": 0, "id": 1})
    if not ann:
        raise HTTPException(404, "Announcement not found")
    seen = {r["user_id"] async for r in db.announcement_reads.find(
        {"announcement_id": aid, **tenant_filter(user)}, {"_id": 0, "user_id": 1})}
    users = await db.users.find(
        {**tenant_filter(user), "disabled": {"$ne": True}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1}).to_list(2000)
    return [u for u in users if u["id"] not in seen]


@router.delete("/{aid}")
async def delete_announcement(aid: str, user: dict = Depends(require_roles("hr"))):
    row = await db.announcements.find_one({"id": aid, **tenant_filter(user)}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Announcement not found")
    await db.announcements.delete_one({"id": aid, **tenant_filter(user)})
    await db.announcement_reads.delete_many({"announcement_id": aid})
    await audit("announcement_deleted", f"announcements/{aid}", user, {"title": row["title"]})
    return {"ok": True}
