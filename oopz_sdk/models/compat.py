from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .area import Area
from .attachment import Attachment
from .base import BaseModel
from .channel import Channel
from .member import Member
from .message import Message


AreaInfo = Area
ChannelInfo = Channel
ChannelMessage = Message
UploadAttachment = Attachment
VoiceChannelMember = Member


@dataclass(slots=True)
class ChatMessageEvent(BaseModel):
    message_id: str
    area: str
    channel: str
    person: str
    content: str
    timestamp: str = ""
    attachments: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LifecycleEvent(BaseModel):
    state: str
    attempt: int = 0
    code: int | None = None
    reason: str = ""
    error: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "AreaInfo",
    "ChannelInfo",
    "ChannelMessage",
    "ChatMessageEvent",
    "LifecycleEvent",
    "UploadAttachment",
    "VoiceChannelMember",
]
