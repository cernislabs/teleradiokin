"""Audit-trail tests: events are recorded on key actions and queryable by admins."""
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


async def _make_study(db_session, mrn="MRN-A1"):
    patient = await create_patient(
        db_session,
        PatientCreate(
            mrn=mrn, family_name="Aud", given_name="It",
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
    )
    db_session.add(study)
    await db_session.commit()
    await db_session.refresh(study)
    return patient, study


async def test_login_is_audited(client, db_session):
    await _user(db_session, "admin@x.io", UserRole.ADMIN)
    headers = await _login(client, "admin@x.io")

    events = await client.get("/api/audit", headers=headers, params={"action": "login"})
    assert events.status_code == 200
    body = events.json()
    assert len(body) >= 1
    assert body[0]["action"] == "login"
    assert body[0]["entity_type"] == "session"
    assert body[0]["actor_email"] == "admin@x.io"


async def test_audit_requires_admin(client, db_session):
    await _user(db_session, "rad@x.io", UserRole.RADIOLOGIST)
    headers = await _login(client, "rad@x.io")
    resp = await client.get("/api/audit", headers=headers)
    assert resp.status_code == 403


async def test_patient_view_and_create_audited(client, db_session):
    await _user(db_session, "admin@x.io", UserRole.ADMIN)
    await _user(db_session, "clin@x.io", UserRole.REFERRING_CLINICIAN)
    clin = await _login(client, "clin@x.io")

    created = await client.post(
        "/api/patients",
        headers=clin,
        json={"mrn": "MRN-AUD9", "family_name": "F", "given_name": "G",
              "sex": "female", "consent_acknowledged": True},
    )
    assert created.status_code == 201
    patient_id = created.json()["id"]

    viewed = await client.get(f"/api/patients/{patient_id}", headers=clin)
    assert viewed.status_code == 200

    admin = await _login(client, "admin@x.io")
    events = await client.get(
        "/api/audit", headers=admin,
        params={"entity_type": "patient", "entity_id": patient_id},
    )
    assert events.status_code == 200
    actions = {e["action"] for e in events.json()}
    assert {"create", "view"} <= actions
    # Every event carries the acting clinician's identity.
    assert all(e["actor_email"] == "clin@x.io" for e in events.json())


async def test_report_finalize_audited(client, db_session):
    await _user(db_session, "admin@x.io", UserRole.ADMIN)
    await _user(db_session, "rad@x.io", UserRole.RADIOLOGIST)
    _, study = await _make_study(db_session)
    rad = await _login(client, "rad@x.io")

    report = await client.post(
        "/api/reports", headers=rad,
        json={"study_id": str(study.id), "findings": "f", "impression": "i", "status": "Final"},
    )
    assert report.status_code == 201
    report_id = report.json()["id"]

    admin = await _login(client, "admin@x.io")
    events = await client.get(
        "/api/audit", headers=admin,
        params={"entity_type": "report", "entity_id": report_id},
    )
    assert events.status_code == 200
    assert any(e["action"] == "finalize" for e in events.json())


async def test_audit_filter_by_action(client, db_session):
    await _user(db_session, "admin@x.io", UserRole.ADMIN)
    admin = await _login(client, "admin@x.io")
    resp = await client.get("/api/audit", headers=admin, params={"action": "view"})
    assert resp.status_code == 200
    assert all(e["action"] == "view" for e in resp.json())
