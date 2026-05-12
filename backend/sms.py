"""Twilio SMS service — bulk payslip notification sends with per-recipient tracking."""
import asyncio
import logging
import os
import re
import uuid
from typing import Optional

from core import db, now_utc, iso

logger = logging.getLogger("salonehcm.sms")

ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")

# E.164 — `+` followed by 8-15 digits
E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")

# Bound concurrency to keep Twilio happy + avoid hitting rate-limits in bulk runs.
SEND_CONCURRENCY = 8


def is_configured() -> bool:
    return bool(ACCOUNT_SID and AUTH_TOKEN and FROM_NUMBER)


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """Convert '+232 76 000 000' → '+23276000000'. Return None if invalid."""
    if not raw:
        return None
    digits = re.sub(r"[^\d+]", "", raw)
    if not digits.startswith("+"):
        return None
    return digits if E164_PATTERN.match(digits) else None


def _get_client():
    """Lazy import + lazy client — never crash app startup when creds are missing."""
    from twilio.rest import Client
    return Client(ACCOUNT_SID, AUTH_TOKEN)


def _send_one_sync(to: str, body: str) -> dict:
    """Sync Twilio call — runs in a thread via asyncio.to_thread."""
    client = _get_client()
    msg = client.messages.create(to=to, from_=FROM_NUMBER, body=body)
    return {"sid": msg.sid, "status": msg.status}


async def send_one(to: str, body: str) -> dict:
    """Async wrapper. Returns {ok, sid, status, error?}."""
    try:
        info = await asyncio.to_thread(_send_one_sync, to, body)
        return {"ok": True, **info}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _format_payslip_sms(employee_name: str, period: str, net: float) -> str:
    first = employee_name.split(" ")[0] if employee_name else "there"
    return (
        f"SaloneHCM: Hi {first}, your payslip for {period} is ready. "
        f"Net pay: SLE {net:,.2f}. Log in to view full payslip."
    )


async def send_payslip_batch(
    run: dict,
    employees: list[dict],
    user: dict,
    dry_run: bool = False,
) -> dict:
    """Send a payslip-ready SMS to each employee. Records every attempt in sms_logs."""
    emp_by_id = {e["id"]: e for e in employees}
    period = run["period"]

    # Build (employee_id, phone, message) tuples, classifying skips
    plan: list[dict] = []
    for slip in run["slips"]:
        emp = emp_by_id.get(slip["employee_id"])
        if not emp:
            plan.append({"employee_id": slip["employee_id"], "name": slip["employee_name"],
                         "status": "skipped", "reason": "employee not found"})
            continue
        phone = normalize_phone(emp.get("phone"))
        if not phone:
            plan.append({"employee_id": emp["id"], "name": slip["employee_name"],
                         "phone": emp.get("phone"), "status": "skipped",
                         "reason": "invalid or missing phone number"})
            continue
        plan.append({
            "employee_id": emp["id"],
            "name": slip["employee_name"],
            "phone": phone,
            "body": _format_payslip_sms(slip["employee_name"], period, slip["net"]),
            "status": "ready",
        })

    sendables = [p for p in plan if p["status"] == "ready"]

    # Dry run — record planned messages but don't hit Twilio
    if dry_run or not is_configured():
        reason = "dry_run" if dry_run else "twilio_not_configured"
        for p in sendables:
            p["status"] = "would_send"
            p["reason"] = reason

    else:
        sem = asyncio.Semaphore(SEND_CONCURRENCY)

        async def _do(p):
            async with sem:
                res = await send_one(p["phone"], p["body"])
            if res["ok"]:
                p["status"] = "sent"
                p["sid"] = res["sid"]
                p["twilio_status"] = res["status"]
            else:
                p["status"] = "failed"
                p["reason"] = res["error"]

        await asyncio.gather(*[_do(p) for p in sendables])

    # Persist every entry as a SMS log
    batch_id = str(uuid.uuid4())
    log_docs = []
    for p in plan:
        log_docs.append({
            "id": str(uuid.uuid4()),
            "company_id": user["company_id"],
            "batch_id": batch_id,
            "run_id": run["id"],
            "period": period,
            "employee_id": p.get("employee_id"),
            "employee_name": p.get("name"),
            "to": p.get("phone"),
            "body_preview": (p.get("body") or "")[:160],
            "status": p["status"],
            "sid": p.get("sid"),
            "reason": p.get("reason"),
            "sent_by": user["email"],
            "sent_at": iso(now_utc()),
            "dry_run": dry_run or not is_configured(),
        })
    if log_docs:
        await db.sms_logs.insert_many(log_docs)

    summary = {
        "batch_id": batch_id,
        "sent": sum(1 for p in plan if p["status"] == "sent"),
        "would_send": sum(1 for p in plan if p["status"] == "would_send"),
        "failed": sum(1 for p in plan if p["status"] == "failed"),
        "skipped": sum(1 for p in plan if p["status"] == "skipped"),
        "total": len(plan),
        "dry_run": dry_run or not is_configured(),
        "twilio_configured": is_configured(),
        "results": plan,
    }
    return summary
