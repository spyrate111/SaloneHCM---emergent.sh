"""Audit log endpoints — admins + read-only auditors, with CSV/PDF exports."""
import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse

from core import db, require_roles, tenant_filter

router = APIRouter(prefix="/audit", tags=["audit"])

_VIEW = require_roles("auditor")


async def _rows(user: dict, limit: int = 2000) -> list[dict]:
    return await db.audit_logs.find(
        tenant_filter(user), {"_id": 0}).sort("ts", -1).to_list(limit)


@router.get("")
async def list_audit(user: dict = Depends(_VIEW)):
    return await _rows(user, 500)


@router.get("/export.csv")
async def export_audit_csv(user: dict = Depends(_VIEW)):
    rows = await _rows(user)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp_utc", "action", "resource", "actor_email", "actor_role", "meta"])
    for r in rows:
        w.writerow([r.get("ts"), r.get("action"), r.get("resource"),
                    r.get("user_email"), r.get("user_role"), str(r.get("meta") or {})])
    return StreamingResponse(
        iter([buf.getvalue().encode()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'})


@router.get("/export.pdf")
async def export_audit_pdf(user: dict = Depends(_VIEW)):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    rows = await _rows(user, 500)
    company = await db.companies.find_one(
        {"id": user.get("company_id")}, {"_id": 0, "name": 1}) or {}
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1 * cm, rightMargin=1 * cm,
                            topMargin=1 * cm, bottomMargin=1 * cm)
    story = [
        Paragraph(f"SaloneHCM — Audit Log · {company.get('name', '')}", styles["Title"]),
        Paragraph(f"Most recent {len(rows)} entries", styles["Normal"]),
        Spacer(1, 8),
    ]
    data = [["Timestamp (UTC)", "Action", "Resource", "Actor", "Role"]]
    for r in rows:
        data.append([
            (r.get("ts") or "")[:19].replace("T", " "),
            r.get("action") or "",
            (r.get("resource") or "")[:48],
            r.get("user_email") or "",
            r.get("user_role") or "",
        ])
    table = Table(data, repeatRows=1, colWidths=[3.6 * cm, 5.4 * cm, 9.2 * cm, 6.4 * cm, 2.6 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A4A1E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2DFD6")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F6F2")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    doc.build(story)
    return Response(
        buf.getvalue(), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="audit-log.pdf"'})
