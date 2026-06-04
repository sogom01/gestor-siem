from datetime import datetime
from pydantic import BaseModel
from app.models.alert import AlertSeverity, AlertStatus


class AlertOut(BaseModel):
    id: str
    created_at: datetime
    severity: AlertSeverity
    title: str
    body: str
    host: str
    source_ip: str | None
    rule_id: str | None
    status: AlertStatus
    resolved_by: str | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class AlertUpdate(BaseModel):
    status: AlertStatus
    resolved_by: str | None = None
