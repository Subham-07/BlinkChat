import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_and_join(client: AsyncClient, mode: str = "saved") -> tuple[str, str, dict]:
    resp = await client.post("/api/rooms", json={"mode": mode})
    data = resp.json()
    code = data["room_code"]
    password = data["room_password"]
    join_resp = await client.post("/api/rooms/join", json={"room_code": code, "room_password": password})
    return code, password, join_resp


async def test_correct_credentials_succeed(client: AsyncClient):
    code, password, join_resp = await _create_and_join(client)
    assert join_resp.status_code == 200
    assert "slot" in join_resp.json()
    assert "blinkchat_session" in join_resp.cookies


async def test_wrong_password_rejected(client: AsyncClient):
    resp = await client.post("/api/rooms", json={"mode": "saved"})
    code = resp.json()["room_code"]
    join_resp = await client.post("/api/rooms/join", json={"room_code": code, "room_password": "wrongpassword"})
    assert join_resp.status_code == 401


async def test_invalid_room_code_rejected(client: AsyncClient):
    join_resp = await client.post("/api/rooms/join", json={"room_code": "XXXXXXXX", "room_password": "anypassword"})
    assert join_resp.status_code == 401


async def test_room_full_on_third_participant(client: AsyncClient):
    resp = await client.post("/api/rooms", json={"mode": "saved"})
    code, password = resp.json()["room_code"], resp.json()["room_password"]

    # Two participants join successfully
    j1 = await client.post("/api/rooms/join", json={"room_code": code, "room_password": password})
    assert j1.status_code == 200

    # Use a new client without cookies for the second participant
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.db.base import get_db
    transport = ASGITransport(app=app)
    # Re-use existing override
    async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as c2:
        j2 = await c2.post("/api/rooms/join", json={"room_code": code, "room_password": password})
        assert j2.status_code == 200

    async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as c3:
        j3 = await c3.post("/api/rooms/join", json={"room_code": code, "room_password": password})
        assert j3.status_code == 409


async def test_session_cookie_is_httponly(client: AsyncClient):
    resp = await client.post("/api/rooms", json={"mode": "saved"})
    code, password = resp.json()["room_code"], resp.json()["room_password"]
    join_resp = await client.post("/api/rooms/join", json={"room_code": code, "room_password": password})
    # httpx exposes set-cookie headers
    set_cookie = join_resp.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()


async def test_history_requires_auth(client: AsyncClient):
    resp = await client.get("/api/rooms/history")
    assert resp.status_code == 401


async def test_history_not_available_for_temp_rooms(client: AsyncClient):
    resp = await client.post("/api/rooms", json={"mode": "temporary"})
    code, password = resp.json()["room_code"], resp.json()["room_password"]
    join_resp = await client.post("/api/rooms/join", json={"room_code": code, "room_password": password})
    cookies = dict(join_resp.cookies)
    hist = await client.get("/api/rooms/history", cookies=cookies)
    assert hist.status_code == 400
