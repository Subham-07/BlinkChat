from pydantic import BaseModel, Field, field_validator
import re


class CreateRoomRequest(BaseModel):
    mode: str = Field(..., pattern="^(temporary|saved)$")


class CreateRoomResponse(BaseModel):
    room_code: str
    room_password: str
    mode: str
    expires_in_seconds: int


class JoinRoomRequest(BaseModel):
    room_code: str = Field(..., min_length=1, max_length=20)
    room_password: str = Field(..., min_length=1, max_length=128)

    @field_validator("room_code")
    @classmethod
    def sanitize_room_code(cls, v: str) -> str:
        # Only allow alphanumeric characters
        if not re.match(r"^[A-Z0-9]{4,12}$", v.upper()):
            raise ValueError("Invalid room code format")
        return v.upper()


class JoinRoomResponse(BaseModel):
    slot: int
    mode: str
    room_expires_at: str  # ISO format


class MessageHistoryResponse(BaseModel):
    messages: list[dict]
    has_more: bool
