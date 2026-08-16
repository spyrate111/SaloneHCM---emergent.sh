"""Leave endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, audit, now_utc, iso, tenant_filter, with_tenant, is_admin
from models import LeaveIn, LeaveDecision

router = APIRouter(prefix="/leave", tags=["leave"])


@router.get("")
async def list_leaves(user: dict = Depends(get_current_user)):
    tf = tenant_filter(user)
    if is_admin(user):
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

    if is_admin(user):
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


@router.get("/coverage-preview")
async def coverage_preview(start_date: str, end_date: str, employee_id: str = None,
                           user: dict = Depends(get_current_user)):
    """Live coverage check while drafting a leave request. Employees preview
    their own branch; admins may preview for any employee. Never blocks."""
    import math
    from datetime import timedelta
    tf = tenant_filter(user)
    eid = employee_id if (employee_id and is_admin(user)) else user.get("employee_id")
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
    if not is_admin(user):
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
    return {"warn": bool(days), "branch_name": branch.get("name"),
            "headcount": headcount, "threshold": threshold,
            "employee_name": lv["employee_name"], "days": days[:14]}


@router.post("")
async def create_leave(body: LeaveIn, user: dict = Depends(get_current_user)):
    eid = body.employee_id if is_admin(user) else user.get("employee_id")
    if not eid:
        raise HTTPException(400, "employee_id required")
    emp = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found in your organization")
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
    await db.leave_requests.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/{lid}/decision")
async def decide_leave(lid: str, body: LeaveDecision, user: dict = Depends(get_current_user)):
    lv = await db.leave_requests.find_one({"id": lid, **tenant_filter(user)}, {"_id": 0})
    if not lv:
        raise HTTPException(404, "Not found")
    # Authorization: admin/superadmin, or the requesting employee's direct manager
    if user.get("role") not in ("admin", "superadmin"):
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
    action = f"leave_{body.status}" if is_admin(user) else f"manager_leave_{body.status}"
    await audit(action, f"leave_requests/{lid}", user, {"employee": lv.get("employee_name")})
    return {"ok": True, "status": body.status}
