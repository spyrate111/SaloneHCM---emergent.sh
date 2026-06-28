"""Seed the marketing video library on first boot.
PLACEHOLDER VIDEOS — replace src/poster URLs with real SaloneHCM screen recordings
when ready. The Google "gtv-videos-bucket" sample MP4s are public-domain test
videos used in HLS/DASH demos and are safe for placeholder use.
Super-admin can manage the library at POST/PATCH/DELETE /api/marketing/admin/videos.
"""
import uuid
from core import db, now_utc, iso, logger

# Picsum.photos provides hotlink-friendly seeded placeholder images.
# Replace the `poster` URL on any video with your real screenshot via the
# super-admin endpoint (POST/PATCH /api/marketing/admin/videos) once recorded.
P = "https://picsum.photos/seed/{}/720/405"
GVB = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample"

SEED_VIDEOS = [
    # ---- Getting started (Small Business persona) ----
    {
        "title": "First payroll run in under 2 hours",
        "summary": "Follow Aminata as she sets up Freetown Logistics Ltd and pays 18 employees end-to-end — from importing the spreadsheet to filing PAYE.",
        "src": f"{GVB}/BigBuckBunny.mp4",
        "poster": P.format("salonehcm-payroll-1"),
        "duration_s": 124,
        "category": "getting_started",
        "persona": "small_business",
        "sort": 10,
        "chapters": [
            {"t": 0,   "label": "Import your team"},
            {"t": 35,  "label": "Set NRA PAYE bands"},
            {"t": 78,  "label": "Run & approve"},
            {"t": 104, "label": "File the return"},
        ],
    },
    {
        "title": "Onboarding your first 10 employees",
        "summary": "How to get a small team from spreadsheet to self-service in a single afternoon — bank details, NASSIT numbers, emergency contacts, and the welcome SMS.",
        "src": f"{GVB}/ForBiggerFun.mp4",
        "poster": P.format("salonehcm-onboard-2"),
        "duration_s": 92,
        "category": "getting_started",
        "persona": "small_business",
        "sort": 20,
        "chapters": [{"t": 0, "label": "Bulk upload"}, {"t": 40, "label": "Welcome SMS"}, {"t": 70, "label": "Self-service activation"}],
    },
    {
        "title": "Filing your NRA PAYE return — a 90-second walkthrough",
        "summary": "Where to find the export, what to double-check, and how SaloneHCM matches NRA's expected format down to the last column.",
        "src": f"{GVB}/ForBiggerEscapes.mp4",
        "poster": P.format("salonehcm-paye-3"),
        "duration_s": 95,
        "category": "getting_started",
        "persona": "small_business",
        "sort": 30,
        "chapters": [{"t": 0, "label": "Pick the period"}, {"t": 30, "label": "Generate the export"}, {"t": 65, "label": "Submit to NRA portal"}],
    },

    # ---- By persona / industry ----
    {
        "title": "Government & MDAs: civil service payroll walkthrough",
        "summary": "Grade & step structure, budget-code roll-ups, MoF two-step approval and the auditor-general report PDF — all in one continuous flow.",
        "src": f"{GVB}/ElephantsDream.mp4",
        "poster": P.format("salonehcm-gov-4"),
        "duration_s": 188,
        "category": "by_persona",
        "persona": "government",
        "sort": 10,
        "chapters": [
            {"t": 0,   "label": "Grade & step structure"},
            {"t": 60,  "label": "Budget code roll-up"},
            {"t": 110, "label": "MoF approval workflow"},
            {"t": 150, "label": "Audit PDF export"},
        ],
    },
    {
        "title": "NGO sector allowances done right",
        "summary": "Per-diem, field, hardship and family-separation allowances applied to one employee or a whole project team in a single click.",
        "src": f"{GVB}/ForBiggerBlazes.mp4",
        "poster": P.format("salonehcm-ngo-5"),
        "duration_s": 137,
        "category": "by_persona",
        "persona": "ngo",
        "sort": 20,
        "chapters": [{"t": 0, "label": "Pick the NGO preset"}, {"t": 45, "label": "Apply to project team"}, {"t": 95, "label": "Auto-detect duty stations"}],
    },
    {
        "title": "Mining sector: hazard, remote-site & fuel allowances",
        "summary": "How a mining operation in Kono runs payroll with shift differentials, hazard pay and on-site fuel benefits — and keeps NRA happy.",
        "src": f"{GVB}/ForBiggerJoyrides.mp4",
        "poster": P.format("salonehcm-mining-6"),
        "duration_s": 156,
        "category": "by_persona",
        "persona": "mining",
        "sort": 30,
        "chapters": [{"t": 0, "label": "Shift configuration"}, {"t": 50, "label": "Hazard band applied"}, {"t": 110, "label": "Tax-exempt fuel handling"}],
    },

    # ---- Deep dives ----
    {
        "title": "Bulk payslip SMS via Twilio +232",
        "summary": "How to send every employee their net-pay SMS in one click — with delivery tracking, retry on failure, and a complete audit log.",
        "src": f"{GVB}/ForBiggerMeltdowns.mp4",
        "poster": P.format("salonehcm-sms-7"),
        "duration_s": 78,
        "category": "deep_dive",
        "persona": "general",
        "sort": 10,
        "chapters": [{"t": 0, "label": "Connect Twilio"}, {"t": 30, "label": "Run the batch"}, {"t": 55, "label": "Inspect delivery logs"}],
    },
    {
        "title": "IFMIS bank file disbursement",
        "summary": "Generate Rokel / SLCB / UBA / Ecobank-format CSVs from a payroll run, reconcile the bank statement, and prove every cedi landed.",
        "src": f"{GVB}/Sintel.mp4",
        "poster": P.format("salonehcm-ifmis-8"),
        "duration_s": 162,
        "category": "deep_dive",
        "persona": "government",
        "sort": 20,
        "chapters": [{"t": 0, "label": "Pick the bank format"}, {"t": 60, "label": "Generate the file"}, {"t": 120, "label": "Reconcile statement"}],
    },
    {
        "title": "Ghost-worker audits in 5 minutes",
        "summary": "How the Civil Service module flags duplicate NASSIT numbers, mismatched bank ownership and dormant payslips — before they hit the press.",
        "src": f"{GVB}/SubaruOutbackOnStreetAndDirt.mp4",
        "poster": P.format("salonehcm-ghost-9"),
        "duration_s": 109,
        "category": "deep_dive",
        "persona": "government",
        "sort": 30,
        "chapters": [{"t": 0, "label": "What's a ghost?"}, {"t": 35, "label": "Run the scan"}, {"t": 80, "label": "Generate the report"}],
    },
]


async def seed_videos() -> None:
    """Insert any seed videos that don't exist (idempotent by title) and
    also update poster URLs in place if the row already exists — this lets us
    swap placeholder posters without manual DB surgery."""
    inserted = 0
    updated = 0
    for v in SEED_VIDEOS:
        existing = await db.marketing_videos.find_one({"title": v["title"]}, {"_id": 1, "poster": 1})
        if existing:
            if existing.get("poster") != v["poster"]:
                await db.marketing_videos.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"poster": v["poster"], "updated_at": iso(now_utc())}},
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
        logger.info("Marketing video library: %d new, %d poster refresh(es)", inserted, updated)
