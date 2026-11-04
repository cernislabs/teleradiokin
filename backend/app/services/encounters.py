"""Encounter business logic."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.encounter import EncounterCreate, EncounterUpdate
from app.infrastructure.models.patient import Encounter


async def get_encounter(session: AsyncSession, encounter_id: uuid.UUID) -> Encounter | None:
    return await session.get(Encounter, encounter_id)


async def list_encounters(
    session: AsyncSession, patient_id: uuid.UUID | None = None
) -> list[Encounter]:
    stmt = select(Encounter).order_by(Encounter.created_at.desc())
    if patient_id is not None:
        stmt = stmt.where(Encounter.patient_id == patient_id)
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
