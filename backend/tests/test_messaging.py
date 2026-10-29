import pytest
from starlette.testclient import TestClient
from app.main import app
from app.services import room_service
from app.db.base import get_db, AsyncSessionLocal
import json


def test_ws_unauthenticated_rejected():
    with TestClient(app) as tc:
        with pytest.raises(Exception):
            with tc.websocket_connect("/ws"):
                pass


@pytest.mark.asyncio
async def test_ws_authenticated_chat():
    # Create room & join via API
    with TestClient(app) as tc:
        # 1. Create room
        r = tc.post("/api/rooms", json={"mode": "saved"})
        assert r.status_code == 201
        data = r.json()
        code = data["room_code"]
        pwd = data["room_password"]

        # 2. Join as Participant 1
        j1 = tc.post("/api/rooms/join", json={"room_code": code, "room_password": pwd})
        assert j1.status_code == 200

        # Connect WebSocket as Participant 1
        with tc.websocket_connect("/ws") as ws1:
            # First message received is history or participant count
            init_msg = json.loads(ws1.receive_text())
            assert init_msg["type"] in ("history", "system")

            # Send a chat message
            ws1.send_text(json.dumps({"type": "message", "content": "Hello World"}))

            # Receive the echoed/broadcast message
            echo_msg = json.loads(ws1.receive_text())
            # Might be system participant count or the message
            if echo_msg["type"] == "system":
                echo_msg = json.loads(ws1.receive_text())

            assert echo_msg["type"] == "message"
            assert echo_msg["content"] == "Hello World"
            assert echo_msg["slot"] == 1
