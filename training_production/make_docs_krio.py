"""Krio-language Training Center documents: quick reference cards + onboarding
checklist. Outputs qrc-*-krio.pdf and onboarding-checklist-krio.pdf into
/app/backend/static/training/docs/."""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

OUT = Path("/app/backend/static/training/docs")
OUT.mkdir(parents=True, exist_ok=True)

GREEN, BLUE, INK, GREY = "#0A4A1E", "#26547C", "#1A1C1E", "#525860"
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, textColor=colors.HexColor(GREEN), spaceAfter=4)
SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=10, textColor=colors.HexColor(GREY), spaceAfter=14)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor(BLUE), spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor(INK), leading=13.5)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)


def brand(story, title, subtitle):
    story.append(Paragraph("SALONEHCM · TRAINING CENTER · KRIO", ParagraphStyle(
        "brand", fontName="Helvetica-Bold", fontSize=8, textColor=colors.HexColor("#8B6A14"))))
    story.append(Spacer(1, 6))
    story.append(Paragraph(title, H1))
    story.append(Paragraph(subtitle, SUB))


def qrc(filename, title, subtitle, sections):
    doc = SimpleDocTemplate(str(OUT / filename), pagesize=A4,
                            leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm)
    story = []
    brand(story, title, subtitle)
    for heading, lines in sections:
        story.append(Paragraph(heading, H2))
        for line in lines:
            story.append(Paragraph(f"• {line}", BULLET))
    doc.build(story)
    print("wrote", filename)


qrc("qrc-getting-started-krio.pdf", "Quick Reference — Aw For Start (Krio)",
    "Sign-in, navigation en aw for find feature dem · keep dis near yu keyboard for week one.", [
    ("Aw for sign in", [
        "Use di work email en password wey yu administrator gi yu; add yu 6-digit authenticator code if 2FA don on.",
        "Yu forget yu password? Yu administrator de reset am na Users &amp; Access.",
    ]),
    ("Aw for find yu way", [
        "Di sidebar de show only wetin yu role en yu plan don unlock.",
        "Feature Directory (number 2 na di sidebar) de list ALL di module dem with den status: Available / Need bigger plan / Na admin only.",
        "Dashboard KPI dem de update live: headcount, payroll cost, leave wey de wait, compliance.",
    ]),
    ("Yu first week", [
        "Day 1: sign in, waka round di dashboard en di Feature Directory.",
        "Day 2: check yu personal details en yu bank/NASSIT number dem na Self-Service.",
        "Day 3–5: watch yu role in training video, den pass di quiz (70%) for get yu certificate.",
    ]),
    ("Usai for get help", [
        "Training Center: video, article, FAQ, quiz dem — public, no login no need.",
        "Access problem → yu administrator. Data problem → yu H R officer.",
    ])])

qrc("qrc-administrator-krio.pdf", "Quick Reference — Administrator (Krio)",
    "Users, capability flags, settings, branch dem en di audit trail.", [
    ("Users en access", [
        "Invite by email; di person go set in own password with di link.",
        "Reset password, delete people wey don leave, en search account dem from one screen.",
    ]),
    ("Capability flags (di banknote icon)", [
        "Finance Officer — de review en approve payroll voucher dem.",
        "MoF Approver — de sign payroll run en authorize voucher payment.",
        "Separation of duties de automatic: creator no be approver no be authorizer.",
    ]),
    ("Branch dem en office (Vouchers → Branches tab)", [
        "One code per branch; optional ministry link; put one supervisor per branch.",
        "Assign workman den to branch — auto voucher generation de group by branch.",
    ]),
    ("Settings", [
        "Organisation profile, plan tier, SMS/email integration, 2FA policy, transparency portal.",
        "Superadmin only: multi-sig MoF threshold (1–5 signature) na di Payroll page.",
    ]),
    ("Audit log", [
        "Every approval, change en payment authorization — yu able search am, e permanent.",
    ])])

qrc("qrc-hr-officer-krio.pdf", "Quick Reference — H R Officer (Krio)",
    "Workman den, leave, attendance en document dem — di everyday H R work.", [
    ("Employee register", [
        "Di single source of truth: grade, salary, bank, NASSIT, department.",
        "Search quick quick; Add Employee de guide yu through all di required statutory field dem.",
    ]),
    ("Leave", [
        "Request dem de come with balance en overlap information.",
        "Approve or reject with comment; di decision de log en di workman go know.",
    ]),
    ("Attendance", [
        "Daily clock-in, absence en timesheet total dem wey de feed payroll.",
        "Correction possible en e de audit log — finish den BEFORE di payroll run.",
    ]),
    ("Document vault", [
        "Contract, ID, letter dem — upload one time, store safe, na yu organisation only.",
        "Use search + category filter for find anything quick quick.",
    ]),
    ("Di golden rule", [
        "Clean data today de prevent payroll palava tomorrow.",
    ])])

qrc("qrc-payroll-officer-krio.pdf", "Quick Reference — Payroll Officer (Krio)",
    "Preview → run → payslip → bank file → filing, with Salone statutory rule dem.", [
    ("Di calculation order", [
        "Basic + allowance = gross → NASSIT employee 5% → NRA PAYE (progressive band) → loan/deduction → net.",
        "Employer NASSIT na 10%; both de show na di payslip en NASSIT schedule.",
    ]),
    ("Aw for run payroll", [
        "ALWAYS Preview first: check headcount en total dem against last month.",
        "Gov tenant: budget check must green; cut-off lock de respect; MoF chain de sign di run.",
    ]),
    ("After di run", [
        "Payslip PDF per workman; bulk payslip SMS; bank file na Rokel / SLCB / UBA / Ecobank format.",
    ]),
    ("Compliance", [
        "Monthly NRA PAYE return + NASSIT schedule export na di expected format.",
        "Deadline dem de track na di Compliance page — file before den turn red.",
    ]),
    ("No ever do dis", [
        "No ever bypass blocked budget check without documented, authorised override.",
    ])])

qrc("qrc-vouchers-krio.pdf", "Quick Reference — Payroll Vouchers (Krio)",
    "Di centralized voucher workflow en every anti-fraud rail.", [
    ("Di stage dem", [
        "Draft → Wait supervisor → Submitted → Under review → Approved → Payment authorized.",
        "Return-for-correction possible na any stage before payment (reason must be 10 character or more).",
    ]),
    ("Who de do wetin", [
        "Branch officer/supervisor de create + submit · supervisor de approve · finance officer de review + approve · MoF/admin de authorize payment.",
    ]),
    ("Di rail dem", [
        "One voucher per branch per period — duplicate de reject.",
        "Double-pay guard: one workman no able de na two active voucher for one period.",
        "E de immutable after submission — correction na only through official return (revision de go up).",
        "Creator no ever able approve in own voucher; authorizer no be creator EN no be approver.",
        "Payment-authorized voucher na permanent record; na only draft yu able delete.",
    ]),
    ("Auto-generation", [
        "Generate-from-run de split one payroll run into one draft voucher per branch; workman den wey no get branch de report.",
    ])])

qrc("qrc-employee-krio.pdf", "Quick Reference — Employee Self-Service (Krio)",
    "Payslip, leave en attendance — everything wey yu able do by yuself.", [
    ("Payslip dem", [
        "Self-Service de list every payslip with gross, deduction en net.",
        "Open any month for di full breakdown (PAYE, NASSIT, loan) en download di PDF.",
    ]),
    ("Leave", [
        "New Request → date + leave type → submit. Yu manager go know one time.",
        "Watch di status change; yu remaining balance de always show.",
    ]),
    ("Attendance", [
        "Clock in/out na di Attendance page; review yu own history.",
        "Something wrong? Tell H R — den go correct am en log am.",
    ]),
    ("Yu account", [
        "Yu forget password → yu administrator. Keep yu bank + NASSIT details current.",
    ])])

# ---- Onboarding checklist (Krio) ----
doc = SimpleDocTemplate(str(OUT / "onboarding-checklist-krio.pdf"), pagesize=A4,
                        leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm)
story = []
brand(story, "Customer Onboarding Checklist (Krio)", "Di 4-week rollout plan — from kickoff to di first live payroll.")
WEEKS = [
    ("Week 1 — Foundation", [
        "Confirm di tenant, plan tier en admin account dem",
        "Turn on 2FA policy en review di security settings",
        "Import di employee register (grade, salary, bank, NASSIT number dem)",
        "Define department / ministry en branch dem with supervisor",
        "Invite H R officer en payroll officer dem; grant Finance/MoF flag careful",
    ]),
    ("Week 2 — Configuration", [
        "Check di NRA PAYE band en NASSIT rate dem for di tenant",
        "Configure allowance rule dem en (Gov) grade &amp; step structure",
        "Set budget code en period allocation dem (Gov)",
        "Connect SMS (Twilio) en email integration",
        "Assign workman den to branch; set di multi-sig MoF threshold",
    ]),
    ("Week 3 — Dry run", [
        "Run one payroll PREVIEW en reconcile am against di last manual payroll",
        "Generate test payslip en one bank file; check di format with di bank",
        "Create one test voucher through di full approval chain",
        "All staff watch den role in training video en pass di quiz",
    ]),
    ("Week 4 — Go live", [
        "Freeze di old spreadsheet dem; announce di cut-over date",
        "Run di first live payroll with finance de watch di approval chain",
        "Send payslip SMS / open self-service access to all workman den",
        "File di first NRA PAYE return en NASSIT schedule from di system",
        "Review di audit log en hold one 30-minute retrospective",
    ]),
]
for wk, items in WEEKS:
    story.append(Paragraph(wk, H2))
    rows = [[Paragraph("☐", BODY), Paragraph(i, BODY)] for i in items]
    t = Table(rows, colWidths=[0.8 * cm, 15.6 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
doc.build(story)
print("wrote onboarding-checklist-krio.pdf")
print("ALL KRIO DOCS DONE")
