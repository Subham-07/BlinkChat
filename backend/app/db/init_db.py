"""Database initialization — creates all tables."""
from app.db.base import Base, get_engine
# Import models so they register with Base metadata
import app.models.room      # noqa: F401
import app.models.participant  # noqa: F401
import app.models.message   # noqa: F401


async def init_db() -> None:
    """Create all database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
