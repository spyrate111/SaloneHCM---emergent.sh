"""Staff ID photos and printable, access-controlled employee ID cards."""
import io
import os
import uuid
from urllib.parse import quote

import qrcode
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

from core import db, require_roles, tenant_filter, with_tenant, now_utc, iso, audit
from storage import APP_NAME, get_object, put_object

router = APIRouter(prefix="/employees", tags=["staff-id-cards"])

MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTO_PIXELS = 20_000_000
CARD_SIZE = (85.6 * mm, 54 * mm)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")


def _normalized_photo(data: bytes) -> bytes:
    try:
        probe = Image.open(io.BytesIO(data))
        if probe.format not in {"JPEG", "PNG"}:
            raise HTTPException(415, "Photo must be a JPEG or PNG image")
        width, height = probe.size
        if width < 100 or height < 100:
            raise HTTPException(422, "Photo must be at least 100 × 100 pixels")
        if width * height > MAX_PHOTO_PIXELS:
            raise HTTPException(413, "Photo dimensions are too large")
        probe.verify()

        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Could not read this photo") from exc


def _fit_text(value: str, font: str, size: float, max_width: float) -> str:
    text = str(value or "").strip()
    if pdfmetrics.stringWidth(text, font, size) <= max_width:
        return text
    suffix = "…"
    while text and pdfmetrics.stringWidth(text + suffix, font, size) > max_width:
        text = text[:-1]
    return (text + suffix) if text else suffix


def _render_card(employee: dict, company_name: str, photo: bytes) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=CARD_SIZE, pageCompression=1)
    width, height = CARD_SIZE

    pdf.setFillColor(colors.HexColor("#F7F6F2"))
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#0A4A1E"))
    pdf.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(6 * mm, height - 7.2 * mm, _fit_text(company_name, "Helvetica-Bold", 8, 40 * mm))
    pdf.setFont("Helvetica", 6)
    pdf.drawRightString(width - 6 * mm, height - 7.2 * mm, "STAFF IDENTIFICATION")

    photo_x, photo_y, photo_w, photo_h = 6 * mm, 14 * mm, 22 * mm, 27 * mm
    pdf.setStrokeColor(colors.HexColor("#B7C8BC"))
    pdf.roundRect(photo_x - 0.5 * mm, photo_y - 0.5 * mm,
                  photo_w + 1 * mm, photo_h + 1 * mm, 1.5 * mm, fill=0, stroke=1)
    pdf.drawImage(
        ImageReader(io.BytesIO(photo)),
        photo_x, photo_y, width=photo_w, height=photo_h,
        preserveAspectRatio=True, anchor="c", mask="auto",
    )

    x = 32 * mm
    text_width = 28 * mm
    employee_name = f'{employee.get("first_name", "")} {employee.get("last_name", "")}'.strip()
    pdf.setFillColor(colors.HexColor("#525860"))
    pdf.setFont("Helvetica", 6)
    pdf.drawString(x, 42 * mm, "EMPLOYEE")
    pdf.setFillColor(colors.HexColor("#1A1C1E"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(x, 37 * mm, _fit_text(employee_name, "Helvetica-Bold", 9, text_width))

    pdf.setFillColor(colors.HexColor("#525860"))
    pdf.setFont("Helvetica", 6)
    pdf.drawString(x, 30.5 * mm, "POSITION")
    pdf.setFillColor(colors.HexColor("#1A1C1E"))
    pdf.setFont("Helvetica", 7)
    pdf.drawString(x, 26.5 * mm, _fit_text(employee.get("job_title", ""), "Helvetica", 7, text_width))

    pdf.setFillColor(colors.HexColor("#525860"))
    pdf.setFont("Helvetica", 6)
    pdf.drawString(x, 20 * mm, "DEPARTMENT")
    pdf.setFillColor(colors.HexColor("#1A1C1E"))
    pdf.setFont("Helvetica", 7)
    pdf.drawString(x, 16 * mm, _fit_text(employee.get("department", ""), "Helvetica", 7, text_width))

    qr = qrcode.QRCode(box_size=5, border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(f"{FRONTEND_URL}/m/clock")
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="#0A4A1E", back_color="#FFFFFF").convert("RGB")
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_size = 17 * mm
    qr_x = width - 6 * mm - qr_size
    qr_y = 17 * mm
    pdf.drawImage(ImageReader(qr_buffer), qr_x, qr_y, width=qr_size, height=qr_size)
    pdf.setFillColor(colors.HexColor("#525860"))
    pdf.setFont("Helvetica", 5.5)
    pdf.drawCentredString(qr_x + qr_size / 2, 14.5 * mm, "Scan to open mobile clock")

    employee_code = str(employee.get("id", "")).replace("-", "")[:8].upper()
    pdf.setFillColor(colors.HexColor("#0A4A1E"))
    pdf.setFont("Helvetica-Bold", 6.5)
    pdf.drawString(6 * mm, 7 * mm, f"STAFF ID  {employee_code}")
    pdf.setFillColor(colors.HexColor("#686D76"))
    pdf.setFont("Helvetica", 5.5)
    pdf.drawRightString(width - 6 * mm, 7 * mm, "Keep this card with you")
    pdf.save()
    return buffer.getvalue()


@router.post("/{eid}/id-photo")
async def upload_id_photo(
    eid: str,
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("hr")),
):
    """Store a sanitized employee photo for their printable staff ID card."""
    if file.content_type not in {"image/jpeg", "image/jpg", "image/png"}:
        raise HTTPException(415, "Upload a JPEG or PNG photo")
    data = await file.read(MAX_PHOTO_BYTES + 1)
    if not data:
        raise HTTPException(400, "Photo file is empty")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "Photo must be 5 MB or smaller")
    normalized = _normalized_photo(data)

    tf = tenant_filter(user)
    employee = await db.employees.find_one({"id": eid, **tf}, {"_id": 0, "id": 1})
    if not employee:
        raise HTTPException(404, "Employee not found")
    storage_path = f"{APP_NAME}/{user['company_id']}/id-card-photos/{eid}.jpg"
    try:
        stored = put_object(storage_path, normalized, "image/jpeg")
    except Exception as exc:
        raise HTTPException(502, "Photo storage is unavailable") from exc

    now = now_utc()
    doc = with_tenant({
        "employee_id": eid,
        "storage_path": stored.get("path", storage_path),
        "content_type": "image/jpeg",
        "updated_at": iso(now),
        "updated_by": user["email"],
    }, user)
    await db.employee_id_photos.update_one(
        {"employee_id": eid, **tf},
        {"$set": doc, "$setOnInsert": {"created_at": iso(now)}},
        upsert=True,
    )
    await audit("employee_id_photo_updated", f"employees/{eid}/id-photo", user,
                {"employee_id": eid, "size": len(normalized)})
    return {"ok": True, "updated_at": iso(now)}


@router.get("/{eid}/id-photo")
async def get_id_photo(eid: str, user: dict = Depends(require_roles("hr"))):
    tf = tenant_filter(user)
    employee = await db.employees.find_one({"id": eid, **tf}, {"_id": 0, "id": 1})
    if not employee:
        raise HTTPException(404, "Employee not found")
    row = await db.employee_id_photos.find_one({"employee_id": eid, **tf}, {"_id": 0})
    if not row:
        raise HTTPException(404, "No ID photo uploaded")
    try:
        data, _ = get_object(row["storage_path"])
    except Exception as exc:
        raise HTTPException(502, "Photo storage is unavailable") from exc
    return StreamingResponse(
        io.BytesIO(data),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{eid}/id-card.pdf")
async def download_id_card(eid: str, user: dict = Depends(require_roles("hr"))):
    tf = tenant_filter(user)
    employee = await db.employees.find_one({"id": eid, **tf}, {"_id": 0})
    if not employee:
        raise HTTPException(404, "Employee not found")
    photo = await db.employee_id_photos.find_one({"employee_id": eid, **tf}, {"_id": 0})
    if not photo:
        raise HTTPException(409, "Upload an employee photo before printing the ID card")
    try:
        photo_bytes, _ = get_object(photo["storage_path"])
    except Exception as exc:
        raise HTTPException(502, "Photo storage is unavailable") from exc
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0, "name": 1}) or {}
    pdf_bytes = _render_card(employee, company.get("name") or "SaloneHCM", photo_bytes)
    filename = f"staff-id-{quote(str(employee.get('last_name') or 'employee'))}.pdf"
    await audit("employee_id_card_downloaded", f"employees/{eid}/id-card", user,
                {"employee_id": eid})
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "Content-Length": str(len(pdf_bytes)),
        },
    )
