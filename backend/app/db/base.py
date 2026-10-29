"""Database engine and session factory — lazy initialization."""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from typing import Optional


class Base(DeclarativeBase):
    pass


# Engine and session factory are initialized lazily via init_engine().
# This prevents the engine from being created at import time, which can
# cause event-loop conflicts on Windows with asyncio.ProactorEventLoop.
_engine = None
_AsyncSessionLocal = None


def init_engine(database_url: str) -> None:
    """Create the async engine and session factory. Called once at app startup."""
    global _engine, _AsyncSessionLocal
    _engine = create_async_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=False,
    )
    _AsyncSessionLocal = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def get_engine():
    if _engine is None:
        raise RuntimeError("Database engine not initialised. Call init_engine() first.")
    return _engine


def get_session_local():
    if _AsyncSessionLocal is None:
        raise RuntimeError("Session factory not initialised. Call init_engine() first.")
    return _AsyncSessionLocal


def AsyncSessionLocal():
    """Return a new AsyncSession from the initialised session factory."""
    return get_session_local()()


async def get_db() -> AsyncSession:
    """FastAPI dependency that provides a database session."""
    session_local = get_session_local()
    async with session_local() as session:
        yield session
