"""Audit-event response schema (Pydantic v2). Read-only; the trail is append-only."""
import uuid
from datetime import datetime

from app.domain.enums import AuditAction, AuditEntity, UserRole
from app.domain.schemas import AppModel


class AuditEventRead(AppModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str
    actor_role: UserRole
    action: AuditAction
    entity_type: AuditEntity
    entity_id: uuid.UUID | None
    ip_address: str | None
    detail: dict | None
    created_at: datetime
