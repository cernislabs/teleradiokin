from app.domain.enums import UserRole
from tests.helpers import login as _login
from tests.helpers import make_patient, make_study
from tests.helpers import make_user as _user


async def _make_study(db_session, mrn="MRN-R1"):
    patient = await make_patient(db_session, mrn=mrn)
    return await make_study(db_session, patient_id=patient.id)


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
