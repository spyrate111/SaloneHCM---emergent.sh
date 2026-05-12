"""Payroll endpoints: preview, run, history, payslip PDF, bank file CSV, my-payslips."""
import io
import csv
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
    return await _run(body.period_year, body.period_month, user)


@router.get("/runs")
async def list_runs(user: dict = Depends(get_current_user)):
    return await db.payroll_runs.find(tenant_filter(user), {"_id": 0}).sort("created_at", -1).to_list(500)


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
async def list_sms_logs(user: dict = Depends(require_admin)):
    rows = await db.sms_logs.find(
        tenant_filter(user), {"_id": 0}
    ).sort("sent_at", -1).to_list(500)
    return rows
