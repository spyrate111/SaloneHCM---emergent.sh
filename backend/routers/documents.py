"""Document Vault — employee documents (contracts, certificates, P9 forms, etc.)."""
import io
import uuid
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import StreamingResponse

from core import (
    db, get_current_user, require_admin, audit, now_utc, iso,
    tenant_filter, with_tenant, require_feature,
)
from storage import put_object, get_object, APP_NAME

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(require_feature("documents"))],
)

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


def _ext_for(content_type: str, filename: str) -> str:
    if content_type in ALLOWED_MIME:
        return ALLOWED_MIME[content_type]
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "bin"


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
    emp = await db.employees.find_one({"id": employee_id, **tenant_filter(user)}, {"_id": 0})
    if not emp:
        raise HTTPException(404, "Employee not found in your organization")

    ext = _ext_for(file.content_type, file.filename or "")
    file_id = str(uuid.uuid4())
    # Prefix path with company_id so storage paths are isolated per tenant
    storage_path = f"{APP_NAME}/{user['company_id']}/uploads/{employee_id}/{file_id}.{ext}"
    try:
        result = put_object(storage_path, data, file.content_type)
    except Exception as e:
        raise HTTPException(502, f"Storage upload failed: {e}") from e

    doc = with_tenant({
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
    }, user)
    await db.documents.insert_one(doc)
    doc.pop("_id", None)
    await audit("document_upload", f"documents/{file_id}", user,
                {"employee_id": employee_id, "category": category, "filename": doc["original_filename"]})
    doc.pop("storage_path", None)
    return doc


@router.get("")
async def list_documents(
    employee_id: Optional[str] = Query(None),
    category: Optional[Category] = Query(None),
    user: dict = Depends(get_current_user),
):
    q: dict = {"is_deleted": False, **tenant_filter(user)}
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
        {"employee_id": eid, "is_deleted": False, **tenant_filter(user)},
        {"_id": 0, "storage_path": 0},
    ).sort("uploaded_at", -1).to_list(1000)
    return rows


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    request: Request,
    auth: Optional[str] = Query(None),
):
    from core import get_current_user as _get_user
    if not request.headers.get("authorization") and auth:
        request.scope["headers"] = list(request.scope["headers"]) + [
            (b"authorization", f"Bearer {auth}".encode()),
        ]
    user = await _get_user(request)

    doc = await db.documents.find_one(
        {"id": doc_id, "is_deleted": False, **tenant_filter(user)},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(404, "Not found")
    if user.get("role") != "admin" and user.get("employee_id") != doc["employee_id"]:
        raise HTTPException(403, "Forbidden")

    data: bytes = b""
    ct: str = "application/octet-stream"
    try:
        data, ct = get_object(doc["storage_path"])
    except Exception as e:
        raise HTTPException(502, f"Storage fetch failed: {e}") from e

    filename = doc.get("original_filename", f"{doc_id}.bin")
    safe_name = quote(filename)
    media_type = doc.get("content_type") or ct or "application/octet-stream"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{safe_name}',
            "Content-Length": str(len(data)),
        },
    )


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(require_admin)):
    tf = tenant_filter(user)
    doc = await db.documents.find_one({"id": doc_id, "is_deleted": False, **tf}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    await db.documents.update_one(
        {"id": doc_id, **tf},
        {"$set": {"is_deleted": True, "deleted_at": iso(now_utc()), "deleted_by": user["email"]}},
    )
    await audit("document_delete", f"documents/{doc_id}", user,
                {"employee_id": doc["employee_id"], "filename": doc.get("original_filename")})
    return {"ok": True}


@router.get("/stats/summary")
async def documents_summary(user: dict = Depends(require_admin)):
    pipeline = [
        {"$match": {"is_deleted": False, **tenant_filter(user)}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}, "size": {"$sum": "$size"}}},
        {"$sort": {"count": -1}},
    ]
    by_cat = [
        {"category": r["_id"], "count": r["count"], "size": r["size"]}
        async for r in db.documents.aggregate(pipeline)
    ]
    total = await db.documents.count_documents({"is_deleted": False, **tenant_filter(user)})
    return {"total": total, "by_category": by_cat}
