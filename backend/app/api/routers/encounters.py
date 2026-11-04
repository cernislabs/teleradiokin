"""Encounter endpoints (visits linking a patient to imaging studies)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import AccessScope
from app.core.dependencies import (
    get_access_scope,
    get_current_user,
    require_clinical_write,
)
from app.domain.encounter import EncounterCreate, EncounterRead, EncounterUpdate
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


async def _visible_encounter_or_404(session, encounter_id, scope: AccessScope):
    encounter = await get_encounter(session, encounter_id)
    if encounter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    if not scope.cross_site:
        patient = await get_patient(session, encounter.patient_id)
        if patient is None or not scope.allows_org(patient.organization_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    return encounter


@router.get("", response_model=list[EncounterRead])
async def list_all(
    patient_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    return await list_encounters(
        session, scope=scope, patient_id=patient_id, limit=limit, offset=offset
    )


@router.post("", response_model=EncounterRead, status_code=status.HTTP_201_CREATED)
async def create(
    payload: EncounterCreate,
    scope: AccessScope = Depends(get_access_scope),
    current_user: User = Depends(require_clinical_write),
    session: AsyncSession = Depends(get_session),
):
    patient = await get_patient(session, payload.patient_id)
    if patient is None or not scope.allows_org(patient.organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return await create_encounter(
        session, payload, referring_clinician_id=current_user.id
    )


@router.get("/{encounter_id}", response_model=EncounterRead)
async def get_one(
    encounter_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _visible_encounter_or_404(session, encounter_id, scope)


@router.patch("/{encounter_id}", response_model=EncounterRead)
async def update(
    encounter_id: uuid.UUID,
    payload: EncounterUpdate,
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(require_clinical_write),
    session: AsyncSession = Depends(get_session),
):
    encounter = await _visible_encounter_or_404(session, encounter_id, scope)
    return await update_encounter(session, encounter, payload)
