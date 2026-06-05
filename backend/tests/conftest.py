import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.services.auth import hash_password

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _make_override(session):
    async def _override():
        yield session
    return _override


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add_all([
            User(username="admin",   email="admin@test.local",
                 hashed_password=hash_password("Admin1234!"),   role=UserRole.admin,   is_active=True),
            User(username="analyst", email="analyst@test.local",
                 hashed_password=hash_password("Analyst1234!"), role=UserRole.analyst, is_active=True),
            User(username="viewer",  email="viewer@test.local",
                 hashed_password=hash_password("Viewer1234!"),  role=UserRole.viewer,  is_active=True),
        ])
        await session.commit()
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db):
    app.dependency_overrides[get_db] = _make_override(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_token(client) -> str:
    r = await client.post("/api/v1/auth/token",
                          json={"username": "admin", "password": "Admin1234!"})
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def analyst_token(client) -> str:
    r = await client.post("/api/v1/auth/token",
                          json={"username": "analyst", "password": "Analyst1234!"})
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def viewer_token(client) -> str:
    r = await client.post("/api/v1/auth/token",
                          json={"username": "viewer", "password": "Viewer1234!"})
    return r.json()["access_token"]
