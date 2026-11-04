import uuid

from app.domain.auth import UserCreate
from app.domain.enums import AdministrativeGender, StudyStatus, UserRole
from app.domain.patient import PatientCreate
from app.infrastructure.models.study import Study
from app.services.auth import create_user
from app.services.patients import create_patient


async def _login(client, email, password="password123"):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _user(db_session, email, role):
    await create_user(
        db_session, UserCreate(email=email, full_name="U", password="password123", role=role)
    )


async def _make_study(db_session, mrn="MRN-R1"):
    patient = await create_patient(
        db_session,
        PatientCreate(
            mrn=mrn, family_name="Rep", given_name="Ort",
            sex=AdministrativeGender.MALE, consent_acknowledged=True,
        ),
    )
    study = Study(
        encounter_id=uuid.uuid4(),
        patient_id=patient.id,
        status=StudyStatus.PENDING,
        storage_key="studies/x/original.dcm",
        original_filename="s.dcm",
        size_bytes=10,
        is_dicom=True,
        modality="CR",
        body_part="CHEST",
        accession_number="ACC-R",
    )
    db_session.add(study)
    await db_session.commit()
    await db_session.refresh(study)
    return study


async def test_radiologist_creates_and_finalizes_report(client, db_session):
    study = await _make_study(db_session)
    await _user(db_session, "rad@x.io", UserRole.RADIOLOGIST)
    headers = await _login(client, "rad@x.io")

    created = await client.post(
        "/api/reports",
        headers=headers,
        json={"study_id": str(study.id), "findings": "No acute abnormality.", "impression": "Normal."},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "Draft"
    report_id = body["id"]

    finalized = await client.patch(
        f"/api/reports/{report_id}", headers=headers, json={"status": "Final"}
    )
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "Final"
    assert finalized.json()["finalized_at"] is not None

    # Study transitions to Reported.
    study_resp = await client.get(f"/api/studies/{study.id}", headers=headers)
    assert study_resp.json()["status"] == "Reported"


async def test_final_report_cannot_be_edited(client, db_session):
    study = await _make_study(db_session)
    await _user(db_session, "rad@x.io", UserRole.RADIOLOGIST)
    headers = await _login(client, "rad@x.io")
    rid = (
        await client.post(
            "/api/reports",
            headers=headers,
            json={"study_id": str(study.id), "findings": "x", "impression": "y", "status": "Final"},
        )
    ).json()["id"]
    resp = await client.patch(f"/api/reports/{rid}", headers=headers, json={"findings": "edit"})
    assert resp.status_code == 409


async def test_duplicate_report_conflict(client, db_session):
    study = await _make_study(db_session)
    await _user(db_session, "rad@x.io", UserRole.RADIOLOGIST)
    headers = await _login(client, "rad@x.io")
    await client.post("/api/reports", headers=headers, json={"study_id": str(study.id)})
    dup = await client.post("/api/reports", headers=headers, json={"study_id": str(study.id)})
    assert dup.status_code == 409


async def test_clinician_cannot_create_report(client, db_session):
    study = await _make_study(db_session)
    await _user(db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    headers = await _login(client, "c@x.io")
    resp = await client.post("/api/reports", headers=headers, json={"study_id": str(study.id)})
    assert resp.status_code == 403


async def test_clinician_can_view_and_print_report(client, db_session):
    study = await _make_study(db_session)
    await _user(db_session, "rad@x.io", UserRole.RADIOLOGIST)
    await _user(db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    rad = await _login(client, "rad@x.io")
    rid = (
        await client.post(
            "/api/reports",
            headers=rad,
            json={"study_id": str(study.id), "findings": "f", "impression": "i", "status": "Final"},
        )
    ).json()["id"]

    clin = await _login(client, "c@x.io")
    view = await client.get(f"/api/reports/{rid}", headers=clin)
    assert view.status_code == 200

    pdf = await client.get(f"/api/reports/{rid}/pdf", headers=clin)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"
