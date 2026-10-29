"""
Test configuration and shared fixtures.

Key design decisions:
- The database engine is created lazily inside the app's lifespan, not at import time.
  This prevents event-loop conflicts on Windows (ProactorEventLoop).
- Tests call app.db.base.init_engine() with an in-memory SQLite URL before the client
  starts, so the lifespan's init_engine() call is a no-op (we override it).
- We patch app.main.init_engine, app.main.init_db, and app.main._cleanup_loop so the
  lifespan does not touch the real database or start background tasks.
- Rate limiting is disabled for all test clients.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, AsyncMock
import asyncio

import app.db.base as db_base_module
from app.db.base import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _make_test_engine():
    return create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = _make_test_engine()
    async with engine.begin() as conn:
        import app.models.room        # noqa: F401
        import app.models.participant  # noqa: F401
        import app.models.message     # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    TestSessionLocal = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine):
    TestSessionLocal = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    # Point the module-level lazy engine to our test engine so ws.py's
    # get_session_local() calls use the in-memory database.
    db_base_module._engine = db_engine
    db_base_module._AsyncSessionLocal = TestSessionLocal

    # Disable rate limiting
    from app.api.rooms import limiter as rooms_limiter
    app.dependency_overrides[get_db] = override_get_db
    app.state.limiter.enabled = False
    rooms_limiter.enabled = False

    # Replace lifespan calls: init_engine is a no-op (engine already set above),
    # init_db is a no-op (tables already created above), cleanup loop sleeps forever.
    noop = AsyncMock(return_value=None)
    noop_init_engine = lambda url: None  # already initialised

    async def noop_cleanup_loop():
        await asyncio.sleep(9999)

    with patch("app.main.init_engine", noop_init_engine), \
         patch("app.main.init_db", noop), \
         patch("app.main._cleanup_loop", noop_cleanup_loop):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    # Restore
    app.dependency_overrides.clear()
    app.state.limiter.enabled = True
    rooms_limiter.enabled = True
    db_base_module._engine = None
    db_base_module._AsyncSessionLocal = None
