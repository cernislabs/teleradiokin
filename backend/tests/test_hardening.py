"""Hardening tests: config fail-fast, storage safety, input caps, pagination, recovery."""
import pytest

from app.core.config import INSECURE_DEFAULT_JWT_KEY, Settings, validate_security
from app.domain.enums import StudyStatus, UserRole
from app.infrastructure.storage import LocalFilesystemStorage
from app.services.maintenance import recover_stale_processing
from tests.helpers import login, make_patient, make_study, make_user


# --- S2: config fail-fast -------------------------------------------------

def test_validate_security_rejects_default_key_in_production():
    settings = Settings(environment="production", jwt_key=INSECURE_DEFAULT_JWT_KEY)
    with pytest.raises(RuntimeError):
        validate_security(settings)


def test_validate_security_rejects_short_key_in_production():
    settings = Settings(environment="production", jwt_key="too-short")
    with pytest.raises(RuntimeError):
        validate_security(settings)


def test_validate_security_allows_development_defaults():
    validate_security(Settings(environment="development"))  # must not raise


def test_validate_security_allows_strong_key():
    validate_security(Settings(environment="production", jwt_key="x" * 48))


# --- S6 / C4: storage traversal + move ------------------------------------

def test_storage_rejects_traversal(tmp_path):
    storage = LocalFilesystemStorage(str(tmp_path / "store"))
    with pytest.raises(ValueError):
        storage.full_path("../escape.txt")


def test_storage_move_renames(tmp_path):
    storage = LocalFilesystemStorage(str(tmp_path / "store"))
    storage.append_bytes("tmp/a.bin", b"hello")
    storage.move("tmp/a.bin", "final/b.bin")
    assert not storage.exists("tmp/a.bin")
    assert storage.exists("final/b.bin")
    with storage.open("final/b.bin") as fh:
        assert fh.read() == b"hello"


# --- S4: extra JSONB size cap ---------------------------------------------

async def test_oversized_extra_rejected(client, db_session):
    await make_user(db_session, "c@x.io", UserRole.REFERRING_CLINICIAN)
    headers = await login(client, "c@x.io")
    resp = await client.post(
        "/api/patients",
        headers=headers,
        json={
            "mrn": "MRN-BIG", "family_name": "F", "given_name": "G",
            "sex": "male", "consent_acknowledged": True,
            "extra": {"blob": "x" * 20000},
        },
    )
    assert resp.status_code == 422


# --- C1: pagination -------------------------------------------------------

async def test_patient_list_pagination(client, db_session):
    await make_user(db_session, "rad@x.io", UserRole.RADIOLOGIST)
    for i in range(5):
        await make_patient(db_session, mrn=f"MRN-P{i}")
    headers = await login(client, "rad@x.io")

    page1 = await client.get("/api/patients?limit=2&offset=0", headers=headers)
    assert page1.status_code == 200
    assert len(page1.json()) == 2

    page3 = await client.get("/api/patients?limit=2&offset=4", headers=headers)
    assert len(page3.json()) == 1

    too_big = await client.get("/api/patients?limit=999", headers=headers)
    assert too_big.status_code == 422


# --- C2: stale-processing recovery ----------------------------------------

async def test_recover_stale_processing(db_session, _maker):
    patient = await make_patient(db_session, mrn="MRN-STUCK")
    study = await make_study(db_session, patient_id=patient.id, status=StudyStatus.PROCESSING)

    recovered = await recover_stale_processing(_maker)
    assert recovered == 1

    async with _maker() as verify:
        refreshed = await verify.get(type(study), study.id)
        assert refreshed.status == StudyStatus.FAILED
        assert refreshed.processing_error
