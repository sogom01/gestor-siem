from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.event import Event, Severity
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.schemas.event import EventIn
import json


# ── Reglas de correlación ──────────────────────────────────────────────
RULES = {
    "BR-001": {
        "name": "Brute Force",
        "condition": lambda counts: counts.get(Severity.ERROR, 0) >= 20,
        "severity": AlertSeverity.crit,
        "title": "BRUTE FORCE DETECTADO",
    },
    "PS-001": {
        "name": "Port Scan",
        "condition": lambda counts: counts.get(Severity.WARN, 0) >= 10,
        "severity": AlertSeverity.crit,
        "title": "PORT SCAN DETECTADO",
    },
}


async def ingest_event(db: AsyncSession, payload: EventIn) -> Event:
    event = Event(
        severity=payload.severity,
        host=payload.host,
        source_ip=payload.source_ip,
        message=payload.message,
        raw=payload.raw,
        timestamp=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()

    # Evaluar reglas de correlación en ventana de 5 minutos
    await _evaluate_rules(db, event)
    await db.commit()
    await db.refresh(event)
    return event


async def _evaluate_rules(db: AsyncSession, trigger: Event) -> None:
    window_start = datetime.utcnow() - timedelta(minutes=5)
    result = await db.execute(
        select(Event.severity, func.count().label("cnt"))
        .where(
            and_(
                Event.host == trigger.host,
                Event.timestamp >= window_start,
            )
        )
        .group_by(Event.severity)
    )
    counts = {row.severity: row.cnt for row in result}

    for rule_id, rule in RULES.items():
        if rule["condition"](counts):
            existing = await db.execute(
                select(Alert).where(
                    and_(
                        Alert.rule_id == rule_id,
                        Alert.host == trigger.host,
                        Alert.status.in_([AlertStatus.open, AlertStatus.reviewing]),
                        Alert.created_at >= window_start,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue  # ya existe alerta activa para este host/regla

            alert = Alert(
                severity=rule["severity"],
                title=rule["title"],
                body=f"Regla {rule_id} activada en host {trigger.host}.",
                host=trigger.host,
                source_ip=trigger.source_ip,
                rule_id=rule_id,
                extra=json.dumps({"counts": {k.value: v for k, v in counts.items()}}),
            )
            db.add(alert)


async def get_events_page(
    db: AsyncSession, page: int = 1, size: int = 100,
    severity: Severity | None = None, host: str | None = None,
) -> tuple[list[Event], int]:
    query = select(Event).order_by(Event.timestamp.desc())
    if severity:
        query = query.where(Event.severity == severity)
    if host:
        query = query.where(Event.host == host)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    return result.scalars().all(), total


async def get_stats(db: AsyncSession) -> dict:
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    events_hour = await db.execute(
        select(func.count()).where(Event.timestamp >= hour_ago)
    )
    events_today = await db.execute(
        select(func.count()).where(Event.timestamp >= today_start)
    )
    failed_logins = await db.execute(
        select(func.count()).where(
            and_(Event.timestamp >= hour_ago, Event.severity == Severity.ERROR)
        )
    )
    critical_alerts = await db.execute(
        select(func.count()).where(
            and_(Alert.severity == AlertSeverity.crit, Alert.status == AlertStatus.open)
        )
    )

    return {
        "events_per_hour": events_hour.scalar_one(),
        "events_today": events_today.scalar_one(),
        "failed_logins_hour": failed_logins.scalar_one(),
        "critical_alerts_open": critical_alerts.scalar_one(),
    }
