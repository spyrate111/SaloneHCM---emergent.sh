"""Document Vault — employee documents (contracts, certificates, P9 forms, etc.)."""
import io
import uuid
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core import db, get_current_user, require_admin, audit, now_utc, iso
from storage import put_object, get_object, APP_NAME

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

Category = Literal["contract", "certificate", "p9_form", "payslip", "id_document", "other"]


class DocumentOut(BaseModel):
    id: str
    employee_id: str
    employee_name: Optional[str] = None
    category: Category
    original_filename: str
    content_type: str
    size: int
    description: Optional[str] = ""
    uploaded_by: str
    uploaded_at: str


def _ext_for(content_type: str, filename: str) -> str:
    if content_type in ALLOWED_MIME:
        return ALLOWED_MIME[content_type]
    # fallback to filename extension
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "bin"


async def _resolve_employee_name(eid: str) -> Optional[str]:
    emp = await db.employees.find_one({"id": eid}, {"_id": 0, "first_name": 1, "last_name": 1})
    if not emp:
        return None
    return f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()


@router.post("/upload")
async def upload_document(
    employee_id: str = Form(...),
    category: Category = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"Unsupported file type {file.content_type}. Allowed: PDF, DOCX, DOC, JPG, PNG")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_BYTES // (1024 * 1024)}MB)")
    emp = await db.employees.find_one({"id": employee_id}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found")

    ext = _ext_for(file.content_type, file.filename or "")
    file_id = str(uuid.uuid4())
    storage_path = f"{APP_NAME}/uploads/{employee_id}/{file_id}.{ext}"
    try:
        result = put_object(storage_path, data, file.content_type)
    except Exception as e:
        raise HTTPException(502, f"Storage upload failed: {e}") from e

    doc = {
        "id": file_id,
        "employee_id": employee_id,
        "employee_name": f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip(),
        "category": category,
        "original_filename": file.filename or f"{file_id}.{ext}",
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "description": (description or "").strip()[:500],
        "storage_path": result.get("path", storage_path),
        "uploaded_by": user["email"],
        "uploaded_at": iso(now_utc()),
        "is_deleted": False,
    }
    await db.documents.insert_one(doc)
    doc.pop("_id", None)
    await audit("document_upload", f"documents/{file_id}", user,
                {"employee_id": employee_id, "category": category, "filename": doc["original_filename"]})
    # don't leak storage_path
    doc.pop("storage_path", None)
    return doc


@router.get("")
async def list_documents(
    employee_id: Optional[str] = Query(None),
    category: Optional[Category] = Query(None),
    user: dict = Depends(get_current_user),
):
    q: dict = {"is_deleted": False}
    if user.get("role") != "admin":
        my_eid = user.get("employee_id")
        if not my_eid:
            return []
        q["employee_id"] = my_eid
    elif employee_id:
        q["employee_id"] = employee_id
    if category:
        q["category"] = category
    rows = await db.documents.find(q, {"_id": 0, "storage_path": 0}).sort("uploaded_at", -1).to_list(1000)
    return rows


@router.get("/employee/{eid}")
async def list_employee_documents(eid: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin" and user.get("employee_id") != eid:
        raise HTTPException(403, "Forbidden")
    rows = await db.documents.find(
        {"employee_id": eid, "is_deleted": False},
        {"_id": 0, "storage_path": 0},
    ).sort("uploaded_at", -1).to_list(1000)
    return rows


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    request: Request,
    auth: Optional[str] = Query(None),
):
    # Manual auth: prefer Authorization header, allow ?auth= token (for <a> downloads)
    from core import get_current_user as _get_user
    if not request.headers.get("authorization") and auth:
        # Build a synthetic request with the auth token header so reuse get_current_user
        request.scope["headers"] = list(request.scope["headers"]) + [
            (b"authorization", f"Bearer {auth}".encode()),
        ]
    user = await _get_user(request)

    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    if user.get("role") != "admin" and user.get("employee_id") != doc["employee_id"]:
        raise HTTPException(403, "Forbidden")

    try:
        data, ct = get_object(doc["storage_path"])
    except Exception as e:
        raise HTTPException(502, f"Storage fetch failed: {e}") from e

    filename = doc.get("original_filename", f"{doc_id}.bin")
    safe_name = quote(filename)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=doc.get("content_type", ct),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{safe_name}',
            "Content-Length": str(len(data)),
        },
    )


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(require_admin)):
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    await db.documents.update_one(
        {"id": doc_id},
        {"$set": {"is_deleted": True, "deleted_at": iso(now_utc()), "deleted_by": user["email"]}},
    )
    await audit("document_delete", f"documents/{doc_id}", user,
                {"employee_id": doc["employee_id"], "filename": doc.get("original_filename")})
    return {"ok": True}


@router.get("/stats/summary")
async def documents_summary(_: dict = Depends(require_admin)):
    pipeline = [
        {"$match": {"is_deleted": False}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}, "size": {"$sum": "$size"}}},
        {"$sort": {"count": -1}},
    ]
    by_cat = [{"category": r["_id"], "count": r["count"], "size": r["size"]} async for r in db.documents.aggregate(pipeline)]
    total = await db.documents.count_documents({"is_deleted": False})
    return {"total": total, "by_category": by_cat}
