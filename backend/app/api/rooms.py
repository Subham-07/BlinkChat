"""Room creation and join endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Optional
from app.db.base import get_db
from app.schemas.room import CreateRoomRequest, CreateRoomResponse, JoinRoomRequest, JoinRoomResponse, MessageHistoryResponse
from app.services import room_service, message_service
from app.services.room_service import RoomNotFound, RoomFull, RoomExpired, InvalidPassword
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/rooms", response_model=CreateRoomResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_room(
    request: Request,
    body: CreateRoomRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateRoomResponse:
    result = await room_service.create_room(db, body.mode)
    return CreateRoomResponse(
        room_code=result["room_code"],
        room_password=result["room_password"],
        mode=result["mode"],
        expires_in_seconds=result["expires_in_seconds"],
    )


@router.post("/rooms/join", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def join_room(
    request: Request,
    body: JoinRoomRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await room_service.join_room(db, body.room_code, body.room_password)
    except (RoomNotFound, InvalidPassword):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid room code or password.")
    except RoomExpired:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This room has expired.")
    except RoomFull:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This room is full.")

    # Issue HttpOnly session cookie
    is_secure = settings.is_production
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result["token"],
        max_age=settings.session_max_age,
        httponly=True,
        secure=is_secure,
        samesite="strict",
        path="/",
    )

    return JoinRoomResponse(
        slot=result["slot"],
        mode=result["mode"],
        room_expires_at=result["room_expires_at"],
    ).model_dump()


@router.get("/rooms/history")
async def get_history(
    request: Request,
    page: int = 0,
    db: AsyncSession = Depends(get_db),
    session_token: Optional[str] = Cookie(default=None, alias="blinkchat_session"),
) -> MessageHistoryResponse:
    """Retrieve paginated saved chat history for the authenticated participant."""
    auth = await room_service.get_authenticated_participant(db, session_token or "")
    if auth is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    participant, room = auth
    if room.mode.value != "saved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="History is only available for Saved Chat rooms.")

    msgs, has_more = await message_service.get_message_history(db, room.id, page)
    return MessageHistoryResponse(
        messages=[
            {
                "id": m.id,
                "slot": m.slot,
                "content": m.content,
                "sent_at": m.sent_at.isoformat(),
            }
            for m in msgs
        ],
        has_more=has_more,
    )
