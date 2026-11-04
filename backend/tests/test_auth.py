import pytest

from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.domain.auth import UserCreate
from app.domain.enums import UserRole
from app.services.auth import create_user


async def _make_user(session, email, password, role):
    return await create_user(
        session,
        UserCreate(email=email, full_name="Test User", password=password, role=role),
    )


# --- Unit: security primitives -------------------------------------------

def test_password_hash_roundtrip():
    hashed = hash_password("S3cret!pass")
    assert hashed != "S3cret!pass"
    assert verify_password("S3cret!pass", hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip():
    token = create_access_token(subject="abc", roles=["Admin"])
    payload = decode_token(token)
    assert payload["sub"] == "abc"
    assert payload["roles"] == ["Admin"]


# --- Integration: login + current user -----------------------------------

async def test_login_success_and_me(client, db_session):
    await _make_user(db_session, "doc@x.io", "password123", UserRole.RADIOLOGIST)

    resp = await client.post("/api/auth/login", json={"email": "doc@x.io", "password": "password123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "doc@x.io"
    assert body["role"] == UserRole.RADIOLOGIST.value


async def test_login_wrong_password(client, db_session):
    await _make_user(db_session, "doc@x.io", "password123", UserRole.RADIOLOGIST)
    resp = await client.post("/api/auth/login", json={"email": "doc@x.io", "password": "nope"})
    assert resp.status_code == 401


async def test_me_requires_token(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


# --- Integration: role-based authorization --------------------------------

async def _login(client, email, password):
    resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


async def test_admin_can_list_users(client, db_session):
    await _make_user(db_session, "admin@x.io", "password123", UserRole.ADMIN)
    token = await _login(client, "admin@x.io", "password123")
    resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert any(u["email"] == "admin@x.io" for u in resp.json())


async def test_non_admin_forbidden_from_users(client, db_session):
    await _make_user(db_session, "rad@x.io", "password123", UserRole.RADIOLOGIST)
    token = await _login(client, "rad@x.io", "password123")
    resp = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_admin_creates_user(client, db_session):
    await _make_user(db_session, "admin@x.io", "password123", UserRole.ADMIN)
    token = await _login(client, "admin@x.io", "password123")
    resp = await client.post(
        "/api/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "new@x.io",
            "full_name": "New Clinician",
            "password": "password123",
            "role": UserRole.REFERRING_CLINICIAN.value,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "new@x.io"
