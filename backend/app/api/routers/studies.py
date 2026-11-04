"""Imaging-study upload and retrieval endpoints."""
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import AccessScope
from app.core.dependencies import (
    Auditor,
    get_access_scope,
    get_auditor,
    get_current_user,
    get_storage,
    require_clinical_write,
)
from app.domain.enums import AuditAction, AuditEntity, StudyStatus
from app.domain.study import StudyRead, UploadInit, UploadSessionRead
from app.infrastructure.database import get_session
from app.infrastructure.models.study import UploadSession
from app.infrastructure.models.user import User
from app.infrastructure.storage import StudyStorage
from app.services import studies as svc
from app.services.encounters import get_encounter
from app.services.patients import get_patient

router = APIRouter(prefix="/api/studies", tags=["studies"])


async def _get_upload(session: AsyncSession, upload_id: uuid.UUID) -> UploadSession:
    upload = await session.get(UploadSession, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return upload


async def _require_encounter_in_scope(session, encounter_id, scope: AccessScope) -> None:
    """Reject upload against an encounter the caller's org may not touch."""
    if scope.cross_site:
        return
    encounter = await get_encounter(session, encounter_id)
    if encounter is not None:
        patient = await get_patient(session, encounter.patient_id)
        if patient is not None and scope.allows_org(patient.organization_id):
            return
    raise HTTPException(status_code=404, detail="Encounter not found")


# --- Chunked upload -------------------------------------------------------

@router.post("/uploads", response_model=UploadSessionRead, status_code=status.HTTP_201_CREATED)
async def open_upload(
    payload: UploadInit,
    scope: AccessScope = Depends(get_access_scope),
    current_user: User = Depends(require_clinical_write),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    await _require_encounter_in_scope(session, payload.encounter_id, scope)
    return await svc.open_upload(
        session,
        encounter_id=payload.encounter_id,
        filename=payload.filename,
        content_type=payload.content_type,
        total_size=payload.total_size,
        created_by=current_user.id,
        storage=storage,
    )


@router.get("/uploads/{upload_id}", response_model=UploadSessionRead)
async def get_upload(
    upload_id: uuid.UUID,
    _: User = Depends(require_clinical_write),
    session: AsyncSession = Depends(get_session),
):
    return await _get_upload(session, upload_id)


@router.put("/uploads/{upload_id}", response_model=UploadSessionRead)
async def append_chunk(
    upload_id: uuid.UUID,
    request: Request,
    offset: int = Query(..., ge=0),
    _: User = Depends(require_clinical_write),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    upload = await _get_upload(session, upload_id)
    data = await request.body()
    return await svc.append_chunk(
        session, upload, offset=offset, data=data, storage=storage
    )


@router.post(
    "/uploads/{upload_id}/complete",
    response_model=StudyRead,
    status_code=status.HTTP_201_CREATED,
)
async def complete_upload(
    upload_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    current_user: User = Depends(require_clinical_write),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    upload = await _get_upload(session, upload_id)
    study = await svc.complete_upload(session, upload, storage=storage)
    await auditor.log(
        AuditAction.CREATE, AuditEntity.STUDY, study.id,
        {"filename": study.original_filename, "patient_id": str(study.patient_id)},
    )
    # Extract metadata + preview off the request path.
    background.add_task(
        svc.process_study, request.app.state.session_factory, study.id, storage
    )
    return study


# --- Retrieval ------------------------------------------------------------

@router.get("", response_model=list[StudyRead])
async def list_studies(
    status_filter: StudyStatus | None = Query(default=None, alias="status"),
    patient_id: uuid.UUID | None = None,
    encounter_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await svc.list_studies(
        session, scope=scope, status=status_filter,
        patient_id=patient_id, encounter_id=encounter_id, limit=limit, offset=offset,
    )


@router.get("/{study_id}", response_model=StudyRead)
async def get_study(
    study_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
):
    study = await svc.get_study_visible(session, study_id, scope)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    auditor.log_async(AuditAction.VIEW, AuditEntity.STUDY, study.id)
    return study


@router.get("/{study_id}/file")
async def get_file(
    study_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    """Serve the original stored object (fed to the in-browser DICOM viewer)."""
    study = await svc.get_study_visible(session, study_id, scope)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    auditor.log_async(AuditAction.DOWNLOAD, AuditEntity.STUDY, study.id)
    media_type = "application/dicom" if study.is_dicom else (
        study.content_type or "application/octet-stream"
    )
    return FileResponse(
        storage.full_path(study.storage_key),
        media_type=media_type,
        filename=study.original_filename,
    )


@router.get("/{study_id}/preview")
async def get_preview(
    study_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    study = await svc.get_study_visible(session, study_id, scope)
    if study is None or not study.preview_key:
        raise HTTPException(status_code=404, detail="Preview not available")
    return FileResponse(
        storage.full_path(study.preview_key),
        media_type="image/jpeg",
        filename=f"{study_id}.jpg",
    )
