"""Patient record endpoints.

Reads are available to any authenticated user but scoped by organization
(clinicians see only their site; radiologists/admins are cross-site). Writes are
limited to Admin and ReferringClinician.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import AccessScope
from app.core.dependencies import (
    Auditor,
    get_access_scope,
    get_auditor,
    get_current_user,
    require_clinical_write,
)
from app.domain.enums import AuditAction, AuditEntity
from app.domain.patient import PatientCreate, PatientRead, PatientUpdate
from app.infrastructure.database import get_session
from app.infrastructure.models.user import User
from app.services.patients import (
    create_patient,
    get_patient,
    get_patient_by_mrn,
    list_patients,
    update_patient,
)

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("", response_model=list[PatientRead])
async def list_all(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    return await list_patients(session, scope=scope, limit=limit, offset=offset)


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create(
    payload: PatientCreate,
    current_user: User = Depends(require_clinical_write),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
):
    if await get_patient_by_mrn(session, payload.mrn) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this MRN already exists",
        )
    patient = await create_patient(
        session, payload, organization_id=current_user.organization_id
    )
    await auditor.log(
        AuditAction.CREATE, AuditEntity.PATIENT, patient.id, {"mrn": patient.mrn}
    )
    return patient


@router.get("/{patient_id}", response_model=PatientRead)
async def get_one(
    patient_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
):
    patient = await get_patient(session, patient_id)
    if patient is None or not scope.allows_org(patient.organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    auditor.log_async(AuditAction.VIEW, AuditEntity.PATIENT, patient.id)
    return patient


@router.patch("/{patient_id}", response_model=PatientRead)
async def update(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(require_clinical_write),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
):
    patient = await get_patient(session, patient_id)
    if patient is None or not scope.allows_org(patient.organization_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    updated = await update_patient(session, patient, payload)
    await auditor.log(AuditAction.UPDATE, AuditEntity.PATIENT, updated.id)
    return updated
