"""Audit log helpers."""

from typing import Any, Optional, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import current_request_context
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
    context = {key: value for key, value in current_request_context().items() if value}
    payload_json = {**context, **(payload or {})}
    row = AuditLog(
        actor_employee_id=user.id if user else None,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=payload_json,
    )
    db.add(row)
    await db.flush()
    return row
