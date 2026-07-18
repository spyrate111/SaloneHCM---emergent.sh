"""Payroll endpoints: preview, run, history, payslip PDF, bank file CSV, my-payslips."""
import io
import csv
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core import db, get_current_user, require_admin, audit, tenant_filter, require_feature
from models import PayrollRunIn
from payroll_engine import calc_payslip, run_payroll as _run, build_payslip_pdf
from sms import send_payslip_batch, is_configured as sms_is_configured

router = APIRouter(prefix="/payroll", tags=["payroll"])


class SendSmsIn(BaseModel):
    dry_run: bool = False


@router.post("/preview")
async def preview_payroll(user: dict = Depends(require_admin)):
    emps = await db.employees.find(
        {"status": "active", **tenant_filter(user)},
        {"_id": 0},
    ).to_list(2000)
    slips = [calc_payslip(e) for e in emps]
    totals = {
        "employee_count": len(slips),
        "gross": round(sum(s["gross"] for s in slips), 2),
        "nassit_employee": round(sum(s["nassit_employee"] for s in slips), 2),
        "nassit_employer": round(sum(s["nassit_employer"] for s in slips), 2),
        "paye": round(sum(s["paye"] for s in slips), 2),
        "net": round(sum(s["net"] for s in slips), 2),
    }
    return {"slips": slips, "totals": totals}


@router.post("/run")
async def run_payroll(body: PayrollRunIn, user: dict = Depends(require_admin)):
    """Run payroll for the given period.

    Guardrail (Gov tier only): re-runs the pre-payroll budget check against
    IFMIS allocations. Blocks unsafe verdicts unless an existing check has an
    active override signed by an mof_approver or superadmin.
    """
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0, "features": 1, "tier": 1}) or {}
    features = company.get("features") or []
    if "gov_payroll" in features:
        period = f"{body.period_year}-{body.period_month:02d}"
        # Look up the most recent budget check for this period.
        latest = await db.payroll_budget_checks.find_one(
            {"company_id": user["company_id"], "period": period},
            {"_id": 0}, sort=[("ran_at", -1)],
        )
        if not latest:
            raise HTTPException(412, {
                "code": "budget_check_missing",
                "message": f"Run a pre-payroll budget check for {period} before executing payroll.",
                "period": period,
            })
        if latest["verdict"] != "safe" and not latest.get("override"):
            raise HTTPException(412, {
                "code": "budget_check_blocked",
                "message": f"Budget check for {period} returned '{latest['verdict']}'. An MoF approver must apply an override before running.",
                "verdict": latest["verdict"],
                "check_id": latest["id"],
                "codes_over": latest["totals"]["codes_over"],
                "unallocated_headcount": latest["totals"]["unallocated_headcount"],
            })
        # Passed — carry the check_id into the run for provenance.
        result = await _run(body.period_year, body.period_month, user)
        override_used = bool(latest.get("override"))
        await db.payroll_runs.update_one(
            {"id": result["id"]},
            {"$set": {"budget_check_id": latest["id"], "budget_override_used": override_used}},
        )
        await db.payroll_budget_checks.update_one(
            {"id": latest["id"]}, {"$set": {"run_id": result["id"]}},
        )
        result["budget_check_id"] = latest["id"]
        result["budget_override_used"] = override_used
        return result

    return await _run(body.period_year, body.period_month, user)


@router.get("/runs")
async def list_runs(user: dict = Depends(get_current_user)):
    return await db.payroll_runs.find(
        tenant_filter(user), {"_id": 0, "slips": 0}).sort("created_at", -1).to_list(500)


@router.get("/runs/{rid}")
async def get_run(rid: str, user: dict = Depends(get_current_user)):
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Not found")
    return r


@router.get("/my-payslip")
async def my_payslip(user: dict = Depends(get_current_user)):
    eid = user.get("employee_id")
    if not eid:
        return {"slip": None}
    e = await db.employees.find_one({"id": eid, **tenant_filter(user)}, {"_id": 0})
    if not e:
        return {"slip": None}
    return {"slip": calc_payslip(e)}


@router.get("/my-payslips")
async def my_payslips(user: dict = Depends(get_current_user)):
    eid = user.get("employee_id")
    if not eid:
        return []
    runs = await db.payroll_runs.find(tenant_filter(user), {"_id": 0}).sort("created_at", -1).to_list(50)
    out = []
    for r in runs:
        slip = next((s for s in r["slips"] if s["employee_id"] == eid), None)
        if slip:
            out.append({"run_id": r["id"], "period": r["period"], "slip": slip})
    return out


@router.get("/runs/{rid}/payslip/{eid}.pdf")
async def payslip_pdf(rid: str, eid: str, user: dict = Depends(get_current_user)):
    if user["role"] not in ("admin", "superadmin") and user.get("employee_id") != eid:
        raise HTTPException(403, "Forbidden")
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    slip = next((s for s in r["slips"] if s["employee_id"] == eid), None)
    if not slip:
        raise HTTPException(404, "Payslip not found")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    pdf = build_payslip_pdf(slip, r["period"], company=company.get("name") if company else "Demo Salone Ltd.")
    fname = f"payslip-{slip['employee_name'].replace(' ', '_')}-{r['period']}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/runs/{rid}/bank-file")
async def bank_file(rid: str, user: dict = Depends(require_admin)):
    """NRC clearing CSV — bank_name, account_no, beneficiary, amount, reference."""
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    emps = await db.employees.find(tenant_filter(user), {"_id": 0}).to_list(2000)
    emp_map = {e["id"]: e for e in emps}
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["bank_name", "account_no", "beneficiary", "amount_sle", "reference"])
    for s in r["slips"]:
        e = emp_map.get(s["employee_id"], {})
        writer.writerow([
            e.get("bank_name", "Sierra Leone Commercial Bank"),
            e.get("bank_account", "0000000000"),
            s["employee_name"],
            f"{s['net']:.2f}",
            f"PAYROLL-{r['period']}",
        ])
    await audit("export_bank_file", f"payroll_runs/{rid}", user,
                {"period": r["period"], "rows": len(r["slips"])})
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="bank-file-{r["period"]}.csv"'},
    )


@router.get("/sms/status")
async def sms_status(_: dict = Depends(require_admin)):
    """Tell the frontend whether Twilio creds are wired so it can warn the admin."""
    return {"twilio_configured": sms_is_configured()}


@router.post("/runs/{rid}/send-sms")
async def send_payslip_sms(
    rid: str,
    body: SendSmsIn,
    user: dict = Depends(require_feature("bulk_sms_payslips")),
):
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin only")
    run = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Payroll run not found")
    employees = await db.employees.find(tenant_filter(user), {"_id": 0}).to_list(2000)
    summary = await send_payslip_batch(run, employees, user, dry_run=body.dry_run)
    await audit(
        "sms_bulk_send",
        f"payroll_runs/{rid}",
        user,
        {
            "period": run["period"],
            "sent": summary["sent"],
            "failed": summary["failed"],
            "skipped": summary["skipped"],
            "dry_run": summary["dry_run"],
            "batch_id": summary["batch_id"],
        },
    )
    return summary


@router.get("/sms/logs")
async def list_sms_logs(
    period: Optional[str] = None,
    status: Optional[str] = None,
    batch_id: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    q: dict = {**tenant_filter(user)}
    if period:
        q["period"] = period
    if status:
        q["status"] = status
    if batch_id:
        q["batch_id"] = batch_id
    rows = await db.sms_logs.find(q, {"_id": 0}).sort("sent_at", -1).to_list(2000)
    return rows


@router.get("/sms/batches")
async def list_sms_batches(user: dict = Depends(require_admin)):
    """Distinct SMS batches with aggregate counts per status — for the audit page header view."""
    pipeline = [
        {"$match": tenant_filter(user)},
        {"$group": {
            "_id": "$batch_id",
            "period": {"$first": "$period"},
            "run_id": {"$first": "$run_id"},
            "sent_by": {"$first": "$sent_by"},
            "sent_at": {"$max": "$sent_at"},
            "dry_run": {"$first": "$dry_run"},
            "total": {"$sum": 1},
            "sent": {"$sum": {"$cond": [{"$eq": ["$status", "sent"]}, 1, 0]}},
            "would_send": {"$sum": {"$cond": [{"$eq": ["$status", "would_send"]}, 1, 0]}},
            "failed": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
            "skipped": {"$sum": {"$cond": [{"$eq": ["$status", "skipped"]}, 1, 0]}},
        }},
        {"$sort": {"sent_at": -1}},
        {"$limit": 200},
    ]
    rows = []
    async for r in db.sms_logs.aggregate(pipeline):
        rows.append({
            "batch_id": r["_id"],
            "period": r.get("period"),
            "run_id": r.get("run_id"),
            "sent_by": r.get("sent_by"),
            "sent_at": r.get("sent_at"),
            "dry_run": r.get("dry_run", False),
            "total": r["total"],
            "sent": r["sent"],
            "would_send": r["would_send"],
            "failed": r["failed"],
            "skipped": r["skipped"],
        })
    return rows


@router.get("/sms/summary")
async def sms_summary(user: dict = Depends(require_admin)):
    """High-level KPIs for the audit page header."""
    tf = tenant_filter(user)
    pipeline = [
        {"$match": tf},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    by_status = {r["_id"]: r["count"] async for r in db.sms_logs.aggregate(pipeline)}
    batch_count = len(await db.sms_logs.distinct("batch_id", tf))
    last = await db.sms_logs.find(tf, {"_id": 0, "sent_at": 1}).sort("sent_at", -1).limit(1).to_list(1)
    return {
        "total_messages": sum(by_status.values()),
        "by_status": by_status,
        "batch_count": batch_count,
        "last_sent_at": last[0]["sent_at"] if last else None,
    }


@router.get("/sms/logs.csv")
async def export_sms_logs_csv(
    period: Optional[str] = None,
    status: Optional[str] = None,
    batch_id: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Forensic CSV export of SMS deliveries — for Auditor General submissions."""
    q: dict = {**tenant_filter(user)}
    if period:
        q["period"] = period
    if status:
        q["status"] = status
    if batch_id:
        q["batch_id"] = batch_id
    rows = await db.sms_logs.find(q, {"_id": 0}).sort("sent_at", -1).to_list(10000)
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "sent_at", "period", "batch_id", "employee_name", "phone", "status",
        "twilio_sid", "reason", "dry_run", "sent_by", "run_id",
    ])
    for r in rows:
        writer.writerow([
            r.get("sent_at", ""),
            r.get("period", ""),
            r.get("batch_id", ""),
            r.get("employee_name", ""),
            r.get("to", ""),
            r.get("status", ""),
            r.get("sid", ""),
            r.get("reason", ""),
            "yes" if r.get("dry_run") else "no",
            r.get("sent_by", ""),
            r.get("run_id", ""),
        ])
    await audit("sms_log_export_csv", "payroll/sms/logs.csv", user, {
        "rows": len(rows),
        "filters": {k: v for k, v in {"period": period, "status": status, "batch_id": batch_id}.items() if v},
    })
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="salonehcm-sms-audit.csv"'},
    )


def _build_sms_csv_bytes(rows: list) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "sent_at", "period", "batch_id", "employee_name", "phone", "status",
        "twilio_sid", "reason", "dry_run", "sent_by", "run_id",
    ])
    for r in rows:
        writer.writerow([
            r.get("sent_at", ""), r.get("period", ""), r.get("batch_id", ""),
            r.get("employee_name", ""), r.get("to", ""), r.get("status", ""),
            r.get("sid", ""), r.get("reason", ""),
            "yes" if r.get("dry_run") else "no",
            r.get("sent_by", ""), r.get("run_id", ""),
        ])
    return buf.getvalue().encode()


class EmailExportIn(BaseModel):
    to: Optional[str] = None  # defaults to caller's own email
    period: Optional[str] = None
    status: Optional[str] = None
    batch_id: Optional[str] = None


@router.post("/sms/logs.csv/email")
async def email_sms_logs_csv(body: EmailExportIn, user: dict = Depends(require_admin)):
    """Email the audit CSV to the requester (or another email)."""
    from email_service import send_csv_attachment, is_configured as _ec
    if not _ec():
        raise HTTPException(503, "Email service not configured")
    q: dict = {**tenant_filter(user)}
    if body.period:
        q["period"] = body.period
    if body.status:
        q["status"] = body.status
    if body.batch_id:
        q["batch_id"] = body.batch_id
    rows = await db.sms_logs.find(q, {"_id": 0}).sort("sent_at", -1).to_list(10000)
    csv_bytes = _build_sms_csv_bytes(rows)
    to = (body.to or user["email"]).strip().lower()
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0, "name": 1})
    res = await send_csv_attachment(
        to=to,
        subject=f"[SaloneHCM] SMS audit log ({len(rows)} rows)",
        title="SMS audit export",
        body_text=(
            f"Attached is your SaloneHCM SMS audit log for "
            f"<strong>{(company or {}).get('name','your company')}</strong>. "
            f"Filters applied: {body.model_dump(exclude={'to'})}. "
            f"Total entries: <strong>{len(rows)}</strong>."
        ),
        csv_bytes=csv_bytes,
        filename=f"salonehcm-sms-audit-{(body.period or 'all')}.csv",
        company_id=user["company_id"],
    )
    await audit("sms_log_email", "payroll/sms/logs.csv/email", user, {"to": to, "rows": len(rows), "ok": res.get("ok")})
    return {**res, "rows": len(rows), "to": to}
