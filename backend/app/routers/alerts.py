from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.alert import Alert, AlertStatus
from app.models.user import User
from app.schemas.alert import AlertOut, AlertUpdate
from app.services.auth import any_role, analyst_or_admin
from app.services.ws_manager import manager

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/active", response_model=list[AlertOut])
async def active_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(any_role),
):
    result = await db.execute(
        select(Alert)
        .where(Alert.status.in_([AlertStatus.open, AlertStatus.reviewing]))
        .order_by(Alert.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.patch("/{alert_id}", response_model=AlertOut)
async def update_alert(
    alert_id: str,
    payload: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(analyst_or_admin),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    alert.status = payload.status
    if payload.status == AlertStatus.resolved:
        alert.resolved_by = current_user.username
        alert.resolved_at = datetime.utcnow()

    await db.commit()
    await db.refresh(alert)

    await manager.broadcast({"type": "alert_update", "data": {"id": alert_id, "status": payload.status.value}})
    return alert
