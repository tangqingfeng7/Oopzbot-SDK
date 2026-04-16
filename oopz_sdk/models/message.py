from __future__ import annotations

from dataclasses import dataclass, field

from .attachment import Attachment
from .base import BaseModel


@dataclass(slots=True)
class Message(BaseModel):
    area: str = ""
    channel: str = ""
    target: str = ""
    text: str = ""
    client_message_id: str = ""
    timestamp: str = ""
    mention_list: list[str] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
