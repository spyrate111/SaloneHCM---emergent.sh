"""Seed the 7 produced training videos (manifest.json → marketing_videos)."""
import json
import uuid
from pathlib import Path

from core import db, iso, now_utc, logger

MANIFEST = Path("/app/backend/static/training/manifest.json")


async def seed_training_videos() -> None:
    if not MANIFEST.exists():
        return
    manifest = json.loads(MANIFEST.read_text())
    n = 0
    for entry in manifest.values():
        existing = await db.marketing_videos.find_one({"title": entry["title"]}, {"_id": 1})
        doc = {
            "title": entry["title"], "summary": entry["summary"],
            "src": entry["src"], "poster": entry["poster"],
            "duration_s": entry["duration_s"], "category": "training",
            "persona": entry["persona"], "sort": entry["sort"],
            "chapters": entry["chapters"], "published": True,
            "slug": entry["slug"], "lang": entry.get("lang", "en"),
            "base_slug": entry.get("base_slug", entry["slug"]),
            "updated_at": iso(now_utc()),
        }
        if existing:
            await db.marketing_videos.update_one({"_id": existing["_id"]}, {"$set": doc})
        else:
            doc["id"] = str(uuid.uuid4())
            doc["created_at"] = doc["updated_at"]
            await db.marketing_videos.insert_one(doc)
            n += 1
    if n:
        logger.info("Training videos seeded: %d", n)
