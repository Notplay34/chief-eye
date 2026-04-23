"""Audit log helpers."""

from typing import Any, Optional, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


class AuditActor(Protocol):
    id: int


async def write_audit_log(
    db: AsyncSession,
    *,
    user: Optional[AuditActor],
    event_type: str,
    entity_type: str,
    entity_id: Optional[int],
    payload: Optional[dict[str, Any]] = None,
) -> AuditLog:
    row = AuditLog(
        actor_employee_id=user.id if user else None,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload or {},
    )
    db.add(row)
    await db.flush()
    return row
