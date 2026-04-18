from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass, field
from typing import Any

if TYPE_CHECKING:
    from .message import Message
from .base import BaseModel


@dataclass(slots=True)
class Event(BaseModel):
    name: str
    event_type: int
    body: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MessageEvent(Event):
    message: Message | None = None
    is_private: bool = False
