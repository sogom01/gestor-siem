import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Enum as SAEnum, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import enum


class Severity(str, enum.Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRIT = "CRIT"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    severity: Mapped[Severity] = mapped_column(SAEnum(Severity), nullable=False, index=True)
    host: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_events_timestamp_severity", "timestamp", "severity"),
    )
