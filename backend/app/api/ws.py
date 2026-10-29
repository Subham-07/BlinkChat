"""WebSocket endpoint for real-time messaging."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.db.base import get_session_local
from app.services import room_service, message_service
from app.services.connection_mgr import manager
from app.core.config import settings
from app.models.room import RoomMode
from pydantic import ValidationError
from app.schemas.message import WsIncoming

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Authenticated WebSocket endpoint.
    1. Validates session cookie before accepting the connection.
    2. Enforces room membership on every message.
    3. Broadcasts to both participants.
    4. Persists messages for Saved Chat rooms.
    5. Stores messages in memory for Temporary Chat rooms (NOT persisted).
    """
    # Validate origin to prevent cross-site WebSocket hijacking
    origin = websocket.headers.get("origin", "")
    if origin and origin not in settings.allowed_origins:
        await websocket.close(code=4003)
        return

    token = websocket.cookies.get(settings.session_cookie_name, "")
    session_local = get_session_local()

    async with session_local() as db:
        auth = await room_service.get_authenticated_participant(db, token)

    if auth is None:
        await websocket.close(code=4001)
        return

    participant, room = auth
    room_id = room.id
    slot = participant.slot

    await websocket.accept()
    await manager.connect(room_id, slot, websocket)

    async with session_local() as db:
        await room_service.mark_connected(db, participant.id, True)

    # Send history for saved rooms (on reconnect)
    if room.mode == RoomMode.saved:
        async with session_local() as db:
            msgs, _ = await message_service.get_message_history(db, room_id, page=0)
        history_payload = json.dumps({
            "type": "history",
            "messages": [
                {"slot": m.slot, "content": m.content, "sent_at": m.sent_at.isoformat()}
                for m in msgs
            ],
        })
        try:
            await websocket.send_text(history_payload)
        except Exception:
            pass
    else:
        # Send in-memory messages for temporary room
        temp_msgs = manager.get_temp_messages(room_id)
        if temp_msgs:
            history_payload = json.dumps({"type": "history", "messages": temp_msgs})
            try:
                await websocket.send_text(history_payload)
            except Exception:
                pass

    # Notify both participants of current participant count
    count = await manager.get_participant_count(room_id)
    await manager.broadcast(room_id, {"type": "system", "text": f"participants:{count}"}, sender_slot=slot)

    try:
        while True:
            raw = await websocket.receive_text()

            # Validate payload
            try:
                incoming = WsIncoming.model_validate_json(raw)
            except (ValidationError, ValueError):
                await websocket.send_text(json.dumps({"type": "error", "text": "Invalid message format."}))
                continue

            if incoming.type != "message":
                await websocket.send_text(json.dumps({"type": "error", "text": "Unknown message type."}))
                continue

            content = incoming.content.strip()
            if not content:
                continue
            if len(content) > settings.max_message_length:
                await websocket.send_text(json.dumps({"type": "error", "text": "Message too long."}))
                continue

            now = datetime.now(timezone.utc).isoformat()
            message_dict = {"type": "message", "slot": slot, "content": content, "sent_at": now}

            if room.mode == RoomMode.saved:
                async with session_local() as db:
                    await message_service.save_message(db, room_id, slot, content)
            else:
                # Temporary: store only in memory
                manager.store_temp_message(room_id, message_dict)

            # Broadcast to both participants
            await manager.broadcast(room_id, message_dict, sender_slot=slot)

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await manager.disconnect(room_id, slot)
        async with session_local() as db:
            await room_service.mark_connected(db, participant.id, False)
        count = await manager.get_participant_count(room_id)
        await manager.broadcast(room_id, {"type": "system", "text": f"participants:{count}"}, sender_slot=slot)
        logger.info("WebSocket disconnected: room=%s slot=%d", room_id, slot)
