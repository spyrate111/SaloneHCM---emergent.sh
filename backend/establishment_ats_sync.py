"""Establishment → Talent ATS sync.

Whenever a Gov tenant creates or edits an `establishment_position`, we auto-publish
matching job_postings so citizens/applicants can apply through the ATS. This closes
the loop between headcount planning (Establishment Control) and recruitment (Talent).

Sync rules
----------
- One establishment_position → at most one auto-managed job_posting
  (linked via `job_postings.position_id`, `source="establishment"`).
- Posting is OPEN iff vacancy_count > 0 AND position.status == "active".
- Fields (title/department/location/salary/description) are refreshed from the
  establishment record on every sync. Manual edits to auto-managed postings are
  intentionally NOT preserved — if you need bespoke copy, create a separate
  `source="manual"` posting.
- Delete/freeze of the establishment position closes (but never deletes) the
  linked posting, so historical applicants remain queryable.
- Sync is fire-and-forget after the primary establishment mutation — failure
  never blocks the caller.
"""
from __future__ import annotations
import logging
import uuid
from collections import defaultdict

from core import db, iso, now_utc, with_tenant

log = logging.getLogger(__name__)


def _posting_from_position(position: dict, vacancy_count: int) -> dict:
    """Build the fields (excluding id, company_id, created_at) for the auto-posting."""
    grade = position.get("grade_code") or ""
    step = position.get("step_number")
    grade_line = f"Grade {grade}" + (f", step {step}" if step else "") if grade else ""
    parts = [
        f"Vacancy at {position['ministry']} · {position['directorate']} · {position['unit']}.",
        f"Approved headcount: {position.get('approved_count', 0)}. Current vacancies: {vacancy_count}.",
    ]
    if grade_line:
        parts.append(grade_line + ".")
    if position.get("budget_code"):
        parts.append(f"Funded under budget code {position['budget_code']}.")
    parts.append("Applications are reviewed on a rolling basis. Sierra Leonean citizens preferred.")

    return {
        "title": position["position_title"],
        "department": position["directorate"],
        "location": "Freetown",
        "employment_type": "Full-time",
        "salary_min_sle": 0,
        "salary_max_sle": 0,
        "description": " ".join(parts),
        "source": "establishment",
        "position_id": position["id"],
        "establishment_meta": {
            "ministry": position["ministry"],
            "directorate": position["directorate"],
            "unit": position["unit"],
            "grade_code": position.get("grade_code"),
            "step_number": position.get("step_number"),
            "budget_code": position.get("budget_code"),
            "approved_count": position.get("approved_count", 0),
            "vacancy_count": vacancy_count,
            "position_status": position.get("status"),
        },
        "auto_synced_at": iso(now_utc()),
    }


async def sync_position_to_posting(position: dict, filled_count: int, user: dict) -> dict | None:
    """Create or update the job_posting linked to `position`. Returns the posting doc or None."""
    approved = position.get("approved_count", 0)
    vacancy = max(0, approved - filled_count)
    is_active = position.get("status") == "active"
    should_be_open = is_active and vacancy > 0

    existing = await db.job_postings.find_one({"position_id": position["id"], "company_id": user["company_id"]}, {"_id": 0})
    base = _posting_from_position(position, vacancy)
    base["status"] = "open" if should_be_open else "closed"

    if existing:
        await db.job_postings.update_one(
            {"id": existing["id"], "company_id": user["company_id"]},
            {"$set": base},
        )
        merged = {**existing, **base}
        merged.pop("_id", None)
        return merged

    # No existing posting.
    if not should_be_open:
        # Nothing to open, nothing to update — no-op (avoid publishing already-full/frozen positions).
        return None

    pid = str(uuid.uuid4())
    doc = with_tenant({
        **base,
        "id": pid,
        "created_at": iso(now_utc()),
    }, user)
    await db.job_postings.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def close_position_posting(position_id: str, user: dict) -> bool:
    """Ensure the linked posting is closed (used when the position is deleted).
    Returns True if a posting was updated."""
    r = await db.job_postings.update_one(
        {"position_id": position_id, "company_id": user["company_id"], "source": "establishment"},
        {"$set": {
            "status": "closed",
            "auto_synced_at": iso(now_utc()),
            "establishment_meta.position_status": "deleted",
        }},
    )
    return bool(r.matched_count)


async def sync_all_positions_for_tenant(company_id: str, actor_email: str = "system") -> dict:
    """Batch: reconcile every establishment_position → job_posting for one tenant.
    Idempotent. Safe to run on boot or from an admin endpoint."""
    positions = await db.establishment_positions.find({"company_id": company_id}, {"_id": 0}).to_list(5000)
    if not positions:
        return {"positions": 0, "created": 0, "updated": 0, "closed": 0}

    # Compute filled counts once.
    filled = defaultdict(int)
    async for e in db.employees.find(
        {"company_id": company_id, "position_id": {"$exists": True, "$ne": None},
         "status": {"$ne": "terminated"}},
        {"_id": 0, "position_id": 1},
    ):
        if e.get("position_id"):
            filled[e["position_id"]] += 1

    pseudo_user = {"company_id": company_id, "email": actor_email}
    created = updated = closed = 0
    for p in positions:
        prior = await db.job_postings.find_one({"position_id": p["id"], "company_id": company_id}, {"_id": 0, "status": 1})
        result = await sync_position_to_posting(p, filled.get(p["id"], 0), pseudo_user)
        if result is None:
            continue
        if prior is None:
            created += 1
        elif prior.get("status") == "open" and result.get("status") == "closed":
            closed += 1
        else:
            updated += 1
    log.info("[establishment→ats] company=%s positions=%d created=%d updated=%d closed=%d",
             company_id, len(positions), created, updated, closed)
    return {"positions": len(positions), "created": created, "updated": updated, "closed": closed}
