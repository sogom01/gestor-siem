import pytest
from httpx import AsyncClient


async def _ingest_event(client: AsyncClient, token: str, severity: str, host: str) -> None:
    """Ingesta suficientes eventos para disparar una regla de correlación."""
    for _ in range(22):
        await client.post(
            "/api/v1/events/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={"severity": severity, "host": host,
                  "message": f"login failed from 10.0.0.1", "source_ip": "10.0.0.1"},
        )


async def test_active_alerts_returns_list(client: AsyncClient, admin_token: str):
    r = await client.get("/api/v1/alerts/active",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_active_alerts_requires_auth(client: AsyncClient):
    r = await client.get("/api/v1/alerts/active")
    assert r.status_code == 403


async def test_alert_created_by_correlation_rule(client: AsyncClient, admin_token: str):
    # BR-001 se dispara con >= 20 eventos ERROR en el mismo host en 5 min
    await _ingest_event(client, admin_token, "ERROR", "brute-host")

    r = await client.get("/api/v1/alerts/active",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    alerts = r.json()
    brute_alerts = [a for a in alerts if a["rule_id"] == "BR-001" and a["host"] == "brute-host"]
    assert len(brute_alerts) >= 1, "BR-001 no se disparó tras 22 eventos ERROR en el mismo host"


async def test_alert_update_resolve(client: AsyncClient, admin_token: str):
    # Crear alerta vía regla
    await _ingest_event(client, admin_token, "ERROR", "resolve-host")

    alerts_r = await client.get("/api/v1/alerts/active",
                                headers={"Authorization": f"Bearer {admin_token}"})
    alerts = [a for a in alerts_r.json() if a["host"] == "resolve-host"]
    assert alerts, "No se creó alerta para resolve-host"

    alert_id = alerts[0]["id"]
    r = await client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "resolved"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"
    assert r.json()["resolved_by"] == "admin"


async def test_alert_update_reviewing(client: AsyncClient, analyst_token: str, admin_token: str):
    await _ingest_event(client, admin_token, "ERROR", "review-host")

    alerts_r = await client.get("/api/v1/alerts/active",
                                headers={"Authorization": f"Bearer {admin_token}"})
    alerts = [a for a in alerts_r.json() if a["host"] == "review-host"]
    assert alerts

    alert_id = alerts[0]["id"]
    r = await client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"status": "reviewing"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "reviewing"


async def test_alert_update_viewer_forbidden(client: AsyncClient, viewer_token: str, admin_token: str):
    await _ingest_event(client, admin_token, "ERROR", "viewer-host")

    alerts_r = await client.get("/api/v1/alerts/active",
                                headers={"Authorization": f"Bearer {admin_token}"})
    alerts = [a for a in alerts_r.json() if a["host"] == "viewer-host"]
    assert alerts

    alert_id = alerts[0]["id"]
    r = await client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"status": "resolved"},
    )
    assert r.status_code == 403


async def test_alert_not_found(client: AsyncClient, admin_token: str):
    r = await client.patch(
        "/api/v1/alerts/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "resolved"},
    )
    assert r.status_code == 404
