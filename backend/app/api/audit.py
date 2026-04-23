from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequireAdmin, UserInfo
from app.core.database import get_db
from app.models import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs")
async def list_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAdmin),
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "actor_employee_id": row.actor_employee_id,
            "event_type": row.event_type,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "payload_json": row.payload_json or {},
        }
        for row in rows
    ]
