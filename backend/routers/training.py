"""Public Training Center: KB articles, FAQs, quizzes with certification.
Everything here is public (no auth) — the Training Center is a marketing/support surface."""
import io
import uuid
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import db, iso, now_utc
from training_content import ARTICLES, FAQS, QUIZZES, RESOURCES

router = APIRouter(prefix="/public/training", tags=["training"])

_QUIZ_BY_ID = {q["id"]: q for q in QUIZZES}


@router.get("/content")
async def training_content():
    quizzes_public = [
        {"id": q["id"], "title": q["title"], "role": q["role"], "pass_pct": q["pass_pct"],
         "questions": [{"q": x["q"], "options": x["options"]} for x in q["questions"]]}
        for q in QUIZZES
    ]
    return {
        "articles": ARTICLES,
        "faqs": FAQS,
        "quizzes": quizzes_public,
        "resources": [{**r, "url": f"/api/static/training/docs/{r['file']}"} for r in RESOURCES],
    }


class QuizSubmitIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    answers: list[int] = Field(..., min_length=1)


@router.post("/quiz/{qid}/submit")
async def submit_quiz(qid: str, body: QuizSubmitIn):
    quiz = _QUIZ_BY_ID.get(qid)
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    questions = quiz["questions"]
    if len(body.answers) != len(questions):
        raise HTTPException(422, f"Expected {len(questions)} answers")
    correct = sum(1 for a, x in zip(body.answers, questions) if a == x["answer"])
    score = round(100 * correct / len(questions))
    passed = score >= quiz["pass_pct"]
    attempt = {
        "id": str(uuid.uuid4()), "quiz_id": qid, "name": body.name.strip(),
        "score": score, "passed": passed, "at": iso(now_utc()),
    }
    await db.training_attempts.insert_one(dict(attempt))
    cert_id = None
    if passed:
        cert_id = f"TC-{secrets.token_hex(4).upper()}"
        await db.training_certs.insert_one({
            "id": cert_id, "name": body.name.strip(), "quiz_id": qid,
            "quiz_title": quiz["title"], "score": score, "issued_at": iso(now_utc()),
        })
    review = [{"correct": a == x["answer"], "answer_idx": x["answer"]}
              for a, x in zip(body.answers, questions)]
    return {"score": score, "passed": passed, "pass_pct": quiz["pass_pct"],
            "correct": correct, "total": len(questions),
            "certificate_id": cert_id, "review": review}


@router.get("/certificates/{cid}/verify")
async def verify_certificate(cid: str):
    doc = await db.training_certs.find_one({"id": cid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Certificate not found")
    return doc


@router.get("/certificates/{cid}.pdf")
async def certificate_pdf(cid: str):
    doc = await db.training_certs.find_one({"id": cid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Certificate not found")
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setFillColor(colors.HexColor("#FDFCFB"))
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#0A4A1E"))
    c.setLineWidth(4)
    c.rect(1.2 * cm, 1.2 * cm, W - 2.4 * cm, H - 2.4 * cm)
    c.setLineWidth(0.8)
    c.rect(1.6 * cm, 1.6 * cm, W - 3.2 * cm, H - 3.2 * cm)

    for i, stripe in enumerate(["#1EB53A", "#FFFFFF", "#0072C6"]):
        c.setFillColor(colors.HexColor(stripe))
        c.rect(1.6 * cm, H - 1.6 * cm - (i + 1) * 0.22 * cm, W - 3.2 * cm, 0.22 * cm, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#0A4A1E"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2.4 * cm, H - 3.1 * cm, "SaloneHCM · Training Center")
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(W / 2, H - 5.4 * cm, "CERTIFICATE OF ACHIEVEMENT")
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#525860"))
    c.drawCentredString(W / 2, H - 7.0 * cm, "This is to certify that")
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#1A1C1E"))
    c.drawCentredString(W / 2, H - 8.8 * cm, doc["name"])
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#525860"))
    c.drawCentredString(W / 2, H - 10.2 * cm, "has passed the certification quiz")
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.HexColor("#26547C"))
    c.drawCentredString(W / 2, H - 11.8 * cm, doc["quiz_title"])
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor("#17A035"))
    c.drawCentredString(W / 2, H - 13.2 * cm, f"Score: {doc['score']}%")

    issued = doc.get("issued_at", "")[:10]
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#686D76"))
    c.drawString(2.4 * cm, 2.2 * cm, f"Issued on: {issued}")
    c.drawRightString(W - 2.4 * cm, 2.2 * cm, f"Certificate ID: {cid}  ·  verify at /training")
    c.showPage()
    c.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="salonehcm-certificate-{cid}.pdf"'})
