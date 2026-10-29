"""
In-memory WebSocket connection manager.

IMPORTANT LIMITATION: This implementation is designed for a single
server process. It does not synchronise state across multiple workers
or processes. In a multi-worker deployment, a shared pub/sub layer
(e.g. Redis) would be required.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from fastapi import WebSocket


@dataclass
class RoomConnections:
    slot1_ws: Optional[WebSocket] = None
    slot2_ws: Optional[WebSocket] = None
    # Last activity timestamp for inactivity tracking (epoch seconds)
    last_message_at: float = field(default_factory=lambda: __import__('time').time())


class ConnectionManager:
    def __init__(self) -> None:
        # room_id -> RoomConnections
        self._rooms: dict[str, RoomConnections] = {}
        # Temporary chat message store: room_id -> list of message dicts
        self._temp_messages: dict[str, list[dict]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room_id: str, slot: int, websocket: WebSocket) -> None:
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = RoomConnections()
            conn = self._rooms[room_id]
            if slot == 1:
                conn.slot1_ws = websocket
            else:
                conn.slot2_ws = websocket

    async def disconnect(self, room_id: str, slot: int) -> None:
        async with self._lock:
            if room_id not in self._rooms:
                return
            conn = self._rooms[room_id]
            if slot == 1:
                conn.slot1_ws = None
            else:
                conn.slot2_ws = None

    async def broadcast(self, room_id: str, message: dict, sender_slot: int) -> None:
        """Send a message to both participants in the room."""
        import time, json
        async with self._lock:
            conn = self._rooms.get(room_id)
            if not conn:
                return
            conn.last_message_at = time.time()
            targets = []
            if conn.slot1_ws:
                targets.append(conn.slot1_ws)
            if conn.slot2_ws:
                targets.append(conn.slot2_ws)

        payload = json.dumps(message)
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                pass  # Connection already dropped; disconnect handled elsewhere

    async def get_participant_count(self, room_id: str) -> int:
        async with self._lock:
            conn = self._rooms.get(room_id)
            if not conn:
                return 0
            return sum(1 for ws in [conn.slot1_ws, conn.slot2_ws] if ws is not None)

    def store_temp_message(self, room_id: str, message: dict) -> None:
        """Store a message in memory for temporary rooms. NOT persisted."""
        if room_id not in self._temp_messages:
            self._temp_messages[room_id] = []
        self._temp_messages[room_id].append(message)
        # Cap at 500 messages per room to prevent memory abuse
        if len(self._temp_messages[room_id]) > 500:
            self._temp_messages[room_id] = self._temp_messages[room_id][-500:]

    def get_temp_messages(self, room_id: str) -> list[dict]:
        return self._temp_messages.get(room_id, [])

    async def evict_room(self, room_id: str) -> None:
        """Remove all in-memory state for a room (called on expiry)."""
        async with self._lock:
            self._rooms.pop(room_id, None)
            self._temp_messages.pop(room_id, None)

    async def get_inactive_temp_rooms(self, inactivity_timeout: float) -> list[str]:
        """Return room IDs with no recent message activity."""
        import time
        cutoff = time.time() - inactivity_timeout
        async with self._lock:
            return [
                rid for rid, conn in self._rooms.items()
                if conn.last_message_at < cutoff
            ]


# Singleton — one manager for the application lifetime
manager = ConnectionManager()
