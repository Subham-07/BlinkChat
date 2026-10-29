import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_temporary_room(client: AsyncClient):
    resp = await client.post("/api/rooms", json={"mode": "temporary"})
    assert resp.status_code == 201
    data = resp.json()
    assert "room_code" in data
    assert "room_password" in data
    assert data["mode"] == "temporary"
    assert data["expires_in_seconds"] > 0


async def test_create_saved_room(client: AsyncClient):
    resp = await client.post("/api/rooms", json={"mode": "saved"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["mode"] == "saved"


async def test_room_codes_are_unique(client: AsyncClient):
    codes = set()
    for _ in range(10):
        resp = await client.post("/api/rooms", json={"mode": "temporary"})
        codes.add(resp.json()["room_code"])
    assert len(codes) == 10  # All unique


async def test_password_not_in_db(client: AsyncClient, db_session):
    from app.models.room import Room
    from sqlalchemy import select
    resp = await client.post("/api/rooms", json={"mode": "saved"})
    code = resp.json()["room_code"]
    plaintext_password = resp.json()["room_password"]

    result = await db_session.execute(select(Room).where(Room.code == code))
    room = result.scalar_one()
    # The stored hash must NOT equal the plaintext password
    assert room.password_hash != plaintext_password
    # The hash must start with argon2 identifier
    assert room.password_hash.startswith("$argon2")


async def test_invalid_mode_rejected(client: AsyncClient):
    resp = await client.post("/api/rooms", json={"mode": "invalid"})
    assert resp.status_code == 422
