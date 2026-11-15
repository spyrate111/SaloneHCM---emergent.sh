"""Decision Brief PDF builder — extracted from simulator router for testability."""
import io
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _styles():
    base = getSampleStyleSheet()
    return {
        "h": ParagraphStyle("h", parent=base["Heading1"], fontSize=22, textColor=colors.HexColor("#0A4A1E"), spaceAfter=4),
        "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=9, textColor=colors.HexColor("#525860")),
        "label": ParagraphStyle("l", parent=base["Normal"], fontSize=8, textColor=colors.HexColor("#525860"), spaceBefore=10),
        "h3": base["Heading3"],
    }


def _callout_table(data: dict) -> Table:
    cheapest_title = next((r["scenario"]["title"] for r in data["rows"] if r["scenario"]["id"] == data["cheapest_id"]), "—")
    targeted_title = next((r["scenario"]["title"] for r in data["rows"] if r["scenario"]["id"] == data["most_targeted_id"]), "—")
    rows = [
        ["Recommendation", "Scenario"],
        ["Cheapest option", cheapest_title],
        ["Most targeted (high impact, low cost)", targeted_title],
    ]
    t = Table(rows, colWidths=[200, 300])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#26547C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#E4F7E7")),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#FBE9DF")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2DFD6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _comparison_table(data: dict) -> Table:
    headers = ["#", "Scenario", "Status", "Affected", "Δ Employer/mo", "Annualized Δ", "Δ PAYE", "Δ NASSIT"]
    rows = [headers]
    for i, r in enumerate(data["rows"], start=1):
        s = r["scenario"]
        t = r["totals"]
        rows.append([
            str(i),
            s["title"][:40],
            s["approval_status"] + (" · applied" if s["applied"] else ""),
            str(t["affected"]),
            f"{t['delta_employer']:+,.2f}",
            f"{t['annualized']:+,.2f}",
            f"{t['paye_delta']:+,.2f}",
            f"{t['nassit_delta']:+,.2f}",
        ])
    table = Table(rows, colWidths=[20, 145, 70, 50, 70, 75, 60, 65])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A4A1E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F7F6F2"), colors.white]),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#E4F7E7")),  # highlight cheapest
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2DFD6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def build_pdf(data: dict, user: dict, company: dict | None) -> bytes:
    """Render the Decision Brief PDF as bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    st = _styles()

    company_name = (company or {}).get("name", "Demo Salone Ltd.")
    company_label = (company or {}).get("label", "")
    when = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

    story = [
        Paragraph("SaloneHCM Decision Brief", st["h"]),
        Paragraph(
            f"{company_name} &nbsp;·&nbsp; {company_label} &nbsp;·&nbsp; Sierra Leone &nbsp;·&nbsp; "
            f"Prepared by {user['email']} &nbsp;·&nbsp; {when}",
            st["sub"],
        ),
        Spacer(1, 14),
        Paragraph("<b>Compared scenarios (ranked by annualized employer cost — cheapest first)</b>", st["h3"]),
        Spacer(1, 6),
        _callout_table(data),
        Spacer(1, 18),
        _comparison_table(data),
        Paragraph(
            "<i>All figures in Sierra Leonean Leone (SLE). Simulations were re-computed against live employee records at the time of export. "
            "NASSIT = employee 5% + employer 10% of basic salary. PAYE bands per NRA.</i>",
            st["label"],
        ),
    ]
    doc.build(story)
    return buf.getvalue()
