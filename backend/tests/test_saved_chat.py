import pytest
from httpx import AsyncClient
from app.services.message_service import save_message, get_message_history

pytestmark = pytest.mark.asyncio


async def test_messages_persist_in_saved_room(client: AsyncClient, db_session):
    resp = await client.post("/api/rooms", json={"mode": "saved"})
    data = resp.json()
    code, password = data["room_code"], data["room_password"]

    # Get room id from DB
    from app.models.room import Room
    from sqlalchemy import select
    result = await db_session.execute(select(Room).where(Room.code == code))
    room = result.scalar_one()

    # Directly save messages via service
    await save_message(db_session, room.id, 1, "Hello from slot 1")
    await save_message(db_session, room.id, 2, "Hello from slot 2")

    msgs, has_more = await get_message_history(db_session, room.id)
    assert len(msgs) == 2
    assert msgs[0].content == "Hello from slot 1"
    assert not has_more


async def test_history_pagination(client: AsyncClient, db_session):
    from app.models.room import Room
    from sqlalchemy import select
    resp = await client.post("/api/rooms", json={"mode": "saved"})
    code = resp.json()["room_code"]
    result = await db_session.execute(select(Room).where(Room.code == code))
    room = result.scalar_one()

    # Insert 55 messages
    for i in range(55):
        await save_message(db_session, room.id, 1, f"msg {i}")

    msgs, has_more = await get_message_history(db_session, room.id, page=0)
    assert len(msgs) == 50
    assert has_more

    msgs2, has_more2 = await get_message_history(db_session, room.id, page=1)
    assert len(msgs2) == 5
    assert not has_more2
