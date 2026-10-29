import pytest
from app.services.connection_mgr import ConnectionManager
from app.services.message_service import get_message_history

pytestmark = pytest.mark.asyncio


async def test_temp_messages_not_in_db(db_session):
    """Temporary chat messages must never appear in saved_messages table."""
    from app.models.room import Room
    from sqlalchemy import select
    # Create a temp room directly in DB to get an ID
    from datetime import datetime, timedelta, timezone
    from app.models.room import RoomMode
    import uuid
    from app.core.security import hash_password
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    room = Room(
        id=str(uuid.uuid4()),
        code="TEMPTEST1",
        password_hash=hash_password("test"),
        mode=RoomMode.temporary,
        created_at=now,
        expires_at=now + timedelta(hours=4),
        last_activity_at=now,
        is_active=True,
    )
    db_session.add(room)
    await db_session.commit()

    # Simulate storing temp messages in memory only
    mgr = ConnectionManager()
    mgr.store_temp_message(room.id, {"type": "message", "slot": 1, "content": "secret temp message"})

    # Verify NOT in DB
    msgs, _ = await get_message_history(db_session, room.id)
    assert len(msgs) == 0, "Temp messages must not be persisted to the database"


async def test_temp_messages_evicted_on_room_expire():
    """In-memory messages are removed when a room is evicted."""
    mgr = ConnectionManager()
    room_id = "test-room-evict"
    mgr.store_temp_message(room_id, {"type": "message", "content": "ephemeral"})
    assert len(mgr.get_temp_messages(room_id)) == 1

    await mgr.evict_room(room_id)
    assert len(mgr.get_temp_messages(room_id)) == 0


async def test_message_cap_prevents_unbounded_growth():
    """Temp message store is capped at 500 messages."""
    mgr = ConnectionManager()
    room_id = "test-room-cap"
    for i in range(600):
        mgr.store_temp_message(room_id, {"type": "message", "content": f"msg {i}"})
    assert len(mgr.get_temp_messages(room_id)) == 500
