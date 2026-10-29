"""Saved message persistence and retrieval."""
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.message import SavedMessage
import logging

logger = logging.getLogger(__name__)

PAGE_SIZE = 50


async def save_message(
    db: AsyncSession, room_id: str, slot: int, content: str
) -> SavedMessage:
    """Persist a message for a Saved Chat room."""
    msg = SavedMessage(
        room_id=room_id,
        slot=slot,
        content=content,
        sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_message_history(
    db: AsyncSession,
    room_id: str,
    page: int = 0,
) -> tuple[list[SavedMessage], bool]:
    """Return paginated message history for a saved room."""
    offset = page * PAGE_SIZE
    result = await db.execute(
        select(SavedMessage)
        .where(SavedMessage.room_id == room_id)
        .order_by(SavedMessage.sent_at.asc())
        .offset(offset)
        .limit(PAGE_SIZE + 1)
    )
    messages = result.scalars().all()
    has_more = len(messages) > PAGE_SIZE
    return list(messages[:PAGE_SIZE]), has_more
