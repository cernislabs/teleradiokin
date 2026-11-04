"""Shared test helpers (consolidated so each test module stops re-defining them)."""
import uuid

from app.domain.auth import UserCreate
from app.domain.enums import AdministrativeGender, StudyStatus, UserRole
from app.domain.patient import PatientCreate
from app.infrastructure.models.study import Study
from app.services.auth import create_user
from app.services.patients import create_patient

DEFAULT_PASSWORD = "password123"


async def make_user(session, email, role, *, password=DEFAULT_PASSWORD, organization_id=None):
    return await create_user(
        session,
        UserCreate(
            email=email, full_name="Test User", password=password,
            role=role, organization_id=organization_id,
        ),
    )


async def login(client, email, password=DEFAULT_PASSWORD) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def auth_headers(client, session, email, role, *, organization_id=None):
    await make_user(session, email, role, organization_id=organization_id)
    return await login(client, email)


async def make_patient(session, *, mrn="MRN-1", organization_id=None, **overrides):
    data = {
        "mrn": mrn,
        "family_name": "Fam",
        "given_name": "Giv",
        "sex": AdministrativeGender.MALE,
        "consent_acknowledged": True,
    }
    data.update(overrides)
    return await create_patient(session, PatientCreate(**data), organization_id=organization_id)


async def make_study(session, *, patient_id, encounter_id=None, status=StudyStatus.PENDING, **overrides):
    fields = {
        "encounter_id": encounter_id or uuid.uuid4(),
        "patient_id": patient_id,
        "status": status,
        "storage_key": "studies/x/original.dcm",
        "original_filename": "s.dcm",
        "size_bytes": 10,
        "is_dicom": True,
        "modality": "CR",
        "body_part": "CHEST",
        "accession_number": "ACC",
    }
    fields.update(overrides)
    study = Study(**fields)
    session.add(study)
    await session.commit()
    await session.refresh(study)
    return study
