from datetime import datetime
from pydantic import BaseModel
from app.models.agent import AgentStatus


class AgentOut(BaseModel):
    id: str
    name: str
    host: str
    status: AgentStatus
    last_seen: datetime | None
    version: str | None

    model_config = {"from_attributes": True}
