"""Patient record endpoints.

Reads are available to any authenticated user (radiologists need patient context);
writes are limited to Admin and ReferringClinician.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.domain.enums import AuditAction, AuditEntity, UserRole
from app.domain.patient import PatientCreate, PatientRead, PatientUpdate
from app.infrastructure.database import get_session
from app.infrastructure.models.user import User
from app.services import audit
from app.services.patients import (
    create_patient,
    get_patient,
    get_patient_by_mrn,
    list_patients,
    update_patient,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])

_write_roles = require_roles(UserRole.ADMIN, UserRole.REFERRING_CLINICIAN)


@router.get("", response_model=list[PatientRead])
async def list_all(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    return await list_patients(session)


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create(
    payload: PatientCreate,
    request: Request,
    current_user: User = Depends(_write_roles),
    session: AsyncSession = Depends(get_session),
):
    if await get_patient_by_mrn(session, payload.mrn) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this MRN already exists",
        )
    patient = await create_patient(session, payload)
    await audit.record(
        session, actor=current_user, action=AuditAction.CREATE,
        entity_type=AuditEntity.PATIENT, entity_id=patient.id, request=request,
        detail={"mrn": patient.mrn},
    )
    return patient


@router.get("/{patient_id}", response_model=PatientRead)
async def get_one(
    patient_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    patient = await get_patient(session, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    await audit.record(
        session, actor=current_user, action=AuditAction.VIEW,
        entity_type=AuditEntity.PATIENT, entity_id=patient.id, request=request,
    )
    return patient


@router.patch("/{patient_id}", response_model=PatientRead)
async def update(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    request: Request,
    current_user: User = Depends(_write_roles),
    session: AsyncSession = Depends(get_session),
):
    patient = await get_patient(session, patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    updated = await update_patient(session, patient, payload)
    await audit.record(
        session, actor=current_user, action=AuditAction.UPDATE,
        entity_type=AuditEntity.PATIENT, entity_id=updated.id, request=request,
    )
    return updated
