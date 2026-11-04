"""Object-level authorization: clinicians are scoped to their organization."""
import uuid

from app.domain.enums import UserRole
from app.infrastructure.models.organization import Organization
from tests.helpers import login, make_patient, make_study, make_user


async def _org(db_session, name):
    org = Organization(name=name)
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


async def test_clinician_cannot_see_other_org_patient(client, db_session):
    org_a = await _org(db_session, "Site A")
    org_b = await _org(db_session, "Site B")
    await make_user(db_session, "a@x.io", UserRole.REFERRING_CLINICIAN, organization_id=org_a.id)
    patient_b = await make_patient(db_session, mrn="MRN-B", organization_id=org_b.id)

    headers = await login(client, "a@x.io")

    # Not in the list...
    listed = await client.get("/api/patients", headers=headers)
    assert all(p["id"] != str(patient_b.id) for p in listed.json())

    # ...and a direct fetch is 404 (not 403 — existence is not leaked).
    direct = await client.get(f"/api/patients/{patient_b.id}", headers=headers)
    assert direct.status_code == 404


async def test_clinician_sees_own_org_patient(client, db_session):
    org_a = await _org(db_session, "Site A")
    await make_user(db_session, "a@x.io", UserRole.REFERRING_CLINICIAN, organization_id=org_a.id)
    patient_a = await make_patient(db_session, mrn="MRN-A", organization_id=org_a.id)

    headers = await login(client, "a@x.io")
    direct = await client.get(f"/api/patients/{patient_a.id}", headers=headers)
    assert direct.status_code == 200
    listed = await client.get("/api/patients", headers=headers)
    assert any(p["id"] == str(patient_a.id) for p in listed.json())


async def test_radiologist_is_cross_site(client, db_session):
    org_a = await _org(db_session, "Site A")
    org_b = await _org(db_session, "Site B")
    await make_user(db_session, "rad@x.io", UserRole.RADIOLOGIST)  # no org
    pa = await make_patient(db_session, mrn="MRN-A", organization_id=org_a.id)
    pb = await make_patient(db_session, mrn="MRN-B", organization_id=org_b.id)

    headers = await login(client, "rad@x.io")
    assert (await client.get(f"/api/patients/{pa.id}", headers=headers)).status_code == 200
    assert (await client.get(f"/api/patients/{pb.id}", headers=headers)).status_code == 200


async def test_clinician_cannot_view_other_org_study(client, db_session):
    org_a = await _org(db_session, "Site A")
    org_b = await _org(db_session, "Site B")
    await make_user(db_session, "a@x.io", UserRole.REFERRING_CLINICIAN, organization_id=org_a.id)
    patient_b = await make_patient(db_session, mrn="MRN-B", organization_id=org_b.id)
    study_b = await make_study(db_session, patient_id=patient_b.id)

    headers = await login(client, "a@x.io")
    assert (await client.get(f"/api/studies/{study_b.id}", headers=headers)).status_code == 404
    assert (await client.get(f"/api/studies/{study_b.id}/file", headers=headers)).status_code == 404


async def test_missing_study_is_404(client, db_session):
    await make_user(db_session, "rad@x.io", UserRole.RADIOLOGIST)
    headers = await login(client, "rad@x.io")
    resp = await client.get(f"/api/studies/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404
