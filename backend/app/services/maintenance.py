"""Background/startup maintenance: self-healing and garbage collection.

Processing runs in-process via ``BackgroundTasks`` (see ADR-008); if the server
is killed mid-task a study is left ``PROCESSING`` with nothing to finish it, and
abandoned chunked uploads leave orphaned temp files and rows. These routines,
run at startup, keep the system consistent without an external task queue — the
MVP mitigation for that deferred work (see ADR-017).
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.enums import StudyStatus
from app.infrastructure.models.study import Study, UploadSession
from app.infrastructure.storage import StudyStorage

logger = logging.getLogger("maintenance")


async def recover_stale_processing(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Fail studies stuck in PROCESSING. Run at startup: no decode task survives a
    restart, so any PROCESSING row is orphaned and must be marked FAILED (the
    clinician can re-upload) rather than lingering forever."""
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Study).where(Study.status == StudyStatus.PROCESSING)
            )
        ).scalars().all()
        for study in rows:
            study.status = StudyStatus.FAILED
            study.processing_error = (
                "Processing did not finish (server restarted); please re-upload."
            )
        if rows:
            await session.commit()
            logger.warning("Recovered %d stale PROCESSING studies", len(rows))
        return len(rows)


async def purge_stale_uploads(
    session_factory: async_sessionmaker[AsyncSession],
    storage: StudyStorage,
    older_than_hours: int = 24,
) -> int:
    """Delete abandoned upload sessions (opened, never completed) and their temp
    objects once they are older than the TTL, reclaiming disk and rows."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(UploadSession).where(
                    UploadSession.status == "open",
                    UploadSession.created_at < cutoff,
                )
            )
        ).scalars().all()
        for upload in rows:
            if upload.temp_key:
                try:
                    storage.delete(upload.temp_key)
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    logger.exception("Failed to delete temp object %s", upload.temp_key)
            await session.delete(upload)
        if rows:
            await session.commit()
            logger.info("Purged %d stale upload sessions", len(rows))
        return len(rows)
