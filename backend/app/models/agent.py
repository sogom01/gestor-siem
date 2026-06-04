import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import enum


class AgentStatus(str, enum.Enum):
    online = "online"
    warn = "warn"
    error = "error"
    offline = "offline"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    host: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[AgentStatus] = mapped_column(SAEnum(AgentStatus), default=AgentStatus.offline)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[str | None] = mapped_column(String(32), nullable=True)
