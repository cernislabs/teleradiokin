"""Imaging-study and upload schemas (Pydantic v2)."""
import uuid
from datetime import datetime

from pydantic import Field

from app.domain.enums import StudyStatus
from app.domain.schemas import AppModel


class UploadInit(AppModel):
    encounter_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=300)
    content_type: str | None = Field(default=None, max_length=120)
    total_size: int = Field(gt=0, description="Total file size in bytes")


class UploadSessionRead(AppModel):
    id: uuid.UUID
    encounter_id: uuid.UUID
    filename: str
    content_type: str | None
    total_size: int
    received_bytes: int
    status: str


class StudyRead(AppModel):
    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    status: StudyStatus
    original_filename: str
    content_type: str | None
    size_bytes: int
    is_dicom: bool
    has_preview: bool
    modality: str | None
    study_date: str | None
    body_part: str | None
    accession_number: str | None
    study_instance_uid: str | None
    series_instance_uid: str | None
    sop_instance_uid: str | None
    processing_error: str | None
    created_at: datetime
    updated_at: datetime | None
