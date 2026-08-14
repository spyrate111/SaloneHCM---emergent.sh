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
            {"id": emp["branch_id"]}, {"_id": 0, "id": 1, "name": 1, "lat": 1, "lng": 1})
    if branch and branch.get("lat") is not None and body.lat is not None:
        # Haversine (metres)
        import math
        R = 6371000.0
        dlat = math.radians(body.lat - branch["lat"])
        dlng = math.radians(body.lng - branch["lng"])
        a = (math.sin(dlat / 2) ** 2
             + math.cos(math.radians(branch["lat"])) *
             math.cos(math.radians(body.lat)) * math.sin(dlng / 2) ** 2)
        distance_m = 2 * R * math.asin(math.sqrt(a))

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
    return doc


@router.get("/punch/today")
async def todays_punches(user: dict = Depends(get_current_user)):
    if not user.get("employee_id"):
        return []
    today = now_utc().strftime("%Y-%m-%d")
    return await db.attendance.find(
        {"employee_id": user["employee_id"], "date": today,
         **tenant_filter(user)},
        {"_id": 0}).sort("clocked_at", 1).to_list(20)
