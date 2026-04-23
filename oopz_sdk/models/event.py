from __future__ import annotations

from typing import Any

from pydantic import Field


from .message import Message
from .base import BaseModel


class Event(BaseModel):
    name: str
    event_type: int
    body: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class MessageEvent(Event):
    message:  "Message | None" = None
    is_private: bool = False

