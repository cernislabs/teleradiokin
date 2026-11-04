"""Structured report endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.domain.enums import AuditAction, AuditEntity, ReportStatus, UserRole
from app.domain.report import ReportCreate, ReportRead, ReportUpdate
from app.infrastructure.database import get_session
from app.infrastructure.models.patient import Patient
from app.infrastructure.models.study import Study
from app.infrastructure.models.user import User
from app.services import audit
from app.services import reports as svc

router = APIRouter(prefix="/api/reports", tags=["reports"])

_author_roles = require_roles(UserRole.RADIOLOGIST, UserRole.ADMIN)


def _handle(err: svc.ReportError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail=err.detail)


@router.get("", response_model=list[ReportRead])
async def list_reports(
    study_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await svc.list_reports(session, patient_id=patient_id, study_id=study_id)


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
async def create_report(
    payload: ReportCreate,
    request: Request,
    current_user: User = Depends(_author_roles),
    session: AsyncSession = Depends(get_session),
):
    try:
        report = await svc.create_report(session, payload, author_id=current_user.id)
    except svc.ReportError as err:
        raise _handle(err)
    action = (
        AuditAction.FINALIZE if report.status == ReportStatus.FINAL else AuditAction.CREATE
    )
    await audit.record(
        session, actor=current_user, action=action,
        entity_type=AuditEntity.REPORT, entity_id=report.id, request=request,
        detail={"study_id": str(report.study_id)},
    )
    return report


@router.get("/{report_id}", response_model=ReportRead)
async def get_report(
    report_id: uuid.UUID,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    report = await svc.get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.patch("/{report_id}", response_model=ReportRead)
async def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdate,
    request: Request,
    current_user: User = Depends(_author_roles),
    session: AsyncSession = Depends(get_session),
):
    report = await svc.get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        updated = await svc.update_report(session, report, payload)
    except svc.ReportError as err:
        raise _handle(err)
    action = (
        AuditAction.FINALIZE if updated.status == ReportStatus.FINAL else AuditAction.UPDATE
    )
    await audit.record(
        session, actor=current_user, action=action,
        entity_type=AuditEntity.REPORT, entity_id=updated.id, request=request,
    )
    return updated


@router.get("/{report_id}/pdf")
async def report_pdf(
    report_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    report = await svc.get_report(session, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    study = await session.get(Study, report.study_id)
    patient = await session.get(Patient, report.patient_id)
    if study is None or patient is None:
        raise HTTPException(status_code=404, detail="Associated study/patient missing")

    await audit.record(
        session, actor=current_user, action=AuditAction.DOWNLOAD,
        entity_type=AuditEntity.REPORT, entity_id=report.id, request=request,
    )
    pdf_bytes = svc.render_pdf(report, study, patient)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="report-{report_id}.pdf"'},
    )
