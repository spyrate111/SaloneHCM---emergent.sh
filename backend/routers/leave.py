"""Leave endpoints."""
import uuid
from datetime import datetime
from pymongo.errors import DuplicateKeyError
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from core import db, get_current_user, audit, now_utc, iso, tenant_filter, with_tenant, is_admin
from models import LeaveIn, LeaveDecision

from core import can_role

router = APIRouter(prefix="/leave", tags=["leave"])


@router.get("")
async def list_leaves(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    if can_role(user, "hr", "auditor"):
        return await db.leave_requests.find(tf, {"_id": 0}).sort("created_at", -1).to_list(1000)
    # Employee: their own + their direct reports' (if they're a manager)
    my_eid = user.get("employee_id")
    if not my_eid:
        return []
    reports = await db.employees.find(
        {"manager_id": my_eid, **tf},
        {"_id": 0, "id": 1},
    ).to_list(500)
    eids = [my_eid] + [r["id"] for r in reports]
    return await db.leave_requests.find(
        {"employee_id": {"$in": eids}, **tf},
        {"_id": 0},
    ).sort("created_at", -1).to_list(1000)


@router.get("/calendar")
async def leave_calendar(month: str = None, user: dict = Depends(get_current_user)):
    """Month grid data for managers/admins: every approved + pending leave
    overlapping the month. Admin: whole tenant. Manager: self + direct reports."""
    tf = tenant_filter(user)
    m = month or now_utc().strftime("%Y-%m")
    try:
        y, mm = int(m[:4]), int(m[5:7])
        assert 1 <= mm <= 12
    except Exception:
        raise HTTPException(422, "month must be YYYY-MM")
    start = f"{m}-01"
    ny, nm = (y + 1, 1) if mm == 12 else (y, mm + 1)
    end = f"{ny}-{nm:02d}-01"

    if can_role(user, "hr"):
        scope = tf
    else:
        my_eid = user.get("employee_id")
        reports = await db.employees.find(
            {"manager_id": my_eid, **tf}, {"_id": 0, "id": 1}).to_list(500) if my_eid else []
        if not reports:
            raise HTTPException(403, "Managers and admins only")
        scope = {**tf, "employee_id": {"$in": [r["id"] for r in reports] + [my_eid]}}

    rows = await db.leave_requests.find({
        **scope,
        "status": {"$in": ["approved", "pending"]},
        "start_date": {"$lt": end},
        "end_date": {"$gte": start},
    }, {"_id": 0, "id": 1, "employee_id": 1, "employee_name": 1, "leave_type": 1,
        "status": 1, "start_date": 1, "end_date": 1, "days": 1}).to_list(1000)
    return {"month": m, "leaves": rows}


ANNUAL_ENTITLEMENT_DAYS = 21  # Employment Act 2023 minimum


@router.get("/balance")
async def leave_balance(employee_id: str = None, user: dict = Depends(get_current_user)):
    """Current-year annual leave balance. Employees see their own; admins may
    pass employee_id."""
    tf = tenant_filter(user)
    eid = employee_id if (employee_id and can_role(user, "hr")) else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    year = str(now_utc().year)
    rows = await db.leave_requests.find({
        **tf, "employee_id": eid, "leave_type": "annual",
        "status": {"$in": ["approved", "pending"]},
        "start_date": {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"},
    }, {"_id": 0, "status": 1, "days": 1}).to_list(500)
    used = sum(r.get("days", 0) for r in rows if r["status"] == "approved")
    pending = sum(r.get("days", 0) for r in rows if r["status"] == "pending")
    return {"year": int(year), "entitlement": ANNUAL_ENTITLEMENT_DAYS,
            "used": used, "pending": pending,
            "remaining": max(0, ANNUAL_ENTITLEMENT_DAYS - used)}


async def _suggest_ranges(tf: dict, staff: list, eid: str, s: datetime, e: datetime,
                          threshold: int) -> list:
    """Up to 3 nearest same-duration ranges (never before today) where no day
    breaches the branch coverage threshold."""
    from datetime import timedelta
    duration = (e - s).days + 1
    today_d = datetime.fromisoformat(now_utc().strftime("%Y-%m-%d"))
    win_lo = min(s - timedelta(days=60), today_d)
    win_hi = e + timedelta(days=60)
    pool = await db.leave_requests.find({
        **tf, "status": "approved",
        "employee_id": {"$in": [x["id"] for x in staff if x["id"] != eid]},
        "start_date": {"$lte": win_hi.strftime("%Y-%m-%d")},
        "end_date": {"$gte": win_lo.strftime("%Y-%m-%d")},
    }, {"_id": 0, "employee_id": 1, "start_date": 1, "end_date": 1}).to_list(1000)

    def _clear(cand):
        for i in range(duration):
            key = (cand + timedelta(days=i)).strftime("%Y-%m-%d")
            off = len({o["employee_id"] for o in pool
                       if o["start_date"] <= key <= o["end_date"]}) + 1
            if off >= threshold:
                return False
        return True

    suggestions = []
    for dist in range(1, 61):
        for cand in (s + timedelta(days=dist), s - timedelta(days=dist)):
            if cand < today_d or len(suggestions) == 3:
                continue
            if _clear(cand):
                suggestions.append({
                    "start_date": cand.strftime("%Y-%m-%d"),
                    "end_date": (cand + timedelta(days=duration - 1)).strftime("%Y-%m-%d")})
        if len(suggestions) == 3:
            break
    return suggestions


@router.get("/coverage-preview")
async def coverage_preview(start_date: str, end_date: str, employee_id: str = None,
                           user: dict = Depends(get_current_user)):
    """Live coverage check while drafting a leave request. Employees preview
    their own branch; admins may preview for any employee. Never blocks."""
    import math
    from datetime import timedelta
    tf = tenant_filter(user)
    eid = employee_id if (employee_id and can_role(user, "hr")) else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    try:
        s = datetime.fromisoformat(start_date)
        e = datetime.fromisoformat(end_date)
        assert s <= e
    except Exception:
        raise HTTPException(422, "start_date/end_date must be YYYY-MM-DD with start <= end")
    emp = await db.employees.find_one({"id": eid, **tf}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")
    branch_id = emp.get("branch_id")
    if not branch_id:
        return {"warn": False, "reason": "employee has no branch", "days": [],
                "branch_name": None, "headcount": 0, "threshold": 0}
    branch = await db.branches.find_one({"id": branch_id, **tf}, {"_id": 0}) or {}
    staff = await db.employees.find(
        {"branch_id": branch_id, "status": "active", **tf},
        {"_id": 0, "id": 1}).to_list(2000)
    headcount = len(staff)
    threshold = max(2, math.ceil(0.2 * headcount))
    others = await db.leave_requests.find({
        **tf, "status": "approved",
        "employee_id": {"$in": [x["id"] for x in staff if x["id"] != eid]},
        "start_date": {"$lte": end_date}, "end_date": {"$gte": start_date},
    }, {"_id": 0, "employee_name": 1, "start_date": 1, "end_date": 1}).to_list(500)

    days = []
    cur, steps = s, 0
    while cur <= e and steps < 62:
        key = cur.strftime("%Y-%m-%d")
        names = sorted({o["employee_name"] for o in others
                        if o["start_date"] <= key <= o["end_date"]})
        off = len(names) + 1  # + this draft request
        days.append({"date": key, "off_count": off, "already_off": names,
                     "breach": off >= threshold})
        cur += timedelta(days=1)
        steps += 1

    # Nearest alternative ranges (same duration) where no day breaches — up to 3.
    suggestions = []
    if any(d["breach"] for d in days):
        suggestions = await _suggest_ranges(tf, staff, eid, s, e, threshold)
    return {"warn": any(d["breach"] for d in days), "branch_name": branch.get("name"),
            "headcount": headcount, "threshold": threshold, "days": days,
            "suggestions": suggestions}


@router.get("/{lid}/conflicts")
async def leave_conflicts(lid: str, user: dict = Depends(get_current_user)):
    """Pre-approval coverage check: warn when approving would put >= 20% of the
    branch's staff (minimum 2 people) off on any overlapping day. Never blocks."""
    import math
    from datetime import timedelta
    tf = tenant_filter(user)
    lv = await db.leave_requests.find_one({"id": lid, **tf}, {"_id": 0})
    if not lv:
        raise HTTPException(404, "Leave request not found")
    emp = await db.employees.find_one({"id": lv["employee_id"], **tf}, {"_id": 0})
    if not can_role(user, "hr"):
        if not emp or emp.get("manager_id") != user.get("employee_id"):
            raise HTTPException(403, "Admin or manager only")
    branch_id = (emp or {}).get("branch_id")
    if not branch_id:
        return {"warn": False, "reason": "employee has no branch", "days": [],
                "employee_name": lv["employee_name"]}
    branch = await db.branches.find_one({"id": branch_id, **tf}, {"_id": 0}) or {}
    staff = await db.employees.find(
        {"branch_id": branch_id, "status": "active", **tf},
        {"_id": 0, "id": 1}).to_list(2000)
    headcount = len(staff)
    threshold = max(2, math.ceil(0.2 * headcount))
    others = await db.leave_requests.find({
        **tf, "id": {"$ne": lid}, "status": "approved",
        "employee_id": {"$in": [s["id"] for s in staff if s["id"] != lv["employee_id"]]},
        "start_date": {"$lte": lv["end_date"]}, "end_date": {"$gte": lv["start_date"]},
    }, {"_id": 0, "employee_id": 1, "employee_name": 1, "start_date": 1, "end_date": 1}).to_list(500)

    days = []
    cur = datetime.fromisoformat(lv["start_date"])
    last = datetime.fromisoformat(lv["end_date"])
    steps = 0
    while cur <= last and steps < 62:
        key = cur.strftime("%Y-%m-%d")
        names = sorted({o["employee_name"] for o in others
                        if o["start_date"] <= key <= o["end_date"]})
        off = len(names) + 1  # + this request
        if off >= threshold:
            days.append({"date": key, "off_count": off, "already_off": names})
        cur += timedelta(days=1)
        steps += 1
    suggestions = []
    if days:
        suggestions = await _suggest_ranges(
            tf, staff, lv["employee_id"],
            datetime.fromisoformat(lv["start_date"]),
            datetime.fromisoformat(lv["end_date"]), threshold)
    return {"warn": bool(days), "branch_name": branch.get("name"),
            "headcount": headcount, "threshold": threshold,
            "employee_name": lv["employee_name"], "days": days[:14],
            "suggestions": suggestions}


@router.post("/{lid}/suggest-dates")
async def suggest_dates(lid: str, user: dict = Depends(get_current_user)):
    """Push the employee up to 3 better-covered alternative ranges for their
    pending request. Admin or the employee's direct manager only."""
    import math
    tf = tenant_filter(user)
    lv = await db.leave_requests.find_one({"id": lid, **tf}, {"_id": 0})
    if not lv:
        raise HTTPException(404, "Leave request not found")
    emp = await db.employees.find_one({"id": lv["employee_id"], **tf}, {"_id": 0})
    if not can_role(user, "hr"):
        if not emp or emp.get("manager_id") != user.get("employee_id"):
            raise HTTPException(403, "Admin or manager only")
    branch_id = (emp or {}).get("branch_id")
    if not branch_id:
        raise HTTPException(409, "Employee has no branch — no coverage data")
    staff = await db.employees.find(
        {"branch_id": branch_id, "status": "active", **tf},
        {"_id": 0, "id": 1}).to_list(2000)
    threshold = max(2, math.ceil(0.2 * len(staff)))
    suggestions = await _suggest_ranges(
        tf, staff, lv["employee_id"],
        datetime.fromisoformat(lv["start_date"]),
        datetime.fromisoformat(lv["end_date"]), threshold)
    if not suggestions:
        raise HTTPException(409, "No better-covered dates found nearby")

    def _fmt(r):
        return r["start_date"] if r["start_date"] == r["end_date"] else f'{r["start_date"]} → {r["end_date"]}'

    target = await db.users.find_one(
        {"employee_id": lv["employee_id"], **tf}, {"_id": 0, "id": 1})
    push = {"sent": 0, "skipped": "no_account"}
    if target:
        from push_service import fanout_to_user
        push = await fanout_to_user(target["id"], {
            "title": "Alternative leave dates suggested",
            "body": (f'Your {lv["leave_type"]} leave {_fmt(lv)} clashes with team '
                     f'coverage. Better-covered options: '
                     f'{"; ".join(_fmt(r) for r in suggestions)}'),
            "url": "/m/leave", "kind": "leave_date_suggestion",
            "tag": f"leave-suggest-{lid}"})
    await audit("leave_dates_suggested", f"leave_requests/{lid}", user,
                {"employee": lv.get("employee_name"), "suggestions": suggestions})
    # Persist for the employee's "suggested dates" inbox (supersede older ones)
    await db.leave_suggestions.update_many(
        {**tf, "leave_id": lid, "status": "open"},
        {"$set": {"status": "superseded"}})
    await db.leave_suggestions.insert_one(with_tenant({
        "id": str(uuid.uuid4()), "leave_id": lid,
        "employee_id": lv["employee_id"], "employee_name": lv.get("employee_name"),
        "leave_type": lv["leave_type"],
        "original": {"start_date": lv["start_date"], "end_date": lv["end_date"]},
        "suggestions": suggestions, "suggested_by": user.get("name") or "Approver",
        "suggested_by_user_id": user["id"],
        "status": "open", "created_at": iso(now_utc()),
    }, user))
    return {"ok": True, "suggestions": suggestions, "push": push}


@router.get("/suggestions/mine")
async def my_date_suggestions(user: dict = Depends(get_current_user)):
    """Open alternative-date suggestions an approver sent to me."""
    eid = user.get("employee_id")
    if not eid:
        return []
    return await db.leave_suggestions.find(
        {**tenant_filter(user), "employee_id": eid, "status": "open"},
        {"_id": 0}).sort("created_at", -1).to_list(20)


class AcceptSuggestionIn(BaseModel):
    start_date: str
    end_date: str


@router.post("/suggestions/{sid}/accept")
async def accept_date_suggestion(sid: str, body: AcceptSuggestionIn,
                                 user: dict = Depends(get_current_user)):
    """One-tap re-submit: new request with the chosen suggested range; the
    original pending request is withdrawn."""
    tf = tenant_filter(user)
    sug = await db.leave_suggestions.find_one({"id": sid, **tf}, {"_id": 0})
    if not sug or sug["status"] != "open":
        raise HTTPException(404, "Suggestion not found or already handled")
    if sug["employee_id"] != user.get("employee_id"):
        raise HTTPException(403, "Not your suggestion")
    if not any(r["start_date"] == body.start_date and r["end_date"] == body.end_date
               for r in sug["suggestions"]):
        raise HTTPException(422, "Chosen range is not one of the suggested options")
    emp = await db.employees.find_one({"id": sug["employee_id"], **tf}, {"_id": 0})
    days = (datetime.fromisoformat(body.end_date)
            - datetime.fromisoformat(body.start_date)).days + 1
    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "employee_id": sug["employee_id"],
        "employee_name": f'{emp["first_name"]} {emp["last_name"]}',
        "leave_type": sug["leave_type"],
        "start_date": body.start_date,
        "end_date": body.end_date,
        "days": max(1, days),
        "reason": "Re-submitted with approver-suggested dates",
        "status": "pending",
        "created_at": iso(now_utc()),
    }, user)
    await db.leave_requests.insert_one(doc)
    doc.pop("_id", None)
    await db.leave_requests.update_one(
        {"id": sug["leave_id"], **tf, "status": "pending"},
        {"$set": {"status": "withdrawn"}})
    await db.leave_suggestions.update_one({"id": sid}, {"$set": {"status": "accepted"}})
    await audit("leave_suggestion_accepted", f"leave_requests/{doc['id']}", user,
                {"from_suggestion": sid, "range": [body.start_date, body.end_date]})
    push = {"sent": 0, "skipped": "no_approver"}
    approver_uid = sug.get("suggested_by_user_id")
    if approver_uid:
        from push_service import fanout_to_user
        rng = (body.start_date if body.start_date == body.end_date
               else f"{body.start_date} → {body.end_date}")
        push = await fanout_to_user(approver_uid, {
            "title": "Suggested dates accepted",
            "body": f'{doc["employee_name"]} accepted your suggested dates ({rng}). Tap to approve.',
            "url": f"/m/leave?focus={doc['id']}",
            "kind": "leave_suggestion_accepted",
            "tag": f"leave-accept-{sid}",
        })
    return {**doc, "push": push}


@router.post("/suggestions/{sid}/dismiss")
async def dismiss_date_suggestion(sid: str, user: dict = Depends(get_current_user)):
    """Employee dismisses an approver's alternative-date suggestion; the
    original request stays pending and the card never reappears."""
    tf = tenant_filter(user)
    sug = await db.leave_suggestions.find_one({"id": sid, **tf}, {"_id": 0})
    if not sug or sug["status"] != "open":
        raise HTTPException(404, "Suggestion not found or already handled")
    if sug["employee_id"] != user.get("employee_id"):
        raise HTTPException(403, "Not your suggestion")
    await db.leave_suggestions.update_one({"id": sid}, {"$set": {"status": "dismissed"}})
    await audit("leave_suggestion_dismissed", f"leave_suggestions/{sid}", user,
                {"leave_id": sug["leave_id"]})
    return {"ok": True}


@router.post("")
async def create_leave(body: LeaveIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if can_role(user, "hr") else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    emp = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found in your organization")

    client_request_id = (body.client_request_id or "").strip()

    async def _existing_request():
        if not client_request_id:
            return None
        existing = await db.leave_requests.find_one(
            {**tenant_filter(user), "employee_id": eid, "client_request_id": client_request_id},
            {"_id": 0},
        )
        if not existing:
            return None
        same_request = (
            existing.get("leave_type") == body.leave_type
            and existing.get("start_date") == body.start_date
            and existing.get("end_date") == body.end_date
            and (existing.get("reason") or "") == (body.reason or "")
        )
        if not same_request:
            raise HTTPException(409, "This offline request ID was already used for different leave details")
        return existing

    existing = await _existing_request()
    if existing:
        return existing

    days = (datetime.fromisoformat(body.end_date) - datetime.fromisoformat(body.start_date)).days + 1
    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "employee_name": f'{emp["first_name"]} {emp["last_name"]}',
        "leave_type": body.leave_type,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "days": max(1, days),
        "reason": body.reason,
        "status": "pending",
        "created_at": iso(now_utc()),
    }, user)
    if client_request_id:
        doc["client_request_id"] = client_request_id
    try:
        await db.leave_requests.insert_one(doc)
    except DuplicateKeyError:
        existing = await _existing_request()
        if existing:
            return existing
        raise HTTPException(409, "This offline request ID has already been used")
    doc.pop("_id", None)
    return doc


@router.put("/{lid}/decision")
async def decide_leave(lid: str, body: LeaveDecision, user: dict = Depends(get_current_user)):
    lv = await db.leave_requests.find_one({"id": lid, **tenant_filter(user)}, {"_id": 0})
    if not lv:
        raise HTTPException(404, "Not found")
    # Authorization: admin/superadmin, or the requesting employee's direct manager
    if not can_role(user, "hr"):
        if not user.get("employee_id"):
            raise HTTPException(403, "Admin or manager only")
        emp = await db.employees.find_one({"id": lv["employee_id"]}, {"_id": 0})
        if not emp or emp.get("manager_id") != user["employee_id"]:
            raise HTTPException(403, "You can only decide leave for your direct reports")
    res = await db.leave_requests.update_one(
        {"id": lid, **tenant_filter(user)},
        {"$set": {"status": body.status}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Not found")
    action = f"leave_{body.status}" if can_role(user, "hr") else f"manager_leave_{body.status}"
    await audit(action, f"leave_requests/{lid}", user, {"employee": lv.get("employee_name")})
    return {"ok": True, "status": body.status}
