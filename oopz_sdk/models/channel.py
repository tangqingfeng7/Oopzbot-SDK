from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import BaseModel


@dataclass(slots=True)
class Channel(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    area: str = ""
    group: str = ""
    secret: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChannelGroup(BaseModel):
    id: str = ""
    name: str = ""
    channels: list[Channel] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
