"""Encounter business logic."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import AccessScope
from app.domain.encounter import EncounterCreate, EncounterUpdate
from app.infrastructure.models.patient import Encounter, Patient


async def get_encounter(session: AsyncSession, encounter_id: uuid.UUID) -> Encounter | None:
    return await session.get(Encounter, encounter_id)


async def list_encounters(
    session: AsyncSession,
    *,
    scope: AccessScope,
    patient_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Encounter]:
    stmt = select(Encounter).order_by(Encounter.created_at.desc())
    if not scope.cross_site:
        stmt = stmt.join(Patient, Encounter.patient_id == Patient.id).where(
            Patient.organization_id == scope.organization_id
        )
    if patient_id is not None:
        stmt = stmt.where(Encounter.patient_id == patient_id)
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_encounter(
    session: AsyncSession,
    data: EncounterCreate,
    referring_clinician_id: uuid.UUID | None,
) -> Encounter:
    encounter = Encounter(
        patient_id=data.patient_id,
        referring_clinician_id=referring_clinician_id,
        status=data.status,
        reason=data.reason,
        occurred_at=data.occurred_at,
        notes=data.notes,
        extra=data.extra or {},
    )
    session.add(encounter)
    await session.commit()
    await session.refresh(encounter)
    return encounter


async def update_encounter(
    session: AsyncSession, encounter: Encounter, data: EncounterUpdate
) -> Encounter:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(encounter, field, value)
    await session.commit()
    await session.refresh(encounter)
    return encounter
