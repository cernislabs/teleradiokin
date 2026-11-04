"""Idempotent seeding of initial accounts.

Runs on application startup (after migrations). Creates one Admin, one
Radiologist, and one ReferringClinician when they do not already exist and when
their passwords are configured via environment variables.
"""
import logging
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.domain.enums import AdministrativeGender, EncounterStatus, UserRole
from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.models.patient import Encounter, Patient
from app.infrastructure.models.user import User

logger = logging.getLogger("seed")

SAMPLE_MRN = "MRN-0001"


async def seed_initial_data() -> None:
    settings = get_settings()
    seeds = [
        ("admin@teleradiokin.org", "System Administrator",
         UserRole.ADMIN, settings.seed_admin_password),
        ("radiologist@teleradiokin.org", "Dr. Remote Radiologist",
         UserRole.RADIOLOGIST, settings.seed_radiologist_password),
        ("clinician@teleradiokin.org", "Dr. Referring Clinician",
         UserRole.REFERRING_CLINICIAN, settings.seed_clinician_password),
    ]

    async with AsyncSessionLocal() as session:
        created = 0
        for email, full_name, role, password in seeds:
            if not password:
                logger.warning("No seed password for %s; skipping.", role)
                continue
            exists = await session.execute(select(User).where(User.email == email))
            if exists.scalar_one_or_none() is not None:
                continue
            session.add(
                User(
                    email=email,
                    full_name=full_name,
                    hashed_password=hash_password(password),
                    role=role,
                    is_active=True,
                )
            )
            created += 1
            logger.info("Seeded %s account: %s", role.value, email)
        if created:
            await session.commit()

        await _seed_sample_patient(session)


async def _seed_sample_patient(session) -> None:
    exists = await session.execute(select(Patient).where(Patient.mrn == SAMPLE_MRN))
    patient = exists.scalar_one_or_none()
    if patient is not None:
        return

    patient = Patient(
        mrn=SAMPLE_MRN,
        family_name="Doe",
        given_name="Jane",
        birth_date=date(1990, 5, 17),
        sex=AdministrativeGender.FEMALE,
        phone="+243000000000",
        consent_acknowledged=True,
        consent_acknowledged_at=datetime.now(timezone.utc),
        extra={"notes": "Seeded sample patient"},
    )
    session.add(patient)
    await session.flush()

    # Link a referring clinician to a sample encounter when one exists.
    clinician = (
        await session.execute(
            select(User).where(User.role == UserRole.REFERRING_CLINICIAN)
        )
    ).scalar_one_or_none()

    session.add(
        Encounter(
            patient_id=patient.id,
            referring_clinician_id=clinician.id if clinician else None,
            status=EncounterStatus.PLANNED,
            reason="Initial consultation — chest imaging requested",
        )
    )
    await session.commit()
    logger.info("Seeded sample patient %s", SAMPLE_MRN)
