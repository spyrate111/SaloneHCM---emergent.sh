"""Compliance Score — 0-100 governance health for Gov-tier customers.

Aggregates four dimensions:
  · payroll_timeliness  — did NRA PAYE land before the 15th of the following month?
  · nassit_accuracy     — do payroll runs sum to exactly 5%+10% of basic?
  · sms_delivery        — % SMS sent successfully in last 30d (only counted if Gov tier)
  · audit_coverage      — audit-log entries per active day in last 30d
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from core import db, tenant_filter

# Weights sum to 100. Tunable per tier later.
WEIGHTS = {
    "payroll_timeliness": 25,
    "nassit_accuracy": 30,
    "sms_delivery": 20,
    "audit_coverage": 25,
}


def _grade(score: float) -> str:
    if score >= 95:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


async def _payroll_timeliness(tf: dict) -> dict:
    """Each payroll run scores 100 if created by 15th of (period_month+1), else penalised."""
    runs = await db.payroll_runs.find(tf, {"_id": 0}).sort("created_at", -1).to_list(12)
    if not runs:
        return {"score": 0, "filed_on_time": 0, "total_runs": 0, "note": "No payroll runs yet."}
    on_time = 0
    for r in runs:
        py, pm = r.get("period_year"), r.get("period_month")
        if not py or not pm:
            continue
        # Filing deadline: 15th of following month
        deadline = datetime(py + (1 if pm == 12 else 0), 1 if pm == 12 else pm + 1, 15, tzinfo=timezone.utc)
        created_at = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        if created_at <= deadline:
            on_time += 1
    score = round(on_time / len(runs) * 100)
    return {
        "score": score,
        "filed_on_time": on_time,
        "total_runs": len(runs),
        "note": f"{on_time} of {len(runs)} runs filed by NRA 15th deadline.",
    }


async def _nassit_accuracy(tf: dict) -> dict:
    """For each payroll slip, verify NASSIT employee = 5% basic and employer = 10% basic (±SLE 1)."""
    runs = await db.payroll_runs.find(tf, {"_id": 0}).sort("created_at", -1).to_list(6)
    if not runs:
        return {"score": 0, "passing_slips": 0, "total_slips": 0, "note": "No payroll runs yet."}
    passing = 0
    total = 0
    for r in runs:
        for s in r["slips"]:
            total += 1
            basic = s.get("basic", 0)
            expected_emp = round(basic * 0.05, 2)
            expected_er = round(basic * 0.10, 2)
            if (abs(s.get("nassit_employee", 0) - expected_emp) <= 1.0
                    and abs(s.get("nassit_employer", 0) - expected_er) <= 1.0):
                passing += 1
    score = round(passing / total * 100) if total else 0
    return {
        "score": score,
        "passing_slips": passing,
        "total_slips": total,
        "note": f"{passing} of {total} payslips match required NASSIT formulae.",
    }


async def _sms_delivery(tf: dict, gov_tier: bool) -> dict:
    """% SMS sent successfully in last 30d. Skipped + dry_run rows excluded from denominator."""
    if not gov_tier:
        return {"score": None, "note": "SMS delivery is a Gov-tier metric.", "applicable": False}
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    pipeline = [
        {"$match": {**tf, "sent_at": {"$gte": since}, "dry_run": False}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    counts: dict[str, int] = defaultdict(int)
    async for r in db.sms_logs.aggregate(pipeline):
        counts[r["_id"]] = r["count"]
    sent = counts.get("sent", 0)
    failed = counts.get("failed", 0)
    attempted = sent + failed
    if attempted == 0:
        return {"score": 100, "sent": 0, "failed": 0,
                "note": "No live SMS sends in last 30 days (no penalty).", "applicable": True}
    score = round(sent / attempted * 100)
    return {
        "score": score,
        "sent": sent,
        "failed": failed,
        "note": f"{sent} delivered, {failed} failed in last 30 days.",
        "applicable": True,
    }


async def _audit_coverage(tf: dict) -> dict:
    """≥ 1 audit entry per active business day in last 30 days = full score."""
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    pipeline = [
        {"$match": {**tf, "ts": {"$gte": since}}},
        {"$group": {"_id": {"$substr": ["$ts", 0, 10]}, "count": {"$sum": 1}}},
    ]
    days_with_activity = 0
    async for _ in db.audit_logs.aggregate(pipeline):
        days_with_activity += 1
    # Target: 21 business days in 30 (5/7 * 30)
    target = 21
    score = round(min(days_with_activity / target, 1.0) * 100)
    return {
        "score": score,
        "active_days": days_with_activity,
        "target_days": target,
        "note": f"Audit activity on {days_with_activity} of last {target} expected business days.",
    }


async def compute(user: dict) -> dict:
    tf = tenant_filter(user)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    gov_tier = company and "bulk_sms_payslips" in (company.get("features") or [])

    parts = {
        "payroll_timeliness": await _payroll_timeliness(tf),
        "nassit_accuracy": await _nassit_accuracy(tf),
        "sms_delivery": await _sms_delivery(tf, bool(gov_tier)),
        "audit_coverage": await _audit_coverage(tf),
    }

    # Weighted average — drop non-applicable dimensions
    total_weight = 0
    weighted_sum = 0
    for k, p in parts.items():
        if p.get("applicable") is False:
            continue
        total_weight += WEIGHTS[k]
        weighted_sum += WEIGHTS[k] * p["score"]
    overall = round(weighted_sum / total_weight) if total_weight else 0
    return {
        "score": overall,
        "grade": _grade(overall),
        "breakdown": parts,
        "weights": WEIGHTS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
