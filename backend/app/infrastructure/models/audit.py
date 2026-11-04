"""Audit-trail event model.

Append-only record of who did what to which record and when. The actor's email
and role are denormalized onto the row so the trail survives even if the user
account is later removed (``actor_id`` is nulled, the snapshot remains).
"""
import uuid

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AuditAction, AuditEntity, UserRole
from app.infrastructure.models.base import TimestampedBase
from app.infrastructure.models.types import JsonB, str_enum


class AuditEvent(TimestampedBase):
    """A single audited action. ``created_at`` (from the base) is the event time."""

    __tablename__ = "audit_events"

    # Composite index for the common query: "all events for this record, newest
    # first" (the admin per-record history). Single-column indexes can't serve it.
    __table_args__ = (
        Index("ix_audit_entity_history", "entity_type", "entity_id", "created_at"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=True,
    )
    actor_email: Mapped[str] = mapped_column(String(320), nullable=False)
    actor_role: Mapped[UserRole] = mapped_column(str_enum(UserRole, 32), nullable=False)

    action: Mapped[AuditAction] = mapped_column(str_enum(AuditAction, 16), nullable=False)
    entity_type: Mapped[AuditEntity] = mapped_column(
        str_enum(AuditEntity, 16), index=True, nullable=False
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), index=True, nullable=True
    )

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
