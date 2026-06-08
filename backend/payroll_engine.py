"""Sierra Leone payroll engine: PAYE bands, NASSIT, payslip calc, payroll run, PDF builder."""
import io
import uuid
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from core import db, audit, now_utc, iso

# NRA PAYE bands (monthly SLE, post-2022 redenomination)
PAYE_BANDS = [
    (800, 0.0),
    (2200, 0.15),
    (3600, 0.20),
    (5000, 0.25),
    (7500, 0.30),
    (float("inf"), 0.35),
]
NASSIT_EMPLOYEE = 0.05
NASSIT_EMPLOYER = 0.10


def calc_paye(taxable: float) -> float:
    if taxable <= 0:
        return 0.0
    tax = 0.0
    prev = 0.0
    for upper, rate in PAYE_BANDS:
        slab = min(taxable, upper) - prev
        if slab > 0:
            tax += slab * rate
        if taxable <= upper:
            break
        prev = upper
    return round(tax, 2)


def calc_payslip(emp: dict, allowance_breakdown: Optional[dict] = None,
                 loan_deduction: float = 0.0) -> dict:
    basic = float(emp.get("basic_salary_sle", 0))
    legacy_allow = float(emp.get("allowances_sle", 0))
    breakdown = dict(allowance_breakdown or {})
    if legacy_allow and "Other allowances" not in breakdown:
        breakdown["Other allowances"] = legacy_allow
    allow_total = round(sum(breakdown.values()), 2)
    gross = basic + allow_total
    nassit_emp = round(basic * NASSIT_EMPLOYEE, 2)
    nassit_er = round(basic * NASSIT_EMPLOYER, 2)
    taxable = max(0.0, gross - nassit_emp)
    paye = calc_paye(taxable)
    # Loan deductions are post-tax — they reduce take-home pay but don't change tax liability.
    loan = round(max(0.0, float(loan_deduction or 0.0)), 2)
    net = round(gross - nassit_emp - paye - loan, 2)
    return {
        "employee_id": emp["id"],
        "employee_name": f'{emp["first_name"]} {emp["last_name"]}',
        "basic": basic,
        "allowances": allow_total,
        "allowance_breakdown": breakdown,
        "gross": round(gross, 2),
        "nassit_employee": nassit_emp,
        "nassit_employer": nassit_er,
        "paye": paye,
        "loan_deduction": loan,
        "net": net,
        "grade_code": emp.get("grade_code"),
        "step_number": emp.get("step_number"),
        "budget_code": emp.get("budget_code"),
        "mda_ministry": emp.get("mda_ministry"),
    }


async def run_payroll(year: int, month: int, user: dict, audit_action: str = "payroll_run") -> dict:
    """Shared runner used by both POST /payroll/run and AI action plan executor."""
    emps = await db.employees.find(
        {"status": "active", "company_id": user["company_id"]},
        {"_id": 0},
    ).to_list(2000)
    period = f"{year}-{month:02d}"

    # Pull allowance breakdown + active loan deduction per employee.
    from loans_engine import compute_loan_deduction_for_period, apply_loan_deductions_for_run
    try:
        from routers.civil_service import get_active_allowance_amounts
        slips = []
        applied_loan_rows: list[dict] = []
        for e in emps:
            breakdown = await get_active_allowance_amounts(e, user["company_id"], period)
            loan_due, loan_rows = await compute_loan_deduction_for_period(e["id"], user["company_id"], period)
            slips.append(calc_payslip(e, allowance_breakdown=breakdown, loan_deduction=loan_due))
            applied_loan_rows.extend(loan_rows)
    except Exception:
        slips = [calc_payslip(e) for e in emps]
        applied_loan_rows = []

    rid = str(uuid.uuid4())
    doc = {
        "id": rid,
        "company_id": user["company_id"],
        "period": period,
        "period_year": year,
        "period_month": month,
        "slips": slips,
        "totals": {
            "employee_count": len(slips),
            "gross": round(sum(s["gross"] for s in slips), 2),
            "nassit_employee": round(sum(s["nassit_employee"] for s in slips), 2),
            "nassit_employer": round(sum(s["nassit_employer"] for s in slips), 2),
            "paye": round(sum(s["paye"] for s in slips), 2),
            "loan_deductions": round(sum(s.get("loan_deduction", 0) for s in slips), 2),
            "net": round(sum(s["net"] for s in slips), 2),
        },
        "status": "completed",
        "mof_status": "draft",
        "created_at": iso(now_utc()),
    }
    await db.payroll_runs.insert_one(doc)
    # Now persist the loan deductions against each affected loan, idempotent by (loan_id, period).
    if applied_loan_rows:
        await apply_loan_deductions_for_run(rid, period, applied_loan_rows)
    doc.pop("_id", None)
    await audit(audit_action, f"payroll_runs/{rid}", user,
                {"period": period, "net": doc["totals"]["net"]})
    return doc


def build_payslip_pdf(slip: dict, period: str, company: str = "Demo Salone Ltd.") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading1"], fontSize=20, textColor=colors.HexColor("#133326"), spaceAfter=4)
    sub = ParagraphStyle("s", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#525860"))
    label = ParagraphStyle("l", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#525860"))
    story = [
        Paragraph("SaloneHCM", h),
        Paragraph(f"{company} &nbsp;·&nbsp; Sierra Leone &nbsp;·&nbsp; Period {period}", sub),
        Spacer(1, 16),
        Paragraph(f"<b>Payslip — {slip['employee_name']}</b>", styles["Heading3"]),
        Spacer(1, 8),
    ]
    rows = [
        ["Description", "Amount (SLE)"],
        ["Basic salary", f"{slip['basic']:,.2f}"],
        ["Allowances", f"{slip['allowances']:,.2f}"],
        ["Gross", f"{slip['gross']:,.2f}"],
        ["NASSIT (employee 5%)", f"-{slip['nassit_employee']:,.2f}"],
        ["PAYE (NRA)", f"-{slip['paye']:,.2f}"],
        ["Net pay", f"{slip['net']:,.2f}"],
    ]
    t = Table(rows, colWidths=[300, 200])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#133326")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.HexColor("#F7F6F2"), colors.white]),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E6F4EC")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2DFD6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 18))
    story.append(Paragraph(
        "<i>Calculated per Sierra Leone NRA PAYE bands and NASSIT (5% employee, 10% employer) on basic salary.</i>",
        label,
    ))
    doc.build(story)
    return buf.getvalue()
