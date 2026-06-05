import pytest
from httpx import AsyncClient


# ── helpers ────────────────────────────────────────────────────────────

async def _ingest(client: AsyncClient, token: str, **kwargs) -> dict:
    payload = {"severity": "INFO", "host": "test-host", "message": "test msg", **kwargs}
    r = await client.post(
        "/api/v1/events/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 201
    return r.json()


# ── ingest ─────────────────────────────────────────────────────────────

async def test_ingest_success(client: AsyncClient, admin_token: str):
    ev = await _ingest(client, admin_token, severity="WARN", host="web-01",
                       message="Rate limit reached", source_ip="10.0.1.1")
    assert ev["severity"] == "WARN"
    assert ev["host"] == "web-01"
    assert ev["id"]


async def test_ingest_all_severities(client: AsyncClient, analyst_token: str):
    for sev in ("INFO", "WARN", "ERROR", "CRIT"):
        ev = await _ingest(client, analyst_token, severity=sev, host=f"host-{sev.lower()}")
        assert ev["severity"] == sev


async def test_ingest_invalid_host_rejected(client: AsyncClient, admin_token: str):
    r = await client.post(
        "/api/v1/events/ingest",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"severity": "INFO", "host": "bad host!", "message": "test"},
    )
    assert r.status_code == 422


async def test_ingest_requires_auth(client: AsyncClient):
    r = await client.post("/api/v1/events/ingest",
                          json={"severity": "INFO", "host": "h", "message": "m"})
    assert r.status_code == 403


# ── list / filters ─────────────────────────────────────────────────────

async def test_list_events_returns_page(client: AsyncClient, admin_token: str):
    await _ingest(client, admin_token, host="list-host")
    r = await client.get("/api/v1/events/",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


async def test_list_filter_by_severity(client: AsyncClient, admin_token: str):
    await _ingest(client, admin_token, severity="CRIT", host="crit-host", message="crit event")
    await _ingest(client, admin_token, severity="INFO", host="info-host", message="info event")

    r = await client.get("/api/v1/events/?severity=CRIT",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["severity"] == "CRIT" for i in items)


async def test_list_filter_by_host(client: AsyncClient, admin_token: str):
    await _ingest(client, admin_token, host="unique-hostname", message="findme")

    r = await client.get("/api/v1/events/?host=unique-hostname",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all("unique-hostname" in i["host"] for i in items)


async def test_list_filter_host_partial_match(client: AsyncClient, admin_token: str):
    await _ingest(client, admin_token, host="web-server-01", message="msg")

    r = await client.get("/api/v1/events/?host=web-server",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


async def test_list_pagination(client: AsyncClient, admin_token: str):
    for i in range(5):
        await _ingest(client, admin_token, host=f"host-pag-{i}")

    r = await client.get("/api/v1/events/?page=1&size=2",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 2
    assert body["page"] == 1


def _utc_iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


async def test_list_date_filter(client: AsyncClient, admin_token: str):
    from datetime import datetime, timedelta, timezone
    await _ingest(client, admin_token, host="date-host")

    past   = _utc_iso(datetime.now(timezone.utc) - timedelta(hours=1))
    future = _utc_iso(datetime.now(timezone.utc) + timedelta(hours=1))

    r = await client.get(f"/api/v1/events/?date_from={past}&date_to={future}",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


async def test_list_date_filter_excludes_future(client: AsyncClient, admin_token: str):
    from datetime import datetime, timedelta, timezone
    await _ingest(client, admin_token, host="old-host")

    far_past = _utc_iso(datetime.now(timezone.utc) - timedelta(hours=2))
    cutoff   = _utc_iso(datetime.now(timezone.utc) - timedelta(hours=1))

    # Ventana en el pasado, antes de ingestar → no debe incluir el evento reciente
    r = await client.get(f"/api/v1/events/?date_from={far_past}&date_to={cutoff}",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(i["host"] != "old-host" for i in items)


# ── stats ──────────────────────────────────────────────────────────────

async def test_stats_returns_expected_keys(client: AsyncClient, admin_token: str):
    r = await client.get("/api/v1/events/stats",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    body = r.json()
    assert "events_per_hour" in body
    assert "events_today" in body
    assert "failed_logins_hour" in body
    assert "critical_alerts_open" in body


async def test_stats_counts_recent_event(client: AsyncClient, admin_token: str):
    await _ingest(client, admin_token, host="stat-host")

    r = await client.get("/api/v1/events/stats",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.json()["events_per_hour"] >= 1
    assert r.json()["events_today"] >= 1


# ── timeline ───────────────────────────────────────────────────────────

async def test_timeline_returns_list(client: AsyncClient, admin_token: str):
    await _ingest(client, admin_token, host="tl-host")

    r = await client.get("/api/v1/events/timeline",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0


async def test_timeline_bucket_shape(client: AsyncClient, admin_token: str):
    await _ingest(client, admin_token, severity="WARN", host="tl-warn")

    r = await client.get("/api/v1/events/timeline?minutes=60",
                         headers={"Authorization": f"Bearer {admin_token}"})
    bucket = r.json()[-1]  # bucket más reciente
    for key in ("ts", "INFO", "WARN", "ERROR", "CRIT"):
        assert key in bucket, f"Falta clave '{key}' en bucket"


async def test_timeline_reflects_ingested_event(client: AsyncClient, admin_token: str):
    await _ingest(client, admin_token, severity="ERROR", host="tl-err")

    r = await client.get("/api/v1/events/timeline?minutes=5",
                         headers={"Authorization": f"Bearer {admin_token}"})
    total_errors = sum(b["ERROR"] for b in r.json())
    assert total_errors >= 1


async def test_timeline_minutes_param_validation(client: AsyncClient, admin_token: str):
    r = await client.get("/api/v1/events/timeline?minutes=0",
                         headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 422
