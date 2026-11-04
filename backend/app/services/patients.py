"""Patient-record business logic."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.patient import PatientCreate, PatientUpdate
from app.infrastructure.models.patient import Patient


async def get_patient(session: AsyncSession, patient_id: uuid.UUID) -> Patient | None:
    return await session.get(Patient, patient_id)


async def get_patient_by_mrn(session: AsyncSession, mrn: str) -> Patient | None:
    result = await session.execute(select(Patient).where(Patient.mrn == mrn))
    return result.scalar_one_or_none()


async def list_patients(
    session: AsyncSession, limit: int = 100, offset: int = 0
) -> list[Patient]:
    result = await session.execute(
        select(Patient).order_by(Patient.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def create_patient(session: AsyncSession, data: PatientCreate) -> Patient:
    patient = Patient(
        mrn=data.mrn,
        family_name=data.family_name,
        given_name=data.given_name,
        birth_date=data.birth_date,
        sex=data.sex,
        phone=data.phone,
        consent_acknowledged=data.consent_acknowledged,
        consent_acknowledged_at=datetime.now(timezone.utc),
        extra=data.extra or {},
    )
    session.add(patient)
    await session.commit()
    await session.refresh(patient)
    return patient


async def update_patient(
    session: AsyncSession, patient: Patient, data: PatientUpdate
) -> Patient:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    await session.commit()
    await session.refresh(patient)
    return patient
