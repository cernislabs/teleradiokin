"""Declarative base and a timestamped-entity mixin.

Uses SQLAlchemy's dialect-portable ``Uuid`` type so the same models work on
PostgreSQL (production) and SQLite (fast tests).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root declarative base; `Base.metadata` is the Alembic target."""


class TimestampedBase(Base):
    """Base for persisted entities: surrogate UUID key + audit timestamps."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )
