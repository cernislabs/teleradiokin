"""Structured report endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import AccessScope
from app.core.dependencies import (
    Auditor,
    get_access_scope,
    get_auditor,
    get_current_user,
    require_report_author,
)
from app.domain.enums import AuditAction, AuditEntity, ReportStatus
from app.domain.report import ReportCreate, ReportRead, ReportUpdate
from app.infrastructure.database import get_session
from app.infrastructure.models.patient import Patient
from app.infrastructure.models.study import Study
from app.infrastructure.models.user import User
from app.services import reports as svc

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("", response_model=list[ReportRead])
async def list_reports(
    study_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await svc.list_reports(
        session, scope=scope, patient_id=patient_id, study_id=study_id,
        limit=limit, offset=offset,
    )


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    current_user: User = Depends(require_report_author),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
):
    report = await svc.create_report(session, payload, author_id=current_user.id)
    action = (
        AuditAction.FINALIZE if report.status == ReportStatus.FINAL else AuditAction.CREATE
    )
    await auditor.log(action, AuditEntity.REPORT, report.id, {"study_id": str(report.study_id)})
    return report


@router.get("/{report_id}", response_model=ReportRead)
async def get_report(
    report_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    report = await svc.get_report_visible(session, report_id, scope)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.patch("/{report_id}", response_model=ReportRead)
async def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdate,
    _: User = Depends(require_report_author),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
):
    report = await svc.get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    updated = await svc.update_report(session, report, payload)
    action = (
        AuditAction.FINALIZE if updated.status == ReportStatus.FINAL else AuditAction.UPDATE
    )
    await auditor.log(action, AuditEntity.REPORT, updated.id)
    return updated


@router.get("/{report_id}/pdf")
async def report_pdf(
    report_id: uuid.UUID,
    scope: AccessScope = Depends(get_access_scope),
    auditor: Auditor = Depends(get_auditor),
    session: AsyncSession = Depends(get_session),
):
    report = await svc.get_report_visible(session, report_id, scope)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    study = await session.get(Study, report.study_id)
    patient = await session.get(Patient, report.patient_id)
    if study is None or patient is None:
        raise HTTPException(status_code=404, detail="Associated study/patient missing")

    auditor.log_async(AuditAction.DOWNLOAD, AuditEntity.REPORT, report.id)
    pdf_bytes = svc.render_pdf(report, study, patient)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="report-{report_id}.pdf"'},
    )
