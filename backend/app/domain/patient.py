"""Patient request/response schemas (Pydantic v2)."""
import uuid
from datetime import date, datetime

from pydantic import Field, field_validator

from app.domain.enums import AdministrativeGender
from app.domain.schemas import AppModel, bounded_extra


class PatientCreate(AppModel):
    mrn: str = Field(min_length=1, max_length=64, description="Medical Record Number")
    family_name: str = Field(min_length=1, max_length=120)
    given_name: str = Field(min_length=1, max_length=120)
    birth_date: date | None = None
    sex: AdministrativeGender = AdministrativeGender.UNKNOWN
    phone: str | None = Field(default=None, max_length=40)
    consent_acknowledged: bool = Field(
        description="Must be true: the patient has acknowledged consent."
    )
    extra: dict = Field(default_factory=dict)

    @field_validator("consent_acknowledged")
    @classmethod
    def _require_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError(
                "Patient consent must be acknowledged before creating a record."
            )
        return value

    _check_extra = field_validator("extra")(bounded_extra)


class PatientUpdate(AppModel):
    family_name: str | None = Field(default=None, min_length=1, max_length=120)
    given_name: str | None = Field(default=None, min_length=1, max_length=120)
    birth_date: date | None = None
    sex: AdministrativeGender | None = None
    phone: str | None = Field(default=None, max_length=40)
    extra: dict | None = None

    _check_extra = field_validator("extra")(bounded_extra)


class PatientRead(AppModel):
    id: uuid.UUID
    mrn: str
    organization_id: uuid.UUID | None
    family_name: str
    given_name: str
    birth_date: date | None
    sex: AdministrativeGender
    phone: str | None
    consent_acknowledged: bool
    consent_acknowledged_at: datetime | None
    extra: dict
    created_at: datetime
    updated_at: datetime | None
