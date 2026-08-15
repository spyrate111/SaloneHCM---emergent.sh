"""Training-video completion tracking.

Employees mark walkthrough videos complete (fired by the mobile player's
`ended` event). Supervisors/admins get a completion matrix per employee.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_user, now_utc, iso, tenant_filter, is_admin

router = APIRouter(prefix="/training-progress", tags=["training-progress"])


class CompleteIn(BaseModel):
    base_slug: str = Field(..., min_length=2, max_length=120)
    lang: Optional[str] = Field(default="en", max_length=12)


async def _catalog() -> list[dict]:
    """Distinct training videos (English titles as canonical)."""
    vids = await db.marketing_videos.find(
        {"category": "training", "lang": "en"},
        {"_id": 0, "base_slug": 1, "title": 1, "sort": 1}).to_list(100)
    vids.sort(key=lambda v: v.get("sort") or 0)
    return vids


@router.post("/complete")
async def mark_complete(body: CompleteIn, user: dict = Depends(get_current_user)):
    known = {v["base_slug"] for v in await _catalog()}
    if body.base_slug not in known:
        raise HTTPException(404, "Unknown training video")
    await db.training_progress.update_one(
        {"user_id": user["id"], "base_slug": body.base_slug},
        {"$set": {"company_id": user.get("company_id"),
                  "lang": body.lang or "en",
                  "completed_at": iso(now_utc())},
         "$setOnInsert": {"user_id": user["id"], "base_slug": body.base_slug}},
        upsert=True)
    return {"ok": True, "base_slug": body.base_slug}


@router.get("/me")
async def my_progress(user: dict = Depends(get_current_user)):
    catalog = await _catalog()
    done = await db.training_progress.find(
        {"user_id": user["id"]}, {"_id": 0, "base_slug": 1, "completed_at": 1}).to_list(100)
    return {"completed": [d["base_slug"] for d in done],
            "total": len(catalog),
            "completed_count": len({d["base_slug"] for d in done})}


@router.get("/team")
async def team_progress(branch_id: Optional[str] = None,
                        user: dict = Depends(get_current_user)):
    """Completion matrix. Admins: whole tenant. Branch supervisors: their branches."""
    tf = tenant_filter(user)
    if is_admin(user):
        emp_q = dict(tf)
    else:
        my_branches = await db.branches.find(
            {**tf, "supervisor_user_id": user["id"]}, {"_id": 0, "id": 1}).to_list(100)
        if not my_branches:
            raise HTTPException(403, "Supervisors and admins only")
        emp_q = {**tf, "branch_id": {"$in": [b["id"] for b in my_branches]}}
    if branch_id:
        emp_q["branch_id"] = branch_id

    emps = await db.employees.find(
        emp_q, {"_id": 0, "id": 1, "first_name": 1, "last_name": 1, "branch_id": 1}).to_list(1000)
    emp_ids = [e["id"] for e in emps]
    users = await db.users.find(
        {**tf, "employee_id": {"$in": emp_ids}},
        {"_id": 0, "id": 1, "employee_id": 1, "name": 1}).to_list(1000)
    user_by_emp = {u["employee_id"]: u for u in users}

    catalog = await _catalog()
    progress = await db.training_progress.find(
        {"user_id": {"$in": [u["id"] for u in users]}},
        {"_id": 0, "user_id": 1, "base_slug": 1}).to_list(5000)
    done_by_user: dict[str, set] = {}
    for p in progress:
        done_by_user.setdefault(p["user_id"], set()).add(p["base_slug"])

    branches = {b["id"]: b for b in await db.branches.find(tf, {"_id": 0, "id": 1, "name": 1}).to_list(200)}
    rows = []
    for e in emps:
        u = user_by_emp.get(e["id"])
        done = done_by_user.get(u["id"], set()) if u else set()
        rows.append({
            "employee_id": e["id"],
            "user_id": (u or {}).get("id"),
            "name": f"{e.get('first_name','')} {e.get('last_name','')}".strip(),
            "branch_id": e.get("branch_id"),
            "branch_name": (branches.get(e.get("branch_id")) or {}).get("name"),
            "has_account": bool(u),
            "completed": sorted(done),
            "completed_count": len(done),
        })
    rows.sort(key=lambda r: (-r["completed_count"], r["name"]))
    return {"videos": catalog, "total": len(catalog), "rows": rows}
