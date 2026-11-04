"""Audit-trail business logic: record events and query them (admin).

Recording is deliberately best-effort — an audit failure must never break the
primary operation it accompanies, so :func:`record` swallows and rolls back its
own errors rather than propagating them.
"""
import uuid
from datetime import datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditAction, AuditEntity, UserRole
from app.infrastructure.models.audit import AuditEvent
from app.infrastructure.models.user import User


def client_ip(request: Request | None) -> str | None:
    """Best-effort source IP for an audit event."""
    if request is None or request.client is None:
        return None
    return request.client.host


async def record(
    session: AsyncSession,
    *,
    actor: User,
    action: AuditAction,
    entity_type: AuditEntity,
    entity_id: uuid.UUID | None = None,
    request: Request | None = None,
    detail: dict | None = None,
) -> None:
    """Append one audit event. Never raises — a logging failure must not break
    the action being audited."""
    event = AuditEvent(
        actor_id=actor.id,
        actor_email=actor.email,
        actor_role=UserRole(actor.role),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=client_ip(request),
        detail=detail or None,
    )
    try:
        session.add(event)
        await session.commit()
    except Exception:
        await session.rollback()


async def list_events(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    entity_type: AuditEntity | None = None,
    entity_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEvent]:
    """Return audit events newest-first, filtered and paginated (admin use)."""
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    if actor_id is not None:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if action is not None:
        stmt = stmt.where(AuditEvent.action == action)
    if entity_type is not None:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if since is not None:
        stmt = stmt.where(AuditEvent.created_at >= since)
    if until is not None:
        stmt = stmt.where(AuditEvent.created_at <= until)
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())
