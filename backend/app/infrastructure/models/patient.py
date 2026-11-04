"""Patient and Encounter models (FHIR-leaning, extensible via JSONB)."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import AdministrativeGender, EncounterStatus
from app.infrastructure.models.base import TimestampedBase
from app.infrastructure.models.types import JsonB


class Patient(TimestampedBase):
    __tablename__ = "patients"

    # Business identifier (Medical Record Number).
    mrn: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # FHIR HumanName-style fields.
    family_name: Mapped[str] = mapped_column(String(120), nullable=False)
    given_name: Mapped[str] = mapped_column(String(120), nullable=False)

    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[AdministrativeGender] = mapped_column(
        Enum(
            AdministrativeGender,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=AdministrativeGender.UNKNOWN,
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Consent acknowledgment (required at creation; see service/schema).
    consent_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Extensible, FHIR-leaning attributes (addresses, extra identifiers, etc.).
    extra: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)


class Encounter(TimestampedBase):
    __tablename__ = "encounters"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # The referring clinician who created/owns the encounter (nullable for admin-created).
    referring_clinician_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[EncounterStatus] = mapped_column(
        Enum(
            EncounterStatus,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=EncounterStatus.PLANNED,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    extra: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)
