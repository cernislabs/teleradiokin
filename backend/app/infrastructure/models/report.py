"""Structured radiology report model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ReportStatus
from app.infrastructure.models.base import TimestampedBase
from app.infrastructure.models.types import str_enum


class Report(TimestampedBase):
    """One structured report per study (findings + impression + status)."""

    __tablename__ = "reports"

    study_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("studies.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[ReportStatus] = mapped_column(
        str_enum(ReportStatus, 16), default=ReportStatus.DRAFT, nullable=False,
    )
    findings: Mapped[str] = mapped_column(Text, nullable=False, default="")
    impression: Mapped[str] = mapped_column(Text, nullable=False, default="")
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
