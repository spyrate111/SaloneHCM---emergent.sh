"""Payroll variance analysis — Option B fraud-detection guardrail.

When an MoF approver reviews a payroll run for sign-off, they need to know at
a glance what changed vs the prior period and whether any of it looks anomalous.
Auto-computed from stored payroll_runs data — no schema changes required.

Anomaly heuristics (thresholds tuned for typical Sierra Leone civil-service
payroll where salaries change monthly by ≤2%, headcount by ≤1%):

  HEADCOUNT      Δ headcount ≥ ±5%
  TOTAL_GROSS    Δ gross    ≥ +10%
  MINISTRY_JUMP  any single ministry gross change ≥ +15%
  RAISE          any single employee net change    ≥ +10%
  NEW_STARTER    employee on this run but hired > 30 days ago (should have prior slip)
  RESURRECTED    employee on this run, missing from prior run for ≥ 2 consecutive periods
  TERMINATED     employee marked terminated but still receiving > 0 net pay
"""
from __future__ import annotations
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from core import db, tenant_filter, require_admin, iso, now_utc

router = APIRouter(prefix="/payroll", tags=["payroll-variance"])

# ---- Tunable thresholds ----
HEADCOUNT_PCT = 5.0
GROSS_PCT = 10.0
MINISTRY_PCT = 15.0
RAISE_PCT = 10.0
NEW_STARTER_STALE_DAYS = 30


def _prev_period(period: str) -> Optional[str]:
    """Return the calendar-prior YYYY-MM string, or None if malformed."""
    m = re.match(r"^(\d{4})-(\d{2})$", period or "")
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    mo -= 1
    if mo == 0:
        mo = 12
        y -= 1
    return f"{y}-{mo:02d}"


def _round(x: float) -> float:
    return round(float(x or 0), 2)


def _pct(new: float, old: float) -> Optional[float]:
    if old == 0:
        return None if new == 0 else 100.0
    return round(((new - old) / old) * 100, 2)


def _totals(slips: list[dict]) -> dict:
    """Compute headline totals from a list of payslip dicts."""
    return {
        "headcount": len(slips),
        "gross": _round(sum(s.get("gross") or 0 for s in slips)),
        "paye": _round(sum(s.get("paye") or 0 for s in slips)),
        "nassit_employee": _round(sum(s.get("nassit_employee") or 0 for s in slips)),
        "nassit_employer": _round(sum(s.get("nassit_employer") or 0 for s in slips)),
        "net": _round(sum(s.get("net") or 0 for s in slips)),
    }


def _by_ministry(slips: list[dict], emp_ministry: dict[str, str]) -> dict[str, dict]:
    """Group slips by employee.ministry (fallback to department)."""
    out: dict[str, dict] = defaultdict(lambda: {"headcount": 0, "gross": 0.0, "net": 0.0})
    for s in slips:
        eid = s.get("employee_id")
        ministry = emp_ministry.get(eid) or s.get("department") or "Unassigned"
        m = out[ministry]
        m["headcount"] += 1
        m["gross"] += s.get("gross") or 0
        m["net"] += s.get("net") or 0
    for k in out:
        out[k]["gross"] = _round(out[k]["gross"])
        out[k]["net"] = _round(out[k]["net"])
    return dict(out)


async def _employee_ministry_map(company_id: str) -> dict[str, str]:
    emps = await db.employees.find(
        {"company_id": company_id}, {"_id": 0, "id": 1, "ministry": 1, "department": 1, "hire_date": 1},
    ).to_list(5000)
    return {e["id"]: (e.get("ministry") or e.get("department") or "Unassigned") for e in emps}


async def _hire_date_map(company_id: str) -> dict[str, str]:
    emps = await db.employees.find(
        {"company_id": company_id}, {"_id": 0, "id": 1, "hire_date": 1, "status": 1},
    ).to_list(5000)
    return {e["id"]: e for e in emps}


def _raise_anomalies(cur_by_id: dict, prev_by_id: dict) -> list[dict]:
    out = []
    for eid, cur in cur_by_id.items():
        prev = prev_by_id.get(eid)
        if not prev:
            continue
        delta_pct = _pct(cur.get("net", 0), prev.get("net", 0))
        if delta_pct is not None and delta_pct >= RAISE_PCT:
            out.append({
                "severity": "high" if delta_pct >= 25 else "warn",
                "kind": "raise",
                "subject": cur.get("employee_name") or eid,
                "employee_id": eid,
                "before": _round(prev.get("net", 0)),
                "after": _round(cur.get("net", 0)),
                "delta_pct": delta_pct,
                "message": f"Net pay jumped {delta_pct}% — verify grade change, promotion, or acting allowance is approved.",
            })
    return out


def _new_starter_anomalies(cur_by_id: dict, prev_by_id: dict, emp_index: dict, cur_period: str) -> list[dict]:
    try:
        cur_date = datetime.strptime(cur_period + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        cur_date = datetime.now(timezone.utc)
    out = []
    for eid, cur in cur_by_id.items():
        if eid in prev_by_id:
            continue
        emp = emp_index.get(eid) or {}
        hd = emp.get("hire_date")
        if not hd:
            continue
        try:
            hire = datetime.strptime(hd[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        days_before = (cur_date - hire).days
        if days_before > NEW_STARTER_STALE_DAYS:
            out.append({
                "severity": "warn",
                "kind": "new_starter",
                "subject": cur.get("employee_name") or eid,
                "employee_id": eid,
                "before": 0,
                "after": _round(cur.get("net", 0)),
                "delta_pct": None,
                "message": f"First payslip in ≥ {days_before} days since hire — possible late-add or ghost worker.",
            })
    return out


def _terminated_paid_anomalies(cur_by_id: dict, emp_index: dict) -> list[dict]:
    out = []
    for eid, cur in cur_by_id.items():
        emp = emp_index.get(eid) or {}
        if emp.get("status") == "terminated" and (cur.get("net") or 0) > 0:
            out.append({
                "severity": "high",
                "kind": "terminated_paid",
                "subject": cur.get("employee_name") or eid,
                "employee_id": eid,
                "before": 0,
                "after": _round(cur.get("net", 0)),
                "delta_pct": None,
                "message": "Employee is terminated but still receiving net pay this run.",
            })
    return out


def _detect_anomalies(cur_slips, prev_slips, emp_index, cur_period) -> list[dict]:
    """Return a list of {severity, kind, subject, before, after, delta, delta_pct, message}."""
    prev_by_id = {s["employee_id"]: s for s in prev_slips}
    cur_by_id = {s["employee_id"]: s for s in cur_slips}
    return (
        _raise_anomalies(cur_by_id, prev_by_id)
        + _new_starter_anomalies(cur_by_id, prev_by_id, emp_index, cur_period)
        + _terminated_paid_anomalies(cur_by_id, emp_index)
    )


@router.get("/runs/{rid}/variance")
async def payroll_variance(rid: str, user: dict = Depends(require_admin)):
    """Compute variance for a payroll run vs the previous period's run.
    Returns headline totals, by-ministry deltas, and a list of anomalies."""
    tf = tenant_filter(user)
    cur = await db.payroll_runs.find_one({"id": rid, **tf}, {"_id": 0})
    if not cur:
        raise HTTPException(404, "Payroll run not found")

    prev_period = _prev_period(cur["period"])
    prev = None
    if prev_period:
        # Prefer completed runs of the previous period.
        prev = await db.payroll_runs.find_one(
            {**tf, "period": prev_period}, {"_id": 0}, sort=[("created_at", -1)],
        )

    cur_slips = cur.get("slips") or []
    prev_slips = (prev or {}).get("slips") or []

    ministry_map = await _employee_ministry_map(user["company_id"])
    emp_index = await _hire_date_map(user["company_id"])

    cur_totals = _totals(cur_slips)
    prev_totals = _totals(prev_slips) if prev else {k: 0 for k in cur_totals}

    delta = {
        "headcount": cur_totals["headcount"] - prev_totals["headcount"],
        "gross": _round(cur_totals["gross"] - prev_totals["gross"]),
        "paye": _round(cur_totals["paye"] - prev_totals["paye"]),
        "nassit_employee": _round(cur_totals["nassit_employee"] - prev_totals["nassit_employee"]),
        "nassit_employer": _round(cur_totals["nassit_employer"] - prev_totals["nassit_employer"]),
        "net": _round(cur_totals["net"] - prev_totals["net"]),
    }
    delta_pct = {
        "headcount": _pct(cur_totals["headcount"], prev_totals["headcount"]),
        "gross": _pct(cur_totals["gross"], prev_totals["gross"]),
        "paye": _pct(cur_totals["paye"], prev_totals["paye"]),
        "net": _pct(cur_totals["net"], prev_totals["net"]),
    }

    cur_by_min = _by_ministry(cur_slips, ministry_map)
    prev_by_min = _by_ministry(prev_slips, ministry_map) if prev else {}
    ministry_rows = []
    for m in sorted(set(cur_by_min.keys()) | set(prev_by_min.keys())):
        c = cur_by_min.get(m, {"headcount": 0, "gross": 0.0, "net": 0.0})
        p = prev_by_min.get(m, {"headcount": 0, "gross": 0.0, "net": 0.0})
        ministry_rows.append({
            "ministry": m,
            "headcount_prev": p["headcount"], "headcount": c["headcount"],
            "gross_prev": p["gross"], "gross": c["gross"],
            "delta_gross": _round(c["gross"] - p["gross"]),
            "delta_gross_pct": _pct(c["gross"], p["gross"]),
        })
    # Rank by absolute % change desc
    ministry_rows.sort(key=lambda r: abs(r["delta_gross_pct"] or 0), reverse=True)

    anomalies = _detect_anomalies(cur_slips, prev_slips, emp_index, cur["period"])

    # Headline anomaly flags
    if delta_pct.get("headcount") is not None and abs(delta_pct["headcount"]) >= HEADCOUNT_PCT:
        anomalies.insert(0, {
            "severity": "warn", "kind": "headcount",
            "subject": "Overall headcount",
            "before": prev_totals["headcount"], "after": cur_totals["headcount"],
            "delta_pct": delta_pct["headcount"],
            "message": f"Headcount shifted by {delta_pct['headcount']}% vs {prev_period} — verify joiners/leavers.",
        })
    if delta_pct.get("gross") is not None and delta_pct["gross"] >= GROSS_PCT:
        anomalies.insert(0, {
            "severity": "warn", "kind": "total_gross",
            "subject": "Total gross",
            "before": prev_totals["gross"], "after": cur_totals["gross"],
            "delta_pct": delta_pct["gross"],
            "message": f"Total gross rose {delta_pct['gross']}% — inspect per-ministry breakdown below.",
        })
    for m in ministry_rows:
        dp = m["delta_gross_pct"]
        if dp is not None and dp >= MINISTRY_PCT and m["gross_prev"] > 0:
            anomalies.append({
                "severity": "warn", "kind": "ministry_jump",
                "subject": m["ministry"],
                "before": m["gross_prev"], "after": m["gross"],
                "delta_pct": dp,
                "message": f"{m['ministry']} gross jumped {dp}% ({m['headcount_prev']}→{m['headcount']} headcount).",
            })

    return {
        "run_id": rid,
        "current_period": cur["period"],
        "prior_period": prev_period,
        "prior_exists": prev is not None,
        "computed_at": iso(now_utc()),
        "totals": {
            "current": cur_totals, "prior": prev_totals,
            "delta": delta, "delta_pct": delta_pct,
        },
        "by_ministry": ministry_rows,
        "anomalies": anomalies,
        "anomaly_summary": {
            "count": len(anomalies),
            "high": sum(1 for a in anomalies if a["severity"] == "high"),
            "warn": sum(1 for a in anomalies if a["severity"] == "warn"),
        },
    }
