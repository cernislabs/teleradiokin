import pytest

from app.domain.auth import UserCreate
from app.domain.enums import UserRole
from app.services.auth import create_user


async def _user(session, email, role, password="password123"):
    await create_user(
        session, UserCreate(email=email, full_name="T", password=password, role=role)
    )


async def _token(client, email, password="password123"):
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _patient_payload(**overrides):
    base = {
        "mrn": "MRN-100",
        "family_name": "Doe",
        "given_name": "John",
        "birth_date": "1985-02-01",
        "sex": "male",
        "consent_acknowledged": True,
    }
    base.update(overrides)
    return base


async def _auth_header(client, db_session, email, role):
    await _user(db_session, email, role)
    token = await _token(client, email)
    return {"Authorization": f"Bearer {token}"}


# --- Creation & consent ---------------------------------------------------

async def test_clinician_creates_patient(client, db_session):
    headers = await _auth_header(client, db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    resp = await client.post("/api/patients", json=_patient_payload(), headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["mrn"] == "MRN-100"
    assert body["consent_acknowledged"] is True
    assert body["consent_acknowledged_at"] is not None


async def test_create_patient_requires_consent(client, db_session):
    headers = await _auth_header(client, db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    resp = await client.post(
        "/api/patients", json=_patient_payload(consent_acknowledged=False), headers=headers
    )
    assert resp.status_code == 422


async def test_duplicate_mrn_conflict(client, db_session):
    headers = await _auth_header(client, db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    await client.post("/api/patients", json=_patient_payload(), headers=headers)
    resp = await client.post("/api/patients", json=_patient_payload(), headers=headers)
    assert resp.status_code == 409


# --- Authorization --------------------------------------------------------

async def test_radiologist_cannot_create_patient(client, db_session):
    headers = await _auth_header(client, db_session, "r@x.io", UserRole.RADIOLOGIST)
    resp = await client.post("/api/patients", json=_patient_payload(), headers=headers)
    assert resp.status_code == 403


async def test_radiologist_can_read_patients(client, db_session):
    # clinician creates, radiologist reads
    chdr = await _auth_header(client, db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    await client.post("/api/patients", json=_patient_payload(), headers=chdr)
    rhdr = await _auth_header(client, db_session, "r@x.io", UserRole.RADIOLOGIST)
    resp = await client.get("/api/patients", headers=rhdr)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_patient_requires_auth(client):
    resp = await client.get("/api/patients")
    assert resp.status_code in (401, 403)


# --- Retrieve / update ----------------------------------------------------

async def test_get_and_update_patient(client, db_session):
    headers = await _auth_header(client, db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    created = (await client.post("/api/patients", json=_patient_payload(), headers=headers)).json()
    pid = created["id"]

    got = await client.get(f"/api/patients/{pid}", headers=headers)
    assert got.status_code == 200

    upd = await client.patch(f"/api/patients/{pid}", json={"phone": "+243111222333"}, headers=headers)
    assert upd.status_code == 200
    assert upd.json()["phone"] == "+243111222333"


# --- Encounters -----------------------------------------------------------

async def test_create_encounter_for_patient(client, db_session):
    headers = await _auth_header(client, db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    patient = (await client.post("/api/patients", json=_patient_payload(), headers=headers)).json()

    resp = await client.post(
        "/api/encounters",
        json={"patient_id": patient["id"], "reason": "Chest X-ray"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["patient_id"] == patient["id"]
    assert body["referring_clinician_id"] is not None
    assert body["status"] == "planned"

    listed = await client.get(f"/api/encounters?patient_id={patient['id']}", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_encounter_missing_patient_404(client, db_session):
    headers = await _auth_header(client, db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    resp = await client.post(
        "/api/encounters",
        json={"patient_id": "00000000-0000-0000-0000-000000000000", "reason": "x"},
        headers=headers,
    )
    assert resp.status_code == 404
