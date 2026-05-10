"""Audit log endpoint (admin only)."""
from fastapi import APIRouter, Depends
from core import db, require_admin

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit(_: dict = Depends(require_admin)):
    return await db.audit_logs.find({}, {"_id": 0}).sort("ts", -1).to_list(500)
