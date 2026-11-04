"""Encounter request/response schemas (Pydantic v2)."""
import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.domain.enums import EncounterStatus
from app.domain.schemas import AppModel, bounded_extra


class EncounterCreate(AppModel):
    patient_id: uuid.UUID
    status: EncounterStatus = EncounterStatus.PLANNED
    reason: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    extra: dict = Field(default_factory=dict)

    _check_extra = field_validator("extra")(bounded_extra)


class EncounterUpdate(AppModel):
    status: EncounterStatus | None = None
    reason: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    extra: dict | None = None

    _check_extra = field_validator("extra")(bounded_extra)


class EncounterRead(AppModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    referring_clinician_id: uuid.UUID | None
    status: EncounterStatus
    reason: str | None
    occurred_at: datetime | None
    notes: str | None
    extra: dict
    created_at: datetime
    updated_at: datetime | None
