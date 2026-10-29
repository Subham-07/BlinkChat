"""Room creation, joining, expiry, and cleanup logic."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.room import Room, RoomMode
from app.models.participant import ParticipantSession
from app.core.security import (
    generate_room_code, generate_room_password,
    hash_password, verify_password,
    generate_session_token, hash_token,
)
from app.core.config import settings
from app.services.connection_mgr import manager as conn_manager
import logging

logger = logging.getLogger(__name__)


class RoomError(Exception):
    pass


class RoomNotFound(RoomError):
    pass


class RoomFull(RoomError):
    pass


class RoomExpired(RoomError):
    pass


class InvalidPassword(RoomError):
    pass


async def create_room(db: AsyncSession, mode: str) -> dict:
    """
    Create a new room, returning the room code and password (shown once).
    The plaintext password is NEVER stored after this function returns.
    """
    password = generate_room_password()
    password_hash = hash_password(password)

    # Generate a unique room code
    for _ in range(10):  # retry up to 10 times on collision
        code = generate_room_code()
        existing = await db.execute(select(Room).where(Room.code == code))
        if existing.scalar_one_or_none() is None:
            break
    else:
        raise RoomError("Could not generate a unique room code. Please try again.")

    # Calculate expiry
    if mode == "temporary":
        lifetime = settings.temp_room_max_lifetime_seconds
    else:
        lifetime = settings.saved_room_max_lifetime_seconds

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = now + timedelta(seconds=lifetime)

    room = Room(
        code=code,
        password_hash=password_hash,
        mode=RoomMode(mode),
        created_at=now,
        expires_at=expires_at,
        last_activity_at=now,
        is_active=True,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)

    logger.info("Room created: id=%s mode=%s", room.id, mode)
    # NOTE: password is returned here to be displayed to the creator ONCE.
    # It is not stored anywhere in plaintext after this response.
    return {
        "room_id": room.id,
        "room_code": code,
        "room_password": password,
        "mode": mode,
        "expires_in_seconds": lifetime,
    }


async def join_room(db: AsyncSession, room_code: str, password: str) -> dict:
    """
    Validate credentials, enforce two-person limit, assign slot, and issue session token.
    Slot assignment is done inside a transaction to prevent race conditions.
    """
    result = await db.execute(select(Room).where(Room.code == room_code))
    room = result.scalar_one_or_none()

    # Use generic error to avoid revealing room existence
    if room is None or not room.is_active:
        raise RoomNotFound("Invalid room code or password.")

    if datetime.now(timezone.utc).replace(tzinfo=None) > room.expires_at:
        raise RoomExpired("This room has expired.")

    if not verify_password(password, room.password_hash):
        raise InvalidPassword("Invalid room code or password.")

    # Atomically assign a participant slot
    async with db.begin_nested():
        # Lock existing sessions for this room
        sessions_result = await db.execute(
            select(ParticipantSession)
            .where(ParticipantSession.room_id == room.id)
            .with_for_update()
        )
        sessions = sessions_result.scalars().all()

        occupied_slots = {s.slot for s in sessions}
        available_slots = {1, 2} - occupied_slots

        if not available_slots:
            raise RoomFull("This room is full.")

        slot = min(available_slots)
        token = generate_session_token()
        token_hash = hash_token(token)

        participant = ParticipantSession(
            room_id=room.id,
            slot=slot,
            session_token_hash=token_hash,
            joined_at=datetime.now(timezone.utc).replace(tzinfo=None),
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
            is_connected=False,
        )
        db.add(participant)

    await db.commit()

    logger.info("Participant joined room=%s slot=%d", room.id, slot)
    return {
        "token": token,
        "slot": slot,
        "room_id": room.id,
        "mode": room.mode.value,
        "room_expires_at": room.expires_at.isoformat(),
    }


async def get_authenticated_participant(
    db: AsyncSession, token: str
) -> Optional[tuple[ParticipantSession, Room]]:
    """Validate a session token and return (participant, room) or None."""
    if not token:
        return None
    token_hash = hash_token(token)
    result = await db.execute(
        select(ParticipantSession).where(
            ParticipantSession.session_token_hash == token_hash
        )
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        return None

    room_result = await db.execute(select(Room).where(Room.id == participant.room_id))
    room = room_result.scalar_one_or_none()
    if room is None or not room.is_active or datetime.now(timezone.utc).replace(tzinfo=None) > room.expires_at:
        return None

    return participant, room


async def mark_connected(db: AsyncSession, participant_id: str, connected: bool) -> None:
    await db.execute(
        update(ParticipantSession)
        .where(ParticipantSession.id == participant_id)
        .values(is_connected=connected, last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None))
    )
    await db.commit()


async def expire_room(db: AsyncSession, room_id: str) -> None:
    """Mark a room as inactive and clean up in-memory state."""
    await db.execute(
        update(Room).where(Room.id == room_id).values(is_active=False)
    )
    await db.commit()
    await conn_manager.evict_room(room_id)
    logger.info("Room expired: id=%s", room_id)


async def cleanup_expired_rooms(db: AsyncSession) -> None:
    """Periodic task: expire overdue rooms and clean up in-memory state."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        select(Room).where(Room.is_active == True, Room.expires_at <= now)
    )
    expired = result.scalars().all()
    for room in expired:
        await expire_room(db, room.id)

    # Also check temp rooms for inactivity
    inactive_ids = await conn_manager.get_inactive_temp_rooms(
        settings.temp_room_inactivity_timeout_seconds
    )
    for room_id in inactive_ids:
        result = await db.execute(
            select(Room).where(Room.id == room_id, Room.is_active == True, Room.mode == RoomMode.temporary)
        )
        room = result.scalar_one_or_none()
        if room:
            await expire_room(db, room_id)
