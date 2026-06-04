from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentOut
from app.services.auth import any_role

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status", response_model=list[AgentOut])
async def agent_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(any_role),
):
    result = await db.execute(select(Agent).order_by(Agent.name))
    return result.scalars().all()
