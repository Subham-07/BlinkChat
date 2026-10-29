from pydantic import BaseModel, Field
from typing import Literal


class ChatMessage(BaseModel):
    type: Literal["message"] = "message"
    content: str = Field(..., min_length=1, max_length=4000)


class SystemMessage(BaseModel):
    type: Literal["system"]
    text: str


class WsIncoming(BaseModel):
    type: str
    content: str = Field(default="", max_length=4000)
