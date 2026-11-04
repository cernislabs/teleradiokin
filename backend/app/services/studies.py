"""Imaging-study upload pipeline and processing.

Upload is chunked/resumable for low-bandwidth, intermittent links:
  1. open a session (declare filename + total size),
  2. append chunks sequentially (resume by querying the current offset),
  3. complete — validate type/size/DICOM, store the object, create a Study, and
     schedule background metadata + preview extraction so CPU-heavy decoding never
     blocks the ASGI event loop.
"""
import asyncio
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.domain.enums import StudyStatus
from app.infrastructure.models.patient import Encounter
from app.infrastructure.models.study import Study, UploadSession
from app.infrastructure.storage import StudyStorage
from app.services.dicom import (
    generate_image_preview,
    is_valid_dicom,
    is_valid_image,
    process_dicom_file,
)

logger = logging.getLogger("studies")

DICOM_CONTENT_TYPES = {"application/dicom", "application/octet-stream", ""}
IMAGE_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png"}


class UploadError(Exception):
    """Validation/state error during upload; carries an HTTP status + detail."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# --- Queries --------------------------------------------------------------

async def get_study(session: AsyncSession, study_id: uuid.UUID) -> Study | None:
    return await session.get(Study, study_id)


async def list_studies(
    session: AsyncSession,
    *,
    status: StudyStatus | None = None,
    patient_id: uuid.UUID | None = None,
    encounter_id: uuid.UUID | None = None,
) -> list[Study]:
    stmt = select(Study).order_by(Study.created_at.desc())
    if status is not None:
        stmt = stmt.where(Study.status == status)
    if patient_id is not None:
        stmt = stmt.where(Study.patient_id == patient_id)
    if encounter_id is not None:
        stmt = stmt.where(Study.encounter_id == encounter_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# --- Chunked upload -------------------------------------------------------

async def open_upload(
    session: AsyncSession,
    *,
    encounter_id: uuid.UUID,
    filename: str,
    content_type: str | None,
    total_size: int,
    created_by: uuid.UUID | None,
    storage: StudyStorage,
) -> UploadSession:
    settings = get_settings()
    if total_size <= 0:
        raise UploadError(400, "total_size must be greater than zero")
    if total_size > settings.max_upload_bytes:
        raise UploadError(
            413, f"File exceeds the maximum of {settings.max_upload_bytes} bytes"
        )
    if await session.get(Encounter, encounter_id) is None:
        raise UploadError(404, "Encounter not found")

    upload = UploadSession(
        encounter_id=encounter_id,
        created_by=created_by,
        filename=filename,
        content_type=content_type,
        total_size=total_size,
        received_bytes=0,
        temp_key="",  # set after we have an id
        status="open",
    )
    session.add(upload)
    await session.flush()
    upload.temp_key = f"_uploads/{upload.id}"
    # Create the (empty) temp object so appends have a target.
    storage.append_bytes(upload.temp_key, b"")
    await session.commit()
    await session.refresh(upload)
    return upload


async def append_chunk(
    session: AsyncSession,
    upload: UploadSession,
    *,
    offset: int,
    data: bytes,
    storage: StudyStorage,
) -> UploadSession:
    settings = get_settings()
    if upload.status != "open":
        raise UploadError(409, "Upload session is not open")
    if offset != upload.received_bytes:
        raise UploadError(
            409, f"Unexpected offset; resume from {upload.received_bytes}"
        )
    if len(data) == 0:
        raise UploadError(400, "Empty chunk")
    if len(data) > settings.max_chunk_bytes:
        raise UploadError(413, "Chunk too large")
    if upload.received_bytes + len(data) > upload.total_size:
        raise UploadError(400, "Chunk exceeds declared total size")

    new_size = storage.append_bytes(upload.temp_key, data)
    upload.received_bytes = new_size
    await session.commit()
    await session.refresh(upload)
    return upload


def _classify(filename: str, content_type: str | None) -> str:
    """Return 'dicom' or 'image', or raise if unsupported."""
    name = filename.lower()
    ct = (content_type or "").lower()
    if name.endswith(".dcm") or ct == "application/dicom":
        return "dicom"
    if name.endswith((".jpg", ".jpeg", ".png")) or ct in IMAGE_CONTENT_TYPES:
        return "image"
    # octet-stream with no hint: try DICOM.
    if ct in DICOM_CONTENT_TYPES:
        return "dicom"
    raise UploadError(415, "Unsupported file type (expected DICOM or JPEG/PNG)")


async def complete_upload(
    session: AsyncSession,
    upload: UploadSession,
    *,
    storage: StudyStorage,
) -> Study:
    if upload.status != "open":
        raise UploadError(409, "Upload session is not open")
    if upload.received_bytes != upload.total_size:
        raise UploadError(
            400,
            f"Incomplete upload: {upload.received_bytes}/{upload.total_size} bytes",
        )

    kind = _classify(upload.filename, upload.content_type)
    temp_full = storage.full_path(upload.temp_key)

    if kind == "dicom" and not is_valid_dicom(temp_full):
        storage.delete(upload.temp_key)
        upload.status = "aborted"
        await session.commit()
        raise UploadError(400, "File is not a valid DICOM object")
    if kind == "image" and not is_valid_image(temp_full):
        storage.delete(upload.temp_key)
        upload.status = "aborted"
        await session.commit()
        raise UploadError(400, "File is not a valid image")

    encounter = await session.get(Encounter, upload.encounter_id)
    if encounter is None:
        raise UploadError(404, "Encounter not found")

    study_id = uuid.uuid4()
    suffix = Path(upload.filename).suffix or (".dcm" if kind == "dicom" else ".bin")
    storage_key = f"studies/{study_id}/original{suffix}"

    # Move the temp object into its final location.
    with storage.open(upload.temp_key) as fh:
        storage.save(storage_key, fh)
    storage.delete(upload.temp_key)

    study = Study(
        id=study_id,
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        status=StudyStatus.PROCESSING,
        storage_key=storage_key,
        original_filename=upload.filename,
        content_type=upload.content_type,
        size_bytes=upload.total_size,
        is_dicom=(kind == "dicom"),
    )
    session.add(study)
    upload.status = "completed"
    await session.commit()
    await session.refresh(study)
    return study


# --- Background processing ------------------------------------------------

async def process_study(
    session_factory: async_sessionmaker[AsyncSession],
    study_id: uuid.UUID,
    storage: StudyStorage,
) -> None:
    """Extract metadata + generate a preview. Runs as a background task."""
    async with session_factory() as session:
        study = await session.get(Study, study_id)
        if study is None:
            return
        source = storage.full_path(study.storage_key)
        preview_key = f"studies/{study_id}/preview.jpg"
        preview_full = storage.full_path(preview_key)
        try:
            if study.is_dicom:
                # Offload CPU-heavy pixel decoding off the event loop.
                meta = await asyncio.to_thread(process_dicom_file, source, preview_full)
                study.modality = meta.modality
                study.study_date = meta.study_date
                study.body_part = meta.body_part
                study.accession_number = meta.accession_number
                study.study_instance_uid = meta.study_instance_uid
                study.series_instance_uid = meta.series_instance_uid
                study.sop_instance_uid = meta.sop_instance_uid
            else:
                await asyncio.to_thread(generate_image_preview, source, preview_full)
            study.preview_key = preview_key
            study.status = StudyStatus.PENDING
            study.processing_error = None
        except Exception as exc:  # noqa: BLE001 - record failure, keep serving
            logger.exception("Study %s processing failed", study_id)
            study.status = StudyStatus.FAILED
            study.processing_error = str(exc)[:500]
        await session.commit()
