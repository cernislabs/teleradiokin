"""Audit-trail query endpoint (Admin only)."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin
from app.domain.audit import AuditEventRead
from app.domain.enums import AuditAction, AuditEntity
from app.infrastructure.database import get_session
from app.infrastructure.models.user import User
from app.services import audit as svc

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
async def list_audit_events(
    actor_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    entity_type: AuditEntity | None = None,
    entity_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await svc.list_events(
        session,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
