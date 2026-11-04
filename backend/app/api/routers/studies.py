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

from app.core.dependencies import get_current_user, get_storage, require_roles
from app.domain.enums import StudyStatus, UserRole
from app.domain.study import StudyRead, UploadInit, UploadSessionRead
from app.infrastructure.database import get_session
from app.infrastructure.models.study import UploadSession
from app.infrastructure.models.user import User
from app.infrastructure.storage import StudyStorage
from app.services import studies as svc

router = APIRouter(prefix="/api/studies", tags=["studies"])

_write_roles = require_roles(UserRole.ADMIN, UserRole.REFERRING_CLINICIAN)


def _handle(err: svc.UploadError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail=err.detail)


async def _get_upload(session: AsyncSession, upload_id: uuid.UUID) -> UploadSession:
    upload = await session.get(UploadSession, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return upload


# --- Chunked upload -------------------------------------------------------

@router.post("/uploads", response_model=UploadSessionRead, status_code=status.HTTP_201_CREATED)
async def open_upload(
    payload: UploadInit,
    current_user: User = Depends(_write_roles),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    try:
        return await svc.open_upload(
            session,
            encounter_id=payload.encounter_id,
            filename=payload.filename,
            content_type=payload.content_type,
            total_size=payload.total_size,
            created_by=current_user.id,
            storage=storage,
        )
    except svc.UploadError as err:
        raise _handle(err)


@router.get("/uploads/{upload_id}", response_model=UploadSessionRead)
async def get_upload(
    upload_id: uuid.UUID,
    _: User = Depends(_write_roles),
    session: AsyncSession = Depends(get_session),
):
    return await _get_upload(session, upload_id)


@router.put("/uploads/{upload_id}", response_model=UploadSessionRead)
async def append_chunk(
    upload_id: uuid.UUID,
    request: Request,
    offset: int = Query(..., ge=0),
    _: User = Depends(_write_roles),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    upload = await _get_upload(session, upload_id)
    data = await request.body()
    try:
        return await svc.append_chunk(
            session, upload, offset=offset, data=data, storage=storage
        )
    except svc.UploadError as err:
        raise _handle(err)


@router.post(
    "/uploads/{upload_id}/complete",
    response_model=StudyRead,
    status_code=status.HTTP_201_CREATED,
)
async def complete_upload(
    upload_id: uuid.UUID,
    request: Request,
    background: BackgroundTasks,
    _: User = Depends(_write_roles),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    upload = await _get_upload(session, upload_id)
    try:
        study = await svc.complete_upload(session, upload, storage=storage)
    except svc.UploadError as err:
        raise _handle(err)

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
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await svc.list_studies(
        session, status=status_filter, patient_id=patient_id, encounter_id=encounter_id
    )


@router.get("/{study_id}", response_model=StudyRead)
async def get_study(
    study_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    study = await svc.get_study(session, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found")
    return study


@router.get("/{study_id}/preview")
async def get_preview(
    study_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: StudyStorage = Depends(get_storage),
):
    study = await svc.get_study(session, study_id)
    if study is None or not study.preview_key:
        raise HTTPException(status_code=404, detail="Preview not available")
    return FileResponse(
        storage.full_path(study.preview_key),
        media_type="image/jpeg",
        filename=f"{study_id}.jpg",
    )
