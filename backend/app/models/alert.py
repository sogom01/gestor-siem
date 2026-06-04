import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Enum as SAEnum, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import enum


class AlertSeverity(str, enum.Enum):
    crit = "crit"
    warn = "warn"
    info = "info"


class AlertStatus(str, enum.Enum):
    open = "open"
    reviewing = "reviewing"
    resolved = "resolved"
    ignored = "ignored"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(SAEnum(AlertSeverity), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str] = mapped_column(String(128), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[AlertStatus] = mapped_column(SAEnum(AlertStatus), default=AlertStatus.open)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
