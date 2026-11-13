"""Compliance & Tax endpoints — incl. NRA PAYE return + NASSIT schedule exports."""
import io
import csv
import zipfile
from xml.sax.saxutils import escape as xml_escape
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import db, get_current_user, require_admin, audit, tenant_filter, require_feature
from payroll_engine import PAYE_BANDS, NASSIT_EMPLOYEE, NASSIT_EMPLOYER

from core import require_roles, can_role

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _build_nra_csv(run: dict, employees: list, company: dict) -> bytes:
    emp_map = {e["id"]: e for e in employees}
    period = run["period"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["NRA PAYE RETURN"])
    w.writerow(["Period", period])
    w.writerow(["Employer TIN", (company or {}).get("tin", "")])
    w.writerow(["Employer Name", (company or {}).get("name", "")])
    w.writerow([])
    w.writerow([
        "tin", "employee_name", "nassit_no", "department",
        "gross_sle", "taxable_sle", "paye_sle",
        "nassit_employee_sle", "nassit_employer_sle", "net_sle",
    ])
    for s in run["slips"]:
        emp = emp_map.get(s["employee_id"], {})
        taxable = round(s["gross"] - s["nassit_employee"], 2)
        w.writerow([
            _payroll_identity_value(s, "employee_tin", emp, "tin"),
            s["employee_name"],
            _payroll_identity_value(s, "employee_nassit_no", emp, "nassit_no"),
            _payroll_identity_value(s, "employee_department", emp, "department"),
            f'{s["gross"]:.2f}', f'{taxable:.2f}',
            f'{s["paye"]:.2f}', f'{s["nassit_employee"]:.2f}',
            f'{s["nassit_employer"]:.2f}', f'{s["net"]:.2f}',
        ])
    t = run["totals"]
    w.writerow([])
    w.writerow(["TOTAL", "", "", "",
                f'{t["gross"]:.2f}', f'{t["gross"] - t["nassit_employee"]:.2f}',
                f'{t["paye"]:.2f}', f'{t["nassit_employee"]:.2f}',
                f'{t["nassit_employer"]:.2f}', f'{t["net"]:.2f}'])
    return buf.getvalue().encode()




def _xml_safe_text(value) -> str:
    """Escape text for an OOXML inline string and remove invalid XML control chars."""
    text = str(value if value is not None else "")
    text = "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)
    return xml_escape(text)


def _payroll_identity_value(slip: dict, snapshot_key: str, employee: dict, current_key: str):
    """Use run-time identity when present; only older runs fall back to current profiles."""
    if snapshot_key in slip:
        return slip.get(snapshot_key) or ""
    return employee.get(current_key, "")


def _require_completed_run(run: dict) -> None:
    if run.get("status") != "completed":
        raise HTTPException(409, "Complete the payroll run before preparing or filing compliance workpapers.")


async def _employees_for_payroll_run(run: dict, user: dict) -> list:
    """Load only employees in this payroll run without truncating large establishments."""
    employee_ids = list({
        slip.get("employee_id") for slip in run.get("slips", [])
        if slip.get("employee_id")
    })
    if not employee_ids:
        return []
    return await db.employees.find(
        {"id": {"$in": employee_ids}, **tenant_filter(user)}, {"_id": 0},
    ).to_list(len(employee_ids))


def _build_nassit_xlsx(run: dict, employees: list, company: dict) -> bytes:
    """Build a one-sheet Excel contribution schedule using NASSIT's published fields."""
    emp_map = {e["id"]: e for e in employees}
    rows = [
        ["Name of Employer", company.get("name", "")],
        ["ER Number", company.get("nassit_employer", "")],
        ["Payment Period", run["period"]],
        ["Address of Employer", company.get("address", "")],
        [],
        [
            "No.", "Surname", "First Name", "Other Name(s)", "SS Number",
            "Basic Salary (Le)", "10% (Le)", "5% (Le)", "15% (Le)",
        ],
    ]
    totals = {"basic": 0.0, "employer": 0.0, "employee": 0.0, "total": 0.0}
    for index, slip in enumerate(run["slips"], start=1):
        employee = emp_map.get(slip["employee_id"], {})
        basic = float(slip.get("basic", 0) or 0)
        employee_share = float(slip.get("nassit_employee", 0) or 0)
        employer_share = float(slip.get("nassit_employer", 0) or 0)
        total_share = round(employee_share + employer_share, 2)
        totals["basic"] += basic
        totals["employee"] += employee_share
        totals["employer"] += employer_share
        totals["total"] += total_share
        rows.append([
            index,
            _payroll_identity_value(slip, "employee_last_name", employee, "last_name"),
            _payroll_identity_value(slip, "employee_first_name", employee, "first_name"),
            _payroll_identity_value(slip, "employee_middle_name", employee, "middle_name"),
            _payroll_identity_value(slip, "employee_nassit_no", employee, "nassit_no"),
            basic,
            employer_share,
            employee_share,
            total_share,
        ])
    rows.extend([
        [],
        [
            "TOTAL", "", "", "", "",
            round(totals["basic"], 2),
            round(totals["employer"], 2),
            round(totals["employee"], 2),
            round(totals["total"], 2),
        ],
    ])

    def column_name(number: int) -> str:
        name = ""
        while number:
            number, remainder = divmod(number - 1, 26)
            name = chr(65 + remainder) + name
        return name

    worksheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for col_number, value in enumerate(row, start=1):
            if value is None or value == "":
                continue
            cell_ref = f"{column_name(col_number)}{row_number}"
            if isinstance(value, (int, float)):
                cell_value = f"{float(value):.2f}" if isinstance(value, float) else str(value)
                cells.append(f'<c r="{cell_ref}" t="n"><v>{cell_value}</v></c>')
            else:
                cells.append(
                    f'<c r="{cell_ref}" t="inlineStr"><is><t xml:space="preserve">'
                    f'{_xml_safe_text(value)}</t></is></c>'
                )
        worksheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="6" topLeftCell="A7" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<sheetData>{"".join(worksheet_rows)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Contribution Schedule" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )
    package_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml)
        workbook.writestr("_rels/.rels", package_rels_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


@router.get("/summary")
async def compliance_summary(user: dict = Depends(require_roles("payroll", "auditor"))):
    tf = tenant_filter(user)
    all_runs = await db.payroll_runs.find(tf, {"_id": 0}).sort("created_at", -1).to_list(500)
    # A rerun replaces the earlier run for the same pay period in reporting.
    latest_by_period = {}
    for run in all_runs:
        if run.get("status") == "completed" and run.get("period"):
            latest_by_period.setdefault(run["period"], run)
    latest_runs = list(latest_by_period.values())[:50]

    reporting_year = datetime.now(timezone.utc).year
    year_runs = [
        run for period, run in latest_by_period.items()
        if period.startswith(f"{reporting_year}-")
    ]
    total_paye = sum(float(r.get("totals", {}).get("paye", 0)) for r in year_runs)
    total_nassit = sum(
        float(r.get("totals", {}).get("nassit_employee", 0))
        + float(r.get("totals", {}).get("nassit_employer", 0))
        for r in year_runs
    )

    # NRA filing status is tied to the current payroll run for each period.
    filings = await db.nra_filings.find(tf, {"_id": 0}).sort("filed_at", -1).to_list(500)
    filed_runs = {}
    for filing in filings:
        run_id = filing.get("run_id")
        if run_id and run_id not in filed_runs:
            filed_runs[run_id] = filing
    history = [
        {
            "run_id": r["id"],
            "period": r["period"],
            "paye": r["totals"]["paye"],
            "nassit_total": r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"],
            "employees": r["totals"]["employee_count"],
            "nra_filed": bool(
                filed_runs.get(r["id"])
                and filed_runs[r["id"]].get("reference_source") == "external"
                and filed_runs[r["id"]].get("nra_reference")
            ),
            "nra_legacy_recorded": bool(
                filed_runs.get(r["id"])
                and filed_runs[r["id"]].get("reference_source") != "external"
            ),
            "nra_filed_at": (
                filed_runs[r["id"]].get("filed_at")
                if filed_runs.get(r["id"], {}).get("reference_source") == "external" else None
            ),
            "nra_reference": (
                filed_runs[r["id"]].get("nra_reference")
                if filed_runs.get(r["id"], {}).get("reference_source") == "external" else None
            ),
        }
        for r in latest_runs
    ]
    return {
        "runs_count": len(latest_runs),
        "report_year": reporting_year,
        "ytd_paye_sle": round(total_paye, 2),
        "ytd_nassit_sle": round(total_nassit, 2),
        "filed_count": sum(1 for h in history if h["nra_filed"]),
        "outstanding": [h for h in history if not h["nra_filed"] and not h["nra_legacy_recorded"]],
        "unverified": [h for h in history if h["nra_legacy_recorded"]],
        "history": history,
        "next_filing": "NRA PAYE due by the 15th of the following month",
        "regs": {
            "paye_bands": PAYE_BANDS[:-1],
            "nassit_employee": NASSIT_EMPLOYEE,
            "nassit_employer": NASSIT_EMPLOYER,
        },
    }


@router.get("/nra-export/{rid}")
async def nra_export(rid: str, user: dict = Depends(require_roles("payroll", "auditor"))):
    """Original JSON export — kept for backwards compatibility with the UI table."""
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Not found")
    _require_completed_run(r)
    rows = [
        {
            "employee": s["employee_name"],
            "gross_sle": s["gross"],
            "paye_sle": s["paye"],
            "nassit_employee_sle": s["nassit_employee"],
            "nassit_employer_sle": s["nassit_employer"],
            "net_sle": s["net"],
        }
        for s in r["slips"]
    ]
    return {"period": r["period"], "rows": rows, "totals": r["totals"]}


@router.get("/nra-paye-return.csv/{rid}")
async def nra_paye_return_csv(rid: str, user: dict = Depends(require_feature("nra_export"))):
    """Structured payroll workpaper for NRA PAYE preparation; it does not submit the return."""
    if not can_role(user, "payroll", "auditor"):
        raise HTTPException(403, "Payroll, auditor or admin only")
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    _require_completed_run(r)
    employees = await _employees_for_payroll_run(r, user)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    emp_map = {e["id"]: e for e in employees}
    period = r["period"]

    buf = io.StringIO()
    w = csv.writer(buf)
    # NRA PAYE Return header block
    w.writerow(["NRA PAYE RETURN"])
    w.writerow(["Period", period])
    w.writerow(["Employer TIN", (company or {}).get("tin", "")])
    w.writerow(["Employer Name", (company or {}).get("name", "")])
    w.writerow([])
    w.writerow([
        "tin", "employee_name", "nassit_no", "department",
        "gross_sle", "taxable_sle", "paye_sle",
        "nassit_employee_sle", "nassit_employer_sle", "net_sle",
    ])
    for s in r["slips"]:
        emp = emp_map.get(s["employee_id"], {})
        # Taxable = gross less NASSIT employee (Sierra Leone convention)
        taxable = round(s["gross"] - s["nassit_employee"], 2)
        w.writerow([
            _payroll_identity_value(s, "employee_tin", emp, "tin"),
            s["employee_name"],
            _payroll_identity_value(s, "employee_nassit_no", emp, "nassit_no"),
            _payroll_identity_value(s, "employee_department", emp, "department"),
            f'{s["gross"]:.2f}',
            f'{taxable:.2f}',
            f'{s["paye"]:.2f}',
            f'{s["nassit_employee"]:.2f}',
            f'{s["nassit_employer"]:.2f}',
            f'{s["net"]:.2f}',
        ])
    # Period totals
    t = r["totals"]
    w.writerow([])
    w.writerow(["TOTAL", "", "", "",
                f'{t["gross"]:.2f}', f'{t["gross"] - t["nassit_employee"]:.2f}',
                f'{t["paye"]:.2f}', f'{t["nassit_employee"]:.2f}',
                f'{t["nassit_employer"]:.2f}', f'{t["net"]:.2f}'])

    await audit("nra_paye_export", f"payroll_runs/{rid}", user,
                {"period": period, "rows": len(r["slips"])})
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="NRA-PAYE-Return-{period}.csv"'},
    )




@router.get("/nassit-schedule.xlsx/{rid}")
async def nassit_schedule_xlsx(rid: str, user: dict = Depends(require_feature("nra_export"))):
    """Excel contribution schedule using the fields published in NASSIT's Companion Guide."""
    if not can_role(user, "payroll", "auditor"):
        raise HTTPException(403, "Payroll, auditor or admin only")
    run = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run not found")
    _require_completed_run(run)
    employees = await _employees_for_payroll_run(run, user)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0}) or {}
    if not company.get("name") or not company.get("nassit_employer"):
        raise HTTPException(
            422,
            "Complete the employer name and NASSIT registration number in the company profile before exporting.",
        )
    emp_map = {employee["id"]: employee for employee in employees}
    missing_ids = [
        slip.get("employee_name", "Employee")
        for slip in run["slips"]
        if not (
            _payroll_identity_value(
                slip, "employee_nassit_no",
                emp_map.get(slip["employee_id"], {}), "nassit_no",
            )
        )
    ]
    if missing_ids:
        raise HTTPException(
            422,
            f"NASSIT numbers are missing for {len(missing_ids)} employee(s). Complete their profiles and rerun payroll before exporting.",
        )

    payload = _build_nassit_xlsx(run, employees, company)
    await audit(
        "nassit_schedule_xlsx_export",
        f"payroll_runs/{rid}",
        user,
        {"period": run["period"], "rows": len(run["slips"])},
    )
    return StreamingResponse(
        io.BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition":
                f'attachment; filename="NASSIT-Contribution-Schedule-{run["period"]}.xlsx"'
        },
    )


@router.get("/nassit-schedule.csv/{rid}")
async def nassit_schedule_csv(rid: str, user: dict = Depends(require_feature("nra_export"))):
    """Per-employee NASSIT contribution workpaper to accompany the payment advice form."""
    if not can_role(user, "payroll", "auditor"):
        raise HTTPException(403, "Payroll, auditor or admin only")
    r = await db.payroll_runs.find_one({"id": rid, **tenant_filter(user)}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    _require_completed_run(r)
    employees = await _employees_for_payroll_run(r, user)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    emp_map = {e["id"]: e for e in employees}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["NASSIT CONTRIBUTION SCHEDULE"])
    w.writerow(["Period", r["period"]])
    w.writerow(["Employer NASSIT No.", (company or {}).get("nassit_employer", "")])
    w.writerow(["Employer Name", (company or {}).get("name", "")])
    w.writerow([])
    w.writerow(["nassit_no", "employee_name", "basic_sle", "employee_5pct", "employer_10pct", "total_15pct"])
    total_emp = 0.0
    total_er = 0.0
    for s in r["slips"]:
        emp = emp_map.get(s["employee_id"], {})
        emp_share = s["nassit_employee"]
        er_share = s["nassit_employer"]
        total_emp += emp_share
        total_er += er_share
        w.writerow([
            _payroll_identity_value(s, "employee_nassit_no", emp, "nassit_no"),
            s["employee_name"],
            f'{s.get("basic", 0):.2f}',
            f'{emp_share:.2f}',
            f'{er_share:.2f}',
            f'{emp_share + er_share:.2f}',
        ])
    w.writerow([])
    w.writerow(["TOTAL", "", "",
                f'{total_emp:.2f}', f'{total_er:.2f}', f'{total_emp + total_er:.2f}'])
    await audit("nassit_export", f"payroll_runs/{rid}", user,
                {"period": r["period"], "rows": len(r["slips"])})
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="NASSIT-Schedule-{r["period"]}.csv"'},
    )


class FilingReferenceIn(BaseModel):
    nra_reference: str = Field(..., min_length=1, max_length=120)


@router.post("/file-nra/{rid}")
async def mark_nra_filed(rid: str, body: FilingReferenceIn, user: dict = Depends(require_feature("nra_export"))):
    """Record the reference returned after an employer submits through NRA ITAS."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin only")
    nra_ref = body.nra_reference.strip()
    if not nra_ref:
        raise HTTPException(422, "Enter the reference returned by NRA ITAS")
    tf = tenant_filter(user)
    r = await db.payroll_runs.find_one({"id": rid, **tf}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    _require_completed_run(r)

    filing = {
        "period": r["period"],
        "nra_reference": nra_ref,
        "reference_source": "external",
        "filed_at": datetime.now(timezone.utc).isoformat(),
        "filed_by": user["email"],
        "paye_total": r["totals"]["paye"],
        "nassit_total": r["totals"]["nassit_employee"] + r["totals"]["nassit_employer"],
    }
    existing = await db.nra_filings.find_one({"run_id": rid, **tf}, {"_id": 0})
    if existing and existing.get("reference_source") == "external":
        raise HTTPException(409, "An NRA submission reference is already recorded for this run")
    if existing:
        await db.nra_filings.update_one({"run_id": rid, **tf}, {"$set": filing})
        doc = await db.nra_filings.find_one({"run_id": rid, **tf}, {"_id": 0})
        action = "nra_filing_reference_verified"
    else:
        doc = {
            **tf,
            "id": rid,
            "run_id": rid,
            **filing,
        }
        await db.nra_filings.insert_one(doc)
        doc.pop("_id", None)
        action = "nra_filed"

    await audit(action, f"payroll_runs/{rid}", user,
                {"period": r["period"], "nra_reference": nra_ref})
    return doc


@router.get("/filings")
async def list_filings(user: dict = Depends(require_roles("payroll", "auditor"))):
    return await db.nra_filings.find(tenant_filter(user), {"_id": 0}).sort("filed_at", -1).to_list(500)


class EmailFilingIn(BaseModel):
    to: Optional[str] = None


@router.post("/nra-paye-return.csv/{rid}/email")
async def email_nra_paye_csv(rid: str, body: EmailFilingIn, user: dict = Depends(require_feature("nra_export"))):
    """Email the NRA PAYE Return CSV to the requester (or another email)."""
    if user.get("role") not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin only")
    from email_service import send_csv_attachment, is_configured as _ec
    if not _ec():
        raise HTTPException(503, "Email service not configured")
    tf = tenant_filter(user)
    r = await db.payroll_runs.find_one({"id": rid, **tf}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Run not found")
    _require_completed_run(r)
    employees = await _employees_for_payroll_run(r, user)
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    csv_bytes = _build_nra_csv(r, employees, company or {})
    to = (body.to or user["email"]).strip().lower()
    res = await send_csv_attachment(
        to=to,
        subject=f"[SaloneHCM] NRA PAYE Return — {r['period']}",
        title=f"NRA PAYE Return · {r['period']}",
        body_text=(
            f"Attached is the <strong>NRA PAYE Return</strong> for "
            f"<strong>{(company or {}).get('name','your company')}</strong>, period "
            f"<strong>{r['period']}</strong>. Total PAYE: <strong>SLE {r['totals']['paye']:.2f}</strong>."
        ),
        csv_bytes=csv_bytes,
        filename=f"NRA-PAYE-Return-{r['period']}.csv",
        company_id=user["company_id"],
    )
    await audit("nra_paye_email", f"payroll_runs/{rid}", user, {"to": to, "period": r["period"], "ok": res.get("ok")})
    return {**res, "period": r["period"], "to": to}
