from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import engine, Base
from app.middleware.security import SecurityHeadersMiddleware
from app.routers import auth, events, alerts, agents, ws

# Import all models so Alembic/SQLAlchemy sees them
import app.models  # noqa: F401

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas en dev (en prod usar Alembic migrations)
    if settings.app_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await _seed_dev_data()
    yield
    await engine.dispose()


async def _seed_dev_data():
    """Crea usuario admin y agentes de ejemplo si no existen."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User, UserRole
    from app.models.agent import Agent, AgentStatus
    from app.services.auth import hash_password
    from datetime import datetime

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.username == "admin"))
        if existing.scalar_one_or_none():
            return

        users = [
            User(username="admin", email="admin@siem.local",
                 hashed_password=hash_password("Admin1234!"), role=UserRole.admin),
            User(username="analyst", email="analyst@siem.local",
                 hashed_password=hash_password("Analyst1234!"), role=UserRole.analyst),
            User(username="viewer", email="viewer@siem.local",
                 hashed_password=hash_password("Viewer1234!"), role=UserRole.viewer),
        ]

        agents = [
            Agent(name="web-server-01", host="10.0.1.10", status=AgentStatus.online, last_seen=datetime.utcnow(), version="1.4.2"),
            Agent(name="db-primary",    host="10.0.1.20", status=AgentStatus.online, last_seen=datetime.utcnow(), version="1.4.2"),
            Agent(name="auth-service",  host="10.0.1.30", status=AgentStatus.error,  last_seen=datetime.utcnow(), version="1.4.1"),
            Agent(name="proxy-edge",    host="10.0.1.40", status=AgentStatus.warn,   last_seen=datetime.utcnow(), version="1.4.2"),
            Agent(name="worker-01",     host="10.0.2.10", status=AgentStatus.online, last_seen=datetime.utcnow(), version="1.4.2"),
            Agent(name="worker-02",     host="10.0.2.11", status=AgentStatus.online, last_seen=datetime.utcnow(), version="1.4.2"),
            Agent(name="monitoring",    host="10.0.1.50", status=AgentStatus.online, last_seen=datetime.utcnow(), version="1.4.2"),
            Agent(name="api-gateway-02",host="10.0.1.60", status=AgentStatus.offline,last_seen=None,              version="1.3.9"),
        ]

        db.add_all(users + agents)
        await db.commit()


app = FastAPI(
    title="SIEM-CORE API",
    version="1.4.2",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS debe ir primero (último en add_middleware = primero en ejecutarse)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Security headers va después (se ejecuta antes que CORS en la cadena real)
app.add_middleware(SecurityHeadersMiddleware)

# Routers
app.include_router(auth.router,   prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.4.2"}
