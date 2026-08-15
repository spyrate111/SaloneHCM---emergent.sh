"""Mobile app aggregator + geo-tagged clock in/out — designed to back the
SaloneHCM PWA (and future React Native / Capacitor wrappers) with a small
set of dense, role-aware endpoints that minimise round-trips on cellular
networks."""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import (
    db,
    get_current_user,
    audit,
    now_utc,
    iso,
    tenant_filter,
    with_tenant,
    is_admin,
)
from payroll_engine import calc_payslip

router = APIRouter(prefix="/mobile", tags=["mobile"])


# ---------------------------------------------------------------------------
# Aggregated dashboard — one call to power the mobile Home screen
# ---------------------------------------------------------------------------
@router.get("/summary")
async def mobile_summary(user: dict = Depends(get_current_user)):
    """Compact bundle: my payslip preview, latest payslip, leave balance +
    pending, today's clock, pending approvals for supervisors, and any
    unread notifications. Returns as much as the caller is authorised for."""
    tf = tenant_filter(user)
    eid = user.get("employee_id")

    # Current payslip preview
    payslip_current = None
    payslip_latest = None
    if eid:
        emp = await db.employees.find_one({"id": eid, **tf}, {"_id": 0})
        if emp:
            payslip_current = calc_payslip(emp)
            # Most recent payroll run's slip
            runs = await db.payroll_runs.find(tf, {"_id": 0}).sort(
                "created_at", -1).to_list(1)
            for r in runs:
                slip = next((s for s in r["slips"] if s["employee_id"] == eid), None)
                if slip:
                    payslip_latest = {"run_id": r["id"], "period": r["period"],
                                      "slip": slip}
                    break

    # Leave
    my_leave = []
    pending_reports_leave: list = []
    leave_balance_days = None
    if eid:
        my_leave = await db.leave_requests.find(
            {"employee_id": eid, **tf}, {"_id": 0}).sort(
            "created_at", -1).to_list(10)
        # crude leave balance: annual entitlement 21d/y minus approved this year
        year = now_utc().year
        used = sum(
            lv.get("days", 0)
            for lv in my_leave
            if lv.get("status") == "approved"
            and lv.get("leave_type") in ("annual", "sick") is False
            and (lv.get("start_date") or "").startswith(str(year))
        )
        approved_annual = sum(
            lv.get("days", 0)
            for lv in my_leave
            if lv.get("status") == "approved"
            and lv.get("leave_type") == "annual"
            and (lv.get("start_date") or "").startswith(str(year))
        )
        leave_balance_days = max(0, 21 - approved_annual)
        # Reports pending (any manager)
        reports = await db.employees.find(
            {"manager_id": eid, **tf}, {"_id": 0, "id": 1}).to_list(500)
        r_ids = [r["id"] for r in reports]
        if r_ids:
            pending_reports_leave = await db.leave_requests.find(
                {"employee_id": {"$in": r_ids}, "status": "pending", **tf},
                {"_id": 0}).sort("created_at", -1).to_list(50)

    # Today's clock — attendance rows with kind=clock for today
    today = now_utc().strftime("%Y-%m-%d")
    todays_punches = []
    if eid:
        todays_punches = await db.attendance.find(
            {"employee_id": eid, "date": today, **tf},
            {"_id": 0}).sort("clocked_at", 1).to_list(20)

    # Pending vouchers to approve for supervisors / finance
    voucher_queue: list = []
    if user.get("role") in ("admin", "superadmin", "mof_approver",
                            "finance_officer", "supervisor") or eid:
        # Approvers see relevant vouchers only if their role fits
        role = user.get("role", "employee")
        status_filter = None
        if role == "mof_approver":
            status_filter = "approved"
        elif role == "finance_officer":
            status_filter = "submitted"
        elif role == "supervisor":
            status_filter = "supervisor_pending"
        if status_filter:
            voucher_queue = await db.payroll_vouchers.find(
                {"status": status_filter, **tf},
                {"_id": 0, "id": 1, "voucher_ref": 1, "branch_name": 1,
                 "period": 1, "totals": 1, "status": 1, "created_at": 1}
            ).sort("created_at", 1).to_list(50)

    # Unread notifications (in-app)
    unread = await db.notifications.count_documents(
        {"user_id": user["id"], "read": {"$ne": True}}) if hasattr(
        db, "notifications") else 0

    return {
        "user": {"id": user["id"], "name": user.get("name"),
                 "email": user.get("email"), "role": user.get("role"),
                 "employee_id": eid},
        "payslip_current": payslip_current,
        "payslip_latest": payslip_latest,
        "leave_balance_days": leave_balance_days,
        "my_leave": my_leave,
        "pending_reports_leave": pending_reports_leave,
        "todays_punches": todays_punches,
        "voucher_queue": voucher_queue,
        "unread_notifications": unread,
        "server_time": iso(now_utc()),
    }


# ---------------------------------------------------------------------------
# Geo-tagged clock in/out — a specialised attendance flavour that records
# a punch pair (kind='in'/'out') with WGS-84 lat/lng and a distance-to-branch
# guard so admins can spot punches from the wrong location.
# ---------------------------------------------------------------------------
class PunchIn(BaseModel):
    kind: str = Field(pattern=r"^(in|out)$")
    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy_m: Optional[float] = None
    device_id: Optional[str] = None
    notes: Optional[str] = None


DEFAULT_GEOFENCE_M = 250.0


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


@router.post("/punch")
async def punch(body: PunchIn, user: dict = Depends(get_current_user)):
    eid = user.get("employee_id")
    if not eid:
        raise HTTPException(400, "You are not linked to an employee record")
    emp = await db.employees.find_one(
        {"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")
    today = now_utc().strftime("%Y-%m-%d")

    # Idempotency guard — offline queue replays (multiple drain passes /
    # BackgroundSync restarts) can resend the same punch. A same-kind punch
    # within 15s is a duplicate: return the existing row instead of inserting.
    dup = await db.attendance.find_one({
        "employee_id": eid, "date": today, "kind": body.kind,
        "clocked_at": {"$gte": iso(now_utc() - timedelta(seconds=15))},
        **tenant_filter(user),
    }, {"_id": 0}, sort=[("clocked_at", -1)])
    if dup:
        return dup

    # Compute distance-to-branch if branch has coords + punch has coords.
    distance_m: Optional[float] = None
    branch = None
    if emp.get("branch_id"):
        branch = await db.branches.find_one(
            {"id": emp["branch_id"]},
            {"_id": 0, "id": 1, "name": 1, "lat": 1, "lng": 1,
             "geofence_radius_m": 1, "supervisor_user_id": 1})
    if branch and branch.get("lat") is not None and body.lat is not None:
        distance_m = _haversine_m(branch["lat"], branch["lng"], body.lat, body.lng)
    geofence_m = (branch or {}).get("geofence_radius_m") or DEFAULT_GEOFENCE_M
    in_zone: Optional[bool] = None if distance_m is None else (distance_m <= geofence_m)

    doc = with_tenant({
        "id": str(uuid.uuid4()),
        "employee_id": eid,
        "employee_name": f"{emp.get('first_name','')} {emp.get('last_name','')}".strip(),
        "date": today,
        "clocked_at": iso(now_utc()),
        "kind": body.kind,
        "lat": body.lat, "lng": body.lng,
        "accuracy_m": body.accuracy_m,
        "distance_from_branch_m": (round(distance_m, 1)
                                   if distance_m is not None else None),
        "in_zone": in_zone,
        "branch_id": emp.get("branch_id"),
        "branch_name": branch.get("name") if branch else None,
        "device_id": (body.device_id or "")[:64],
        "notes": (body.notes or "")[:160],
        # keep back-compat with the /attendance list endpoint
        "hours": 0.0, "overtime_hours": 0.0,
        "created_at": iso(now_utc()),
    }, user)
    await db.attendance.insert_one(doc)
    doc.pop("_id", None)

    # If this is a clock-out, pair it with the earliest matching clock-in
    # today and compute worked hours on that in-punch (finance uses in-punch as
    # the anchor row for daily totals).
    if body.kind == "out":
        first_in = await db.attendance.find_one({
            "employee_id": eid, "date": today, "kind": "in",
            **tenant_filter(user),
        }, {"_id": 0}, sort=[("clocked_at", 1)])
        if first_in and first_in.get("clocked_at"):
            t_in = datetime.fromisoformat(first_in["clocked_at"])
            t_out = datetime.fromisoformat(doc["clocked_at"])
            hours = max(0.0, (t_out - t_in).total_seconds() / 3600.0)
            await db.attendance.update_one(
                {"id": first_in["id"]},
                {"$set": {"hours": round(hours, 2),
                          "paired_out_id": doc["id"],
                          "paired_out_at": doc["clocked_at"]}},
            )

    await audit("mobile_punch", f"attendance/{doc['id']}", user, {
        "kind": body.kind, "date": today,
        "distance_m": doc["distance_from_branch_m"],
    })

    # Out-of-zone → alert supervisor (push+SMS) and tenant admins (push),
    # unless an active snooze rule (approved field assignment) suppresses it.
    if in_zone is False:
        import asyncio
        from ooz_alerts import fire_out_of_zone_alert
        snooze = await db.ooz_snoozes.find_one({
            "company_id": doc["company_id"], "employee_id": eid,
            "start_date": {"$lte": today}, "end_date": {"$gte": today},
        }, {"_id": 0})
        asyncio.create_task(fire_out_of_zone_alert(doc, branch, doc["company_id"], snooze=snooze))

    return doc


@router.post("/ooz-digest/run-now")
async def ooz_digest_run_now(user: dict = Depends(get_current_user)):
    """Manually trigger today's out-of-zone email digest for my tenant (admin)."""
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    from ooz_alerts import run_digest_now
    return await run_digest_now(user["company_id"])


@router.get("/ooz-alerts")
async def list_ooz_alerts(date: Optional[str] = None,
                          user: dict = Depends(get_current_user)):
    """Today's (or a given day's) out-of-zone alert log — admins only."""
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    day = date or now_utc().strftime("%Y-%m-%d")
    return await db.ooz_alerts.find(
        {"company_id": user["company_id"], "date": day},
        {"_id": 0}).sort("clocked_at", 1).to_list(500)


# ---------------------------------------------------------------------------
# Alert snooze rules — mute out-of-zone notifications for approved field work.
# ---------------------------------------------------------------------------
class SnoozeIn(BaseModel):
    employee_id: str
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: str = Field(..., min_length=3, max_length=200)


class SnoozePatch(BaseModel):
    start_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: Optional[str] = Field(default=None, min_length=3, max_length=200)


def _with_active(row: dict) -> dict:
    today = now_utc().strftime("%Y-%m-%d")
    row["active"] = row["start_date"] <= today <= row["end_date"]
    return row


@router.post("/ooz-snoozes")
async def create_snooze(body: SnoozeIn, user: dict = Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    if body.end_date < body.start_date:
        raise HTTPException(422, "end_date is before start_date")
    emp = await db.employees.find_one(
        {"id": body.employee_id, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")
    doc = {
        "id": str(uuid.uuid4()), "company_id": user["company_id"],
        "employee_id": emp["id"],
        "employee_name": f"{emp.get('first_name','')} {emp.get('last_name','')}".strip(),
        "start_date": body.start_date, "end_date": body.end_date,
        "reason": body.reason.strip(),
        "created_by": user["email"], "created_at": iso(now_utc()),
    }
    await db.ooz_snoozes.insert_one(doc)
    doc.pop("_id", None)
    await audit("ooz_snooze_created", f"ooz_snoozes/{doc['id']}", user,
                {"employee": doc["employee_name"], "range": f"{doc['start_date']}..{doc['end_date']}"})
    return _with_active(doc)


@router.get("/ooz-snoozes")
async def list_snoozes(user: dict = Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    rows = await db.ooz_snoozes.find(
        tenant_filter(user), {"_id": 0}).sort("created_at", -1).to_list(500)
    return [_with_active(r) for r in rows]


@router.patch("/ooz-snoozes/{sid}")
async def update_snooze(sid: str, body: SnoozePatch, user: dict = Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    doc = await db.ooz_snoozes.find_one({"id": sid, **tenant_filter(user)}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Snooze rule not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(422, "Nothing to update")
    if updates.get("end_date", doc["end_date"]) < updates.get("start_date", doc["start_date"]):
        raise HTTPException(422, "end_date is before start_date")
    if "reason" in updates:
        updates["reason"] = updates["reason"].strip()
    await db.ooz_snoozes.update_one({"id": sid}, {"$set": updates})
    return _with_active({**doc, **updates})


@router.delete("/ooz-snoozes/{sid}")
async def delete_snooze(sid: str, user: dict = Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(403, "Admins only")
    r = await db.ooz_snoozes.delete_one({"id": sid, **tenant_filter(user)})
    if r.deleted_count == 0:
        raise HTTPException(404, "Snooze rule not found")
    await audit("ooz_snooze_deleted", f"ooz_snoozes/{sid}", user, {})
    return {"ok": True}


@router.get("/punch/today")
async def todays_punches(user: dict = Depends(get_current_user)):
    if not user.get("employee_id"):
        return []
    today = now_utc().strftime("%Y-%m-%d")
    return await db.attendance.find(
        {"employee_id": user["employee_id"], "date": today,
         **tenant_filter(user)},
        {"_id": 0}).sort("clocked_at", 1).to_list(20)


# ---------------------------------------------------------------------------
# Team punch map — supervisors see their branches' GPS punches; admins see all.
# ---------------------------------------------------------------------------
async def _team_branches(user: dict):
    """Branches visible on the team map, or None when the user has no access."""
    tf = tenant_filter(user)
    if is_admin(user):
        return await db.branches.find(tf, {"_id": 0}).to_list(200)
    rows = await db.branches.find(
        {**tf, "supervisor_user_id": user["id"]}, {"_id": 0}).to_list(200)
    return rows or None


async def _team_data(user: dict, day: str, employee_id: Optional[str]) -> dict:
    branches = await _team_branches(user)
    if branches is None:
        raise HTTPException(403, "Supervisors and admins only")
    q = {**tenant_filter(user), "date": day, "kind": {"$in": ["in", "out"]}}
    if not is_admin(user):
        q["branch_id"] = {"$in": [b["id"] for b in branches]}
    if employee_id:
        q["employee_id"] = employee_id
    rows = await db.attendance.find(q, {"_id": 0}).sort("clocked_at", 1).to_list(2000)

    bmap = {b["id"]: b for b in branches}
    punches = []
    stats = {"total": 0, "in_zone": 0, "out_zone": 0, "no_gps": 0}
    for p in rows:
        b = bmap.get(p.get("branch_id"))
        dist = p.get("distance_from_branch_m")
        if dist is None and b and b.get("lat") is not None and p.get("lat") is not None:
            dist = round(_haversine_m(b["lat"], b["lng"], p["lat"], p["lng"]), 1)
        radius = (b or {}).get("geofence_radius_m") or DEFAULT_GEOFENCE_M
        in_zone = None
        if p.get("lat") is None or dist is None:
            stats["no_gps"] += 1
        else:
            in_zone = dist <= radius
            stats["in_zone" if in_zone else "out_zone"] += 1
        stats["total"] += 1
        punches.append({
            "id": p["id"], "employee_id": p.get("employee_id"),
            "employee_name": p.get("employee_name"),
            "kind": p.get("kind"), "clocked_at": p.get("clocked_at"),
            "lat": p.get("lat"), "lng": p.get("lng"),
            "accuracy_m": p.get("accuracy_m"),
            "distance_from_branch_m": dist,
            "geofence_radius_m": radius,
            "in_zone": in_zone,
            "branch_id": p.get("branch_id"),
            "branch_name": p.get("branch_name") or (b or {}).get("name"),
        })
    return {
        "date": day,
        "branches": [{"id": b["id"], "code": b.get("code"), "name": b.get("name"),
                      "lat": b.get("lat"), "lng": b.get("lng"),
                      "geofence_radius_m": b.get("geofence_radius_m") or DEFAULT_GEOFENCE_M}
                     for b in branches],
        "punches": punches,
        "stats": stats,
    }


@router.get("/punch/team")
async def team_punches(date: Optional[str] = None, employee_id: Optional[str] = None,
                       user: dict = Depends(get_current_user)):
    day = date or now_utc().strftime("%Y-%m-%d")
    return await _team_data(user, day, employee_id)


@router.get("/punch/team.csv")
async def team_punches_csv(date: Optional[str] = None, employee_id: Optional[str] = None,
                           user: dict = Depends(get_current_user)):
    import csv as _csv
    import io as _io
    from fastapi.responses import StreamingResponse
    day = date or now_utc().strftime("%Y-%m-%d")
    data = await _team_data(user, day, employee_id)
    buf = _io.StringIO()
    w = _csv.writer(buf)
    w.writerow(["employee", "kind", "clocked_at", "branch", "lat", "lng",
                "accuracy_m", "distance_from_branch_m", "geofence_radius_m", "zone"])
    for p in data["punches"]:
        zone = "in_zone" if p["in_zone"] else ("out_of_zone" if p["in_zone"] is False else "no_gps")
        w.writerow([p["employee_name"], p["kind"], p["clocked_at"], p["branch_name"],
                    p["lat"], p["lng"], p["accuracy_m"],
                    p["distance_from_branch_m"], p["geofence_radius_m"], zone])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=punch-map-{day}.csv"})
