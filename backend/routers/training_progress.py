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


class LangIn(BaseModel):
    lang: str = Field(..., pattern="^(en|krio|mende|temne)$")


@router.post("/lang")
async def set_training_lang(body: LangIn, user: dict = Depends(get_current_user)):
    """Remember the user's Training Center language — weekly reminders use it."""
    await db.users.update_one({"id": user["id"]}, {"$set": {"training_lang": body.lang}})
    return {"ok": True, "lang": body.lang}


@router.post("/reminders/run-now")
async def reminders_run_now(user: dict = Depends(get_current_user)):
    """Manually trigger this week's reminder push for my tenant (admin only)."""
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    from training_reminders import run_for_company
    return await run_for_company(user["company_id"])


@router.get("/reminders/stats")
async def reminder_stats(user: dict = Depends(get_current_user)):
    """Weekly nudge analytics: reminders sent per ISO week and the share of
    recipients who completed a video within 7 days of the nudge. Admin only."""
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    from datetime import datetime, timedelta
    LANGS = ("en", "krio", "mende", "temne")
    tf = tenant_filter(user)
    reminders = await db.training_reminders.find(
        tf, {"_id": 0, "user_id": 1, "week": 1, "lang": 1, "push_sent": 1, "created_at": 1}
    ).to_list(5000)
    if not reminders:
        return {"weeks": [], "totals": {"reminded": 0, "delivered": 0,
                                        "completed_after": 0, "nudge_rate": 0},
                "languages": [{"lang": l, "reminded": 0, "completed_after": 0,
                               "nudge_rate": 0.0} for l in LANGS]}
    progress = await db.training_progress.find(
        {"user_id": {"$in": list({r["user_id"] for r in reminders})}},
        {"_id": 0, "user_id": 1, "completed_at": 1}).to_list(10000)
    completions: dict[str, list] = {}
    for p in progress:
        if p.get("completed_at"):
            completions.setdefault(p["user_id"], []).append(p["completed_at"])

    def _rate(c, n):
        return round(100 * c / n, 1) if n else 0.0

    weeks: dict[str, dict] = {}
    for r in reminders:
        w = weeks.setdefault(r["week"], {
            "week": r["week"], "reminded": 0, "delivered": 0, "completed_after": 0,
            "_langs": {l: {"reminded": 0, "completed_after": 0} for l in LANGS}})
        lang = r.get("lang") if r.get("lang") in LANGS else "en"
        w["reminded"] += 1
        w["delivered"] += 1 if r.get("push_sent") else 0
        w["_langs"][lang]["reminded"] += 1
        sent_at = datetime.fromisoformat(r["created_at"])
        cutoff = sent_at + timedelta(days=7)
        if any(sent_at < datetime.fromisoformat(c) <= cutoff
               for c in completions.get(r["user_id"], [])):
            w["completed_after"] += 1
            w["_langs"][lang]["completed_after"] += 1
    out = sorted(weeks.values(), key=lambda x: x["week"], reverse=True)[:12]
    lang_totals = {l: {"reminded": 0, "completed_after": 0} for l in LANGS}
    for w in out:
        w["nudge_rate"] = _rate(w["completed_after"], w["reminded"])
        langs = w.pop("_langs")
        for l in LANGS:
            lang_totals[l]["reminded"] += langs[l]["reminded"]
            lang_totals[l]["completed_after"] += langs[l]["completed_after"]
        w["languages"] = [{"lang": l, **langs[l],
                           "nudge_rate": _rate(langs[l]["completed_after"], langs[l]["reminded"])}
                          for l in LANGS]
    tot_r = sum(w["reminded"] for w in out)
    tot_c = sum(w["completed_after"] for w in out)
    return {"weeks": out,
            "totals": {"reminded": tot_r,
                       "delivered": sum(w["delivered"] for w in out),
                       "completed_after": tot_c,
                       "nudge_rate": _rate(tot_c, tot_r)},
            "languages": [{"lang": l, **lang_totals[l],
                           "nudge_rate": _rate(lang_totals[l]["completed_after"],
                                               lang_totals[l]["reminded"])}
                          for l in LANGS]}
