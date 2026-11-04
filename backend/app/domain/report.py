"""Report request/response schemas (Pydantic v2)."""
import uuid
from datetime import datetime

from pydantic import Field

from app.domain.enums import ReportStatus
from app.domain.schemas import AppModel


class ReportCreate(AppModel):
    study_id: uuid.UUID
    findings: str = Field(default="", max_length=20000)
    impression: str = Field(default="", max_length=20000)
    status: ReportStatus = ReportStatus.DRAFT


class ReportUpdate(AppModel):
    findings: str | None = Field(default=None, max_length=20000)
    impression: str | None = Field(default=None, max_length=20000)
    status: ReportStatus | None = None


class ReportRead(AppModel):
    id: uuid.UUID
    study_id: uuid.UUID
    patient_id: uuid.UUID
    author_id: uuid.UUID | None
    status: ReportStatus
    findings: str
    impression: str
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
