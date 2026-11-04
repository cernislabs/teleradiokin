"""Imaging study and chunked-upload session models."""
import uuid

from sqlalchemy import BigInteger, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import StudyStatus
from app.infrastructure.models.base import TimestampedBase
from app.infrastructure.models.types import JsonB


class UploadSession(TimestampedBase):
    """Tracks a resumable chunked upload before a Study is created."""

    __tablename__ = "upload_sessions"

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    received_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    temp_key: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")


class Study(TimestampedBase):
    """An imaging study (one uploaded object) linked to an encounter/patient."""

    __tablename__ = "studies"

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("encounters.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )

    status: Mapped[StudyStatus] = mapped_column(
        Enum(
            StudyStatus, native_enum=False, length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=StudyStatus.PROCESSING, index=True, nullable=False,
    )

    # Stored object keys (relative to the storage root).
    storage_key: Mapped[str] = mapped_column(String(400), nullable=False)
    preview_key: Mapped[str | None] = mapped_column(String(400), nullable=True)

    # Original file facts.
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_dicom: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Extracted DICOM metadata (nullable until processed).
    modality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    study_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    body_part: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accession_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    study_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    series_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sop_instance_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)

    processing_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)

    @property
    def has_preview(self) -> bool:
        return self.preview_key is not None
