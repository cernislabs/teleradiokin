"""Audit-trail tests: events are recorded on key actions and queryable by admins."""
from app.domain.enums import UserRole
from tests.helpers import login as _login
from tests.helpers import make_patient, make_study
from tests.helpers import make_user as _user


async def _make_study(db_session, mrn="MRN-A1"):
    patient = await make_patient(db_session, mrn=mrn)
    study = await make_study(db_session, patient_id=patient.id)
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
