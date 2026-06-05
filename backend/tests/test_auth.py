import pytest
from httpx import AsyncClient


async def test_login_admin_success(client: AsyncClient):
    r = await client.post("/api/v1/auth/token",
                          json={"username": "admin", "password": "Admin1234!"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["role"] == "admin"
    assert body["expires_in"] > 0


async def test_login_wrong_password(client: AsyncClient):
    r = await client.post("/api/v1/auth/token",
                          json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


async def test_login_unknown_user(client: AsyncClient):
    r = await client.post("/api/v1/auth/token",
                          json={"username": "ghost", "password": "whatever"})
    assert r.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, admin_token: str):
    r = await client.get("/api/v1/auth/me",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert r.json()["role"] == "admin"


async def test_me_without_token_rejected(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 403


async def test_analyst_login(client: AsyncClient):
    r = await client.post("/api/v1/auth/token",
                          json={"username": "analyst", "password": "Analyst1234!"})
    assert r.status_code == 200
    assert r.json()["role"] == "analyst"


async def test_viewer_cannot_ingest(client: AsyncClient, viewer_token: str):
    r = await client.post(
        "/api/v1/events/ingest",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"severity": "INFO", "host": "test-host", "message": "test"},
    )
    assert r.status_code == 403
