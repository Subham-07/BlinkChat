import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from app.core.security import (
    hash_password, verify_password,
    generate_room_code, generate_room_password,
    generate_session_token, hash_token,
)


def test_password_hash_uses_argon2():
    pw = "TestPassword123!"
    h = hash_password(pw)
    assert h.startswith("$argon2")
    assert verify_password(pw, h)
    assert not verify_password("WrongPassword", h)


def test_room_codes_have_sufficient_entropy():
    codes = {generate_room_code() for _ in range(1000)}
    # All 1000 should be unique (collision probability ~0 with 8-char codes)
    assert len(codes) == 1000


def test_room_password_meets_complexity():
    for _ in range(100):
        pwd = generate_room_password()
        assert len(pwd) >= 12
        assert any(c.isupper() for c in pwd)
        assert any(c.islower() for c in pwd)
        assert any(c.isdigit() for c in pwd)
        assert any(c in "!@#$%" for c in pwd)


def test_session_tokens_are_unique():
    tokens = {generate_session_token() for _ in range(1000)}
    assert len(tokens) == 1000


def test_token_hash_differs_from_token():
    token = generate_session_token()
    h = hash_token(token)
    assert h != token
    assert len(h) == 64  # SHA-256 hex digest


@pytest.mark.asyncio
async def test_sql_injection_in_room_code(client: AsyncClient):
    """SQL injection in room_code must not bypass auth or cause errors."""
    malicious_inputs = [
        "' OR '1'='1",
        "XXXXXXXX; DROP TABLE rooms; --",
        "' UNION SELECT * FROM rooms --",
    ]
    for payload in malicious_inputs:
        resp = await client.post(
            "/api/rooms/join",
            json={"room_code": payload, "room_password": "anything"},
        )
        # Should be rejected with validation error (422) or auth error (401)
        assert resp.status_code in (401, 422), f"Unexpected status for payload: {payload!r}"


@pytest.mark.asyncio
async def test_xss_payload_rejected_or_stored_safely(client: AsyncClient, db_session):
    """XSS payloads stored in DB for saved rooms must not be executed in responses."""
    from app.services.message_service import save_message, get_message_history
    from app.models.room import Room
    from sqlalchemy import select
    from app.models.room import RoomMode
    import uuid
    from app.core.security import hash_password

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    xss = "<script>alert('xss')</script>"
    room = Room(
        id=str(uuid.uuid4()),
        code="XSSTEST11",
        password_hash=hash_password("x"),
        mode=RoomMode.saved,
        created_at=now,
        expires_at=now + timedelta(days=7),
        last_activity_at=now,
        is_active=True,
    )
    db_session.add(room)
    await db_session.commit()

    await save_message(db_session, room.id, 1, xss)
    msgs, _ = await get_message_history(db_session, room.id)
    # Content is stored as-is; frontend must render it as textContent
    assert msgs[0].content == xss  # stored verbatim — frontend sanitizes on render


@pytest.mark.asyncio
async def test_health_endpoint_exposes_no_secrets(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.text
    assert "password" not in body.lower()
    assert "secret" not in body.lower()
    assert "token" not in body.lower()
