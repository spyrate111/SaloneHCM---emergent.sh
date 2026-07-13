"""Branches + voucher role flags seed for the centralized voucher repository."""
import uuid
from core import db, logger, iso, now_utc

GOV_BRANCHES = [
    ("MOF-HQ", "Ministry of Finance HQ", "Freetown", "Ministry of Finance"),
    ("MOH-FT", "Ministry of Health Office", "Freetown", "Ministry of Health"),
    ("MOL-FT", "Ministry of Labour Office", "Freetown", "Ministry of Labour"),
]
DEMO_BRANCHES = [
    ("HQ-FT", "Freetown Head Office", "Freetown", ""),
    ("BO-01", "Bo Branch", "Bo", ""),
]


async def seed_branches(gov_id: str, demo_id: str) -> None:
    await _seed_tenant(gov_id, GOV_BRANCHES, match_ministry=True)
    await _seed_tenant(demo_id, DEMO_BRANCHES, match_ministry=False)
    # Finance officer flag on a non-admin gov user so the dual-control chain
    # (creator ≠ approver ≠ authorizer) is exercisable out of the box.
    await db.users.update_one({"email": "memuna.tucker@gov.sl"},
                              {"$set": {"finance_officer": True}})
    # Permanent Secretary doubles as a second MoF approver for payment authorization.
    await db.users.update_one({"email": "adama.sankoh@gov.sl"},
                              {"$set": {"mof_approver": True}})
    logger.info("Voucher branches seeded")


async def _seed_tenant(company_id: str, defs: list, match_ministry: bool) -> None:
    for code, name, region, ministry in defs:
        if not await db.branches.find_one({"company_id": company_id, "code": code}):
            await db.branches.insert_one({
                "id": str(uuid.uuid4()), "company_id": company_id, "code": code,
                "name": name, "region": region, "ministry": ministry,
                "supervisor_user_id": None, "supervisor_email": None, "supervisor_name": None,
                "created_by": "seed", "created_at": iso(now_utc()),
            })
    branches = await db.branches.find({"company_id": company_id}, {"_id": 0}).to_list(50)
    if not branches:
        return

    emps = await db.employees.find(
        {"company_id": company_id, "branch_id": {"$exists": False}},
        {"_id": 0, "id": 1, "department": 1, "mda_ministry": 1}).to_list(2000)
    if match_ministry:
        by_min = {b["ministry"]: b for b in branches if b.get("ministry")}
        for e in emps:
            b = by_min.get(e.get("department")) or by_min.get(e.get("mda_ministry"))
            if b:
                await db.employees.update_one({"id": e["id"]}, {"$set": {"branch_id": b["id"]}})
    else:
        for i, e in enumerate(emps):
            b = branches[i % len(branches)]
            await db.employees.update_one({"id": e["id"]}, {"$set": {"branch_id": b["id"]}})

    # Supervisor per branch: first manager (else first) assigned employee with a user account.
    for b in branches:
        if b.get("supervisor_user_id"):
            continue
        assigned = await db.employees.find(
            {"company_id": company_id, "branch_id": b["id"]},
            {"_id": 0, "email": 1, "is_manager": 1}).sort("email", 1).to_list(500)
        if not assigned:
            continue
        pick = next((e for e in assigned if e.get("is_manager")), assigned[0])
        u = await db.users.find_one({"email": pick["email"], "company_id": company_id},
                                    {"_id": 0, "id": 1, "email": 1, "name": 1})
        if u:
            await db.branches.update_one({"id": b["id"]}, {"$set": {
                "supervisor_user_id": u["id"], "supervisor_email": u["email"],
                "supervisor_name": u["name"]}})
