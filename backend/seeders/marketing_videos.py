"""Seed the marketing video library on first boot.
PLACEHOLDER VIDEOS — hotlink-safe W3C sample MP4s used as demo content.
Replace src/poster URLs with real SaloneHCM screen recordings once produced.
Super-admin can manage the library at POST/PATCH/DELETE /api/marketing/admin/videos.
"""
import uuid
from core import db, now_utc, iso, logger

# Picsum.photos provides hotlink-friendly seeded placeholder images.
# Replace the `poster` URL on any video with your real screenshot via the
# super-admin endpoint (POST/PATCH /api/marketing/admin/videos) once recorded.
P = "https://picsum.photos/seed/{}/720/405"
# W3C hosts these public-domain sample MP4s permanently — verified 200 OK,
# CORS-open, and hotlink-friendly for HTML5 <video> playback.
W3 = "https://media.w3.org/2010/05"

SEED_VIDEOS = [
    # ---- Getting started (Small Business persona) ----
    {
        "title": "First payroll run in under 2 hours",
        "summary": "Follow Aminata as she sets up Freetown Logistics Ltd and pays 18 employees end-to-end — from importing the spreadsheet to filing PAYE.",
        "src": f"{W3}/bunny/trailer.mp4",
        "poster": P.format("salonehcm-payroll-1"),
        "duration_s": 32,
        "category": "getting_started",
        "persona": "small_business",
        "sort": 10,
        "chapters": [
            {"t": 0,  "label": "Import your team"},
            {"t": 8,  "label": "Set NRA PAYE bands"},
            {"t": 18, "label": "Run & approve"},
            {"t": 26, "label": "File the return"},
        ],
    },
    {
        "title": "Onboarding your first 10 employees",
        "summary": "How to get a small team from spreadsheet to self-service in a single afternoon — bank details, NASSIT numbers, emergency contacts, and the welcome SMS.",
        "src": f"{W3}/video/movie_300.mp4",
        "poster": P.format("salonehcm-onboard-2"),
        "duration_s": 30,
        "category": "getting_started",
        "persona": "small_business",
        "sort": 20,
        "chapters": [{"t": 0, "label": "Bulk upload"}, {"t": 12, "label": "Welcome SMS"}, {"t": 22, "label": "Self-service activation"}],
    },
    {
        "title": "Filing your NRA PAYE return — a 90-second walkthrough",
        "summary": "Where to find the export, what to double-check, and how SaloneHCM matches NRA's expected format down to the last column.",
        "src": f"{W3}/sintel/trailer.mp4",
        "poster": P.format("salonehcm-paye-3"),
        "duration_s": 52,
        "category": "getting_started",
        "persona": "small_business",
        "sort": 30,
        "chapters": [{"t": 0, "label": "Pick the period"}, {"t": 18, "label": "Generate the export"}, {"t": 38, "label": "Submit to NRA portal"}],
    },

    # ---- By persona / industry ----
    {
        "title": "Government & MDAs: civil service payroll walkthrough",
        "summary": "Grade & step structure, budget-code roll-ups, MoF two-step approval and the auditor-general report PDF — all in one continuous flow.",
        "src": f"{W3}/bunny/movie.mp4",
        "poster": P.format("salonehcm-gov-4"),
        "duration_s": 596,
        "category": "by_persona",
        "persona": "government",
        "sort": 10,
        "chapters": [
            {"t": 0,   "label": "Grade & step structure"},
            {"t": 120, "label": "Budget code roll-up"},
            {"t": 300, "label": "MoF approval workflow"},
            {"t": 480, "label": "Audit PDF export"},
        ],
    },
    {
        "title": "NGO sector allowances done right",
        "summary": "Per-diem, field, hardship and family-separation allowances applied to one employee or a whole project team in a single click.",
        "src": f"{W3}/bunny/trailer.mp4",
        "poster": P.format("salonehcm-ngo-5"),
        "duration_s": 32,
        "category": "by_persona",
        "persona": "ngo",
        "sort": 20,
        "chapters": [{"t": 0, "label": "Pick the NGO preset"}, {"t": 12, "label": "Apply to project team"}, {"t": 24, "label": "Auto-detect duty stations"}],
    },
    {
        "title": "Mining sector: hazard, remote-site & fuel allowances",
        "summary": "How a mining operation in Kono runs payroll with shift differentials, hazard pay and on-site fuel benefits — and keeps NRA happy.",
        "src": f"{W3}/video/movie_300.mp4",
        "poster": P.format("salonehcm-mining-6"),
        "duration_s": 30,
        "category": "by_persona",
        "persona": "mining",
        "sort": 30,
        "chapters": [{"t": 0, "label": "Shift configuration"}, {"t": 12, "label": "Hazard band applied"}, {"t": 22, "label": "Tax-exempt fuel handling"}],
    },

    # ---- Deep dives ----
    {
        "title": "Bulk payslip SMS via Twilio +232",
        "summary": "How to send every employee their net-pay SMS in one click — with delivery tracking, retry on failure, and a complete audit log.",
        "src": f"{W3}/sintel/trailer.mp4",
        "poster": P.format("salonehcm-sms-7"),
        "duration_s": 52,
        "category": "deep_dive",
        "persona": "general",
        "sort": 10,
        "chapters": [{"t": 0, "label": "Connect Twilio"}, {"t": 18, "label": "Run the batch"}, {"t": 38, "label": "Inspect delivery logs"}],
    },
    {
        "title": "IFMIS bank file disbursement",
        "summary": "Generate Rokel / SLCB / UBA / Ecobank-format CSVs from a payroll run, reconcile the bank statement, and prove every cedi landed.",
        "src": f"{W3}/bunny/trailer.mp4",
        "poster": P.format("salonehcm-ifmis-8"),
        "duration_s": 32,
        "category": "deep_dive",
        "persona": "government",
        "sort": 20,
        "chapters": [{"t": 0, "label": "Pick the bank format"}, {"t": 12, "label": "Generate the file"}, {"t": 22, "label": "Reconcile statement"}],
    },
    {
        "title": "Ghost-worker audits in 5 minutes",
        "summary": "How the Civil Service module flags duplicate NASSIT numbers, mismatched bank ownership and dormant payslips — before they hit the press.",
        "src": f"{W3}/video/movie_300.mp4",
        "poster": P.format("salonehcm-ghost-9"),
        "duration_s": 30,
        "category": "deep_dive",
        "persona": "government",
        "sort": 30,
        "chapters": [{"t": 0, "label": "What's a ghost?"}, {"t": 10, "label": "Run the scan"}, {"t": 22, "label": "Generate the report"}],
    },
]


async def seed_videos() -> None:
    """Insert any seed videos that don't exist (idempotent by title), and
    refresh `src` + `poster` + `duration_s` + `chapters` for existing rows.
    This heals from broken CDNs — e.g., the retired Google gtv-videos-bucket."""
    inserted = 0
    updated = 0
    for v in SEED_VIDEOS:
        existing = await db.marketing_videos.find_one(
            {"title": v["title"]},
            {"_id": 1, "src": 1, "poster": 1, "duration_s": 1, "chapters": 1},
        )
        if existing:
            changes = {}
            for k in ("src", "poster", "duration_s", "chapters"):
                if existing.get(k) != v.get(k):
                    changes[k] = v[k]
            if changes:
                changes["updated_at"] = iso(now_utc())
                await db.marketing_videos.update_one(
                    {"_id": existing["_id"]}, {"$set": changes},
                )
                updated += 1
            continue
        doc = dict(v)
        doc["id"] = str(uuid.uuid4())
        doc["published"] = True
        doc["created_at"] = iso(now_utc())
        doc["updated_at"] = doc["created_at"]
        await db.marketing_videos.insert_one(doc)
        inserted += 1
    if inserted or updated:
        logger.info("Marketing video library: %d new, %d refreshed", inserted, updated)
