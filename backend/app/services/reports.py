"""Report business logic: lifecycle (draft → final) and PDF rendering."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import AccessScope
from app.core.errors import ServiceError
from app.domain.enums import ReportStatus, StudyStatus
from app.domain.report import ReportCreate, ReportUpdate
from app.infrastructure.models.patient import Patient
from app.infrastructure.models.report import Report
from app.infrastructure.models.study import Study


async def get_report(session: AsyncSession, report_id: uuid.UUID) -> Report | None:
    return await session.get(Report, report_id)


async def get_report_visible(
    session: AsyncSession, report_id: uuid.UUID, scope: AccessScope
) -> Report | None:
    """Fetch a report only if the caller's scope may see it (else None → 404)."""
    report = await session.get(Report, report_id)
    if report is None:
        return None
    if scope.cross_site:
        return report
    patient = await session.get(Patient, report.patient_id)
    if patient is None or not scope.allows_org(patient.organization_id):
        return None
    return report


async def get_report_for_study(session: AsyncSession, study_id: uuid.UUID) -> Report | None:
    result = await session.execute(select(Report).where(Report.study_id == study_id))
    return result.scalar_one_or_none()


async def list_reports(
    session: AsyncSession,
    *,
    scope: AccessScope,
    patient_id: uuid.UUID | None = None,
    study_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Report]:
    stmt = select(Report).order_by(Report.created_at.desc())
    if not scope.cross_site:
        stmt = stmt.join(Patient, Report.patient_id == Patient.id).where(
            Patient.organization_id == scope.organization_id
        )
    if patient_id is not None:
        stmt = stmt.where(Report.patient_id == patient_id)
    if study_id is not None:
        stmt = stmt.where(Report.study_id == study_id)
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _apply_finalize(session: AsyncSession, report: Report, study: Study) -> None:
    report.finalized_at = datetime.now(timezone.utc)
    study.status = StudyStatus.REPORTED


async def create_report(
    session: AsyncSession, data: ReportCreate, author_id: uuid.UUID
) -> Report:
    study = await session.get(Study, data.study_id)
    if study is None:
        raise ServiceError(404, "Study not found")
    if await get_report_for_study(session, data.study_id) is not None:
        raise ServiceError(409, "A report already exists for this study")

    report = Report(
        study_id=study.id,
        patient_id=study.patient_id,
        author_id=author_id,
        status=data.status,
        findings=data.findings,
        impression=data.impression,
    )
    if data.status == ReportStatus.FINAL:
        await _apply_finalize(session, report, study)
    else:
        study.status = StudyStatus.IN_REVIEW
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def update_report(
    session: AsyncSession, report: Report, data: ReportUpdate
) -> Report:
    if report.status == ReportStatus.FINAL:
        raise ServiceError(409, "A finalized report cannot be edited")

    if data.findings is not None:
        report.findings = data.findings
    if data.impression is not None:
        report.impression = data.impression

    if data.status == ReportStatus.FINAL:
        study = await session.get(Study, report.study_id)
        if study is not None:
            await _apply_finalize(session, report, study)
        report.status = ReportStatus.FINAL

    await session.commit()
    await session.refresh(report)
    return report


def _latin1(text: str) -> str:
    """Core PDF fonts are Latin-1 only; keep that range (incl. French accents),
    replace anything outside it, and use a plain hyphen for em dashes."""
    return (text or "").replace("—", "-").encode("latin-1", "replace").decode("latin-1")


def render_pdf(report: Report, study: Study, patient) -> bytes:
    """Render a printable PDF of the report. Imported lazily to keep startup light."""
    from fpdf import FPDF

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Radiology Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    status_line = report.status.value
    if report.finalized_at:
        status_line += f" - {report.finalized_at:%Y-%m-%d %H:%M UTC}"
    pdf.cell(0, 6, _latin1(f"Status: {status_line}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Patient", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    birth = patient.birth_date.isoformat() if patient.birth_date else "-"
    pdf.multi_cell(
        0, 6,
        _latin1(
            f"{patient.family_name}, {patient.given_name}\n"
            f"MRN: {patient.mrn}    Sex: {patient.sex}    DOB: {birth}"
        ),
    )
    pdf.ln(1)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Study", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 6,
        _latin1(
            f"Modality: {study.modality or '-'}    Body part: {study.body_part or '-'}\n"
            f"Accession: {study.accession_number or '-'}    Study date: {study.study_date or '-'}"
        ),
    )
    pdf.ln(2)

    for title, body in (("Findings", report.findings), ("Impression", report.impression)):
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, _latin1(body or "-"))
        pdf.ln(2)

    out = pdf.output()
    return bytes(out)
