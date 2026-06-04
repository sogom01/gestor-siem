from datetime import datetime
from pydantic import BaseModel, field_validator
from app.models.event import Severity
import re


class EventIn(BaseModel):
    severity: Severity
    host: str
    source_ip: str | None = None
    message: str
    raw: str | None = None

    @field_validator("host")
    @classmethod
    def host_safe(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9.\-_]{1,128}$", v):
            raise ValueError("host inválido")
        return v

    @field_validator("message")
    @classmethod
    def message_length(cls, v: str) -> str:
        if len(v) > 2048:
            raise ValueError("mensaje demasiado largo")
        return v

    @field_validator("source_ip")
    @classmethod
    def ip_safe(cls, v: str | None) -> str | None:
        if v and not re.match(r"^[\d.:a-fA-F]{1,45}$", v):
            raise ValueError("IP inválida")
        return v


class EventOut(BaseModel):
    id: str
    timestamp: datetime
    severity: Severity
    host: str
    source_ip: str | None
    message: str

    model_config = {"from_attributes": True}


class EventsPage(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    size: int
