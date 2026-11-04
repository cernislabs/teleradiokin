"""End-to-end smoke test: the full MVP flow through the HTTP API.

clinician: create patient -> encounter -> chunked DICOM upload -> complete
radiologist: worklist -> open file -> draft report -> finalize
clinician: download the report PDF
admin: inspect the audit trail covering the whole flow
"""
from app.domain.auth import UserCreate
from app.domain.enums import UserRole
from app.services.auth import create_user


async def _login(client, email, password="password123"):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _seed_users(db_session):
    for email, role in (
        ("admin@x.io", UserRole.ADMIN),
        ("rad@x.io", UserRole.RADIOLOGIST),
        ("clin@x.io", UserRole.REFERRING_CLINICIAN),
    ):
        await create_user(
            db_session,
            UserCreate(email=email, full_name=email, password="password123", role=role),
        )


async def test_full_upload_review_report_flow(client, db_session, sample_dicom_bytes):
    await _seed_users(db_session)

    # --- Referring clinician: patient + encounter + chunked upload --------
    clin = await _login(client, "clin@x.io")

    patient = (
        await client.post(
            "/api/patients",
            headers=clin,
            json={"mrn": "MRN-E2E", "family_name": "End", "given_name": "ToEnd",
                  "sex": "female", "consent_acknowledged": True},
        )
    ).json()

    enc = (
        await client.post(
            "/api/encounters", headers=clin,
            json={"patient_id": patient["id"], "reason": "Chest X-ray"},
        )
    ).json()

    data = sample_dicom_bytes
    upload = (
        await client.post(
            "/api/studies/uploads", headers=clin,
            json={"encounter_id": enc["id"], "filename": "chest.dcm",
                  "content_type": "application/dicom", "total_size": len(data)},
        )
    ).json()
    upload_id = upload["id"]

    # Two chunks (exercise resumable offsets).
    mid = len(data) // 2
    await client.put(f"/api/studies/uploads/{upload_id}?offset=0", headers=clin, content=data[:mid])
    await client.put(f"/api/studies/uploads/{upload_id}?offset={mid}", headers=clin, content=data[mid:])
    completed = await client.post(f"/api/studies/uploads/{upload_id}/complete", headers=clin)
    assert completed.status_code == 201
    study_id = completed.json()["id"]

    # Background task extracted metadata + preview -> Pending.
    study = (await client.get(f"/api/studies/{study_id}", headers=clin)).json()
    assert study["status"] == "Pending"
    assert study["modality"] == "CR"
    assert study["has_preview"] is True

    # --- Radiologist: worklist -> file -> report -------------------------
    rad = await _login(client, "rad@x.io")

    worklist = (await client.get("/api/studies?status=Pending", headers=rad)).json()
    assert any(s["id"] == study_id for s in worklist)

    file_resp = await client.get(f"/api/studies/{study_id}/file", headers=rad)
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"] == "application/dicom"

    report = (
        await client.post(
            "/api/reports", headers=rad,
            json={"study_id": study_id, "findings": "No acute abnormality.",
                  "impression": "Normal chest radiograph."},
        )
    ).json()
    report_id = report["id"]
    assert report["status"] == "Draft"

    finalized = await client.patch(f"/api/reports/{report_id}", headers=rad, json={"status": "Final"})
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "Final"

    # Study is now Reported.
    assert (await client.get(f"/api/studies/{study_id}", headers=rad)).json()["status"] == "Reported"

    # --- Referring clinician: download the PDF ---------------------------
    pdf = await client.get(f"/api/reports/{report_id}/pdf", headers=clin)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"

    # --- Admin: the audit trail covers the whole flow --------------------
    admin = await _login(client, "admin@x.io")
    events = (await client.get("/api/audit?limit=200", headers=admin)).json()

    def seen(action, entity, entity_id=None):
        return any(
            e["action"] == action
            and e["entity_type"] == entity
            and (entity_id is None or e["entity_id"] == entity_id)
            for e in events
        )

    assert seen("login", "session")
    assert seen("create", "patient", patient["id"])
    assert seen("create", "study", study_id)
    assert seen("view", "study", study_id)
    assert seen("download", "study", study_id)
    assert seen("finalize", "report", report_id)
    assert seen("download", "report", report_id)

    # Non-admins cannot read the audit trail.
    assert (await client.get("/api/audit", headers=rad)).status_code == 403
