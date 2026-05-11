"""Audit log endpoint (admin only)."""
from fastapi import APIRouter, Depends
from core import db, require_admin, tenant_filter

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit(user: dict = Depends(require_admin)):
    return await db.audit_logs.find(tenant_filter(user), {"_id": 0}).sort("ts", -1).to_list(500)
