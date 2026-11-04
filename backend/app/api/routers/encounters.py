"""Encounter endpoints (visits linking a patient to imaging studies)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.domain.encounter import EncounterCreate, EncounterRead, EncounterUpdate
from app.domain.enums import UserRole
from app.infrastructure.database import get_session
from app.infrastructure.models.user import User
from app.services.encounters import (
    create_encounter,
    get_encounter,
    list_encounters,
    update_encounter,
)
from app.services.patients import get_patient

router = APIRouter(prefix="/api/encounters", tags=["encounters"])

_write_roles = require_roles(UserRole.ADMIN, UserRole.REFERRING_CLINICIAN)


@router.get("", response_model=list[EncounterRead])
async def list_all(
    patient_id: uuid.UUID | None = None,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    return await list_encounters(session, patient_id=patient_id)


@router.post("", response_model=EncounterRead, status_code=status.HTTP_201_CREATED)
async def create(
    payload: EncounterCreate,
    current_user: User = Depends(_write_roles),
    session: AsyncSession = Depends(get_session),
):
    if await get_patient(session, payload.patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return await create_encounter(
        session, payload, referring_clinician_id=current_user.id
    )


@router.get("/{encounter_id}", response_model=EncounterRead)
async def get_one(
    encounter_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    encounter = await get_encounter(session, encounter_id)
    if encounter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    return encounter


@router.patch("/{encounter_id}", response_model=EncounterRead)
async def update(
    encounter_id: uuid.UUID,
    payload: EncounterUpdate,
    _: User = Depends(_write_roles),
    session: AsyncSession = Depends(get_session),
):
    encounter = await get_encounter(session, encounter_id)
    if encounter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    return await update_encounter(session, encounter, payload)
