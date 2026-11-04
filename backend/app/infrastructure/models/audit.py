"""Audit-trail event model.

Append-only record of who did what to which record and when. The actor's email
and role are denormalized onto the row so the trail survives even if the user
account is later removed (``actor_id`` is nulled, the snapshot remains).
"""
import uuid

from sqlalchemy import Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AuditAction, AuditEntity, UserRole
from app.infrastructure.models.base import TimestampedBase
from app.infrastructure.models.types import JsonB


def _str_enum(enum_cls, length: int):
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class AuditEvent(TimestampedBase):
    """A single audited action. ``created_at`` (from the base) is the event time."""

    __tablename__ = "audit_events"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=True,
    )
    actor_email: Mapped[str] = mapped_column(String(320), nullable=False)
    actor_role: Mapped[UserRole] = mapped_column(_str_enum(UserRole, 32), nullable=False)

    action: Mapped[AuditAction] = mapped_column(_str_enum(AuditAction, 16), nullable=False)
    entity_type: Mapped[AuditEntity] = mapped_column(
        _str_enum(AuditEntity, 16), index=True, nullable=False
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), index=True, nullable=True
    )

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
