from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import BaseModel


@dataclass(slots=True)
class Event(BaseModel):
    name: str
    event_type: int
    body: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MessageEvent(Event):
    message: dict[str, Any] = field(default_factory=dict)
