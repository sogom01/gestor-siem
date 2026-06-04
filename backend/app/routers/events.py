from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.event import Severity
from app.models.user import User
from app.schemas.event import EventIn, EventOut, EventsPage
from app.services.events import ingest_event, get_events_page, get_stats
from app.services.auth import any_role, analyst_or_admin
from app.services.ws_manager import manager

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/ingest", response_model=EventOut, status_code=201)
async def ingest(
    payload: EventIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(analyst_or_admin),
):
    event = await ingest_event(db, payload)
    # Broadcast al WebSocket
    await manager.broadcast({
        "type": "event",
        "data": {
            "id": event.id,
            "timestamp": event.timestamp.isoformat(),
            "severity": event.severity.value,
            "host": event.host,
            "source_ip": event.source_ip,
            "message": event.message,
        },
    })
    return event


@router.get("/", response_model=EventsPage)
async def list_events(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    severity: Severity | None = None,
    host: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(any_role),
):
    items, total = await get_events_page(db, page, size, severity, host)
    return EventsPage(items=items, total=total, page=page, size=size)


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db), _: User = Depends(any_role)):
    return await get_stats(db)
