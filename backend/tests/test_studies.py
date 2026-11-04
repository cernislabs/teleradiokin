import pytest

from app.domain.auth import UserCreate
from app.domain.enums import UserRole
from app.services.auth import create_user


async def _login(client, email, password="password123"):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _setup_encounter(client, db_session, role=UserRole.REFERRING_CLINICIAN, email="c@x.io"):
    await create_user(
        db_session, UserCreate(email=email, full_name="C", password="password123", role=role)
    )
    headers = await _login(client, email)
    patient = (
        await client.post(
            "/api/patients",
            headers=headers,
            json={
                "mrn": "MRN-900",
                "family_name": "Up",
                "given_name": "Load",
                "sex": "male",
                "consent_acknowledged": True,
            },
        )
    ).json()
    enc = (
        await client.post(
            "/api/encounters", headers=headers, json={"patient_id": patient["id"], "reason": "CXR"}
        )
    ).json()
    return headers, enc["id"]


async def _open(client, headers, encounter_id, filename, content_type, size):
    return await client.post(
        "/api/studies/uploads",
        headers=headers,
        json={
            "encounter_id": encounter_id,
            "filename": filename,
            "content_type": content_type,
            "total_size": size,
        },
    )


# --- Happy path: chunked DICOM upload → processed ------------------------

async def test_chunked_dicom_upload_processes(client, db_session, sample_dicom_bytes):
    headers, enc_id = await _setup_encounter(client, db_session)
    data = sample_dicom_bytes
    opened = await _open(client, headers, enc_id, "chest.dcm", "application/dicom", len(data))
    assert opened.status_code == 201
    upload_id = opened.json()["id"]

    # Upload in two chunks to exercise resumable offsets.
    mid = len(data) // 2
    r1 = await client.put(
        f"/api/studies/uploads/{upload_id}?offset=0", headers=headers, content=data[:mid]
    )
    assert r1.status_code == 200
    assert r1.json()["received_bytes"] == mid

    r2 = await client.put(
        f"/api/studies/uploads/{upload_id}?offset={mid}", headers=headers, content=data[mid:]
    )
    assert r2.json()["received_bytes"] == len(data)

    completed = await client.post(f"/api/studies/uploads/{upload_id}/complete", headers=headers)
    assert completed.status_code == 201
    study_id = completed.json()["id"]

    # Background processing should have populated metadata + preview.
    got = await client.get(f"/api/studies/{study_id}", headers=headers)
    body = got.json()
    assert body["status"] == "Pending"
    assert body["is_dicom"] is True
    assert body["modality"] == "CR"
    assert body["body_part"] == "CHEST"
    assert body["has_preview"] is True

    preview = await client.get(f"/api/studies/{study_id}/preview", headers=headers)
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/jpeg"


# --- Resume + offset errors ----------------------------------------------

async def test_study_file_served(client, db_session, sample_dicom_bytes):
    headers, enc_id = await _setup_encounter(client, db_session)
    data = sample_dicom_bytes
    up = (await _open(client, headers, enc_id, "c.dcm", "application/dicom", len(data))).json()["id"]
    await client.put(f"/api/studies/uploads/{up}?offset=0", headers=headers, content=data)
    study_id = (await client.post(f"/api/studies/uploads/{up}/complete", headers=headers)).json()["id"]

    resp = await client.get(f"/api/studies/{study_id}/file", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/dicom"
    assert len(resp.content) == len(data)


async def test_resume_reports_offset(client, db_session, sample_dicom_bytes):
    headers, enc_id = await _setup_encounter(client, db_session)
    data = sample_dicom_bytes
    upload_id = (await _open(client, headers, enc_id, "c.dcm", "application/dicom", len(data))).json()["id"]

    await client.put(f"/api/studies/uploads/{upload_id}?offset=0", headers=headers, content=data[:10])
    # Query progress (simulating a resume after disconnect).
    status = await client.get(f"/api/studies/uploads/{upload_id}", headers=headers)
    assert status.json()["received_bytes"] == 10

    # Wrong offset is rejected.
    bad = await client.put(
        f"/api/studies/uploads/{upload_id}?offset=5", headers=headers, content=data[10:]
    )
    assert bad.status_code == 409


# --- Validation -----------------------------------------------------------

async def test_invalid_dicom_rejected_on_complete(client, db_session):
    headers, enc_id = await _setup_encounter(client, db_session)
    junk = b"this is definitely not a dicom file"
    upload_id = (await _open(client, headers, enc_id, "bad.dcm", "application/dicom", len(junk))).json()["id"]
    await client.put(f"/api/studies/uploads/{upload_id}?offset=0", headers=headers, content=junk)
    completed = await client.post(f"/api/studies/uploads/{upload_id}/complete", headers=headers)
    assert completed.status_code == 400


async def test_incomplete_upload_cannot_complete(client, db_session, sample_dicom_bytes):
    headers, enc_id = await _setup_encounter(client, db_session)
    data = sample_dicom_bytes
    upload_id = (await _open(client, headers, enc_id, "c.dcm", "application/dicom", len(data))).json()["id"]
    await client.put(f"/api/studies/uploads/{upload_id}?offset=0", headers=headers, content=data[:5])
    completed = await client.post(f"/api/studies/uploads/{upload_id}/complete", headers=headers)
    assert completed.status_code == 400


# --- Authorization --------------------------------------------------------

async def test_radiologist_cannot_open_upload(client, db_session):
    headers, enc_id = await _setup_encounter(client, db_session)  # clinician setup
    rad_headers = await _setup_rad(client, db_session)
    resp = await client.post(
        "/api/studies/uploads",
        headers=rad_headers,
        json={"encounter_id": enc_id, "filename": "x.dcm", "content_type": "application/dicom", "total_size": 10},
    )
    assert resp.status_code == 403


async def _setup_rad(client, db_session):
    await create_user(
        db_session, UserCreate(email="r@x.io", full_name="R", password="password123", role=UserRole.RADIOLOGIST)
    )
    return await _login(client, "r@x.io")
