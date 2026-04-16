from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .attachment import Attachment
from .base import BaseModel


@dataclass(slots=True)
class Message(BaseModel):
    message_id: str = ""
    area: str = ""
    channel: str = ""
    person: str = ""
    target: str = ""
    text: str = ""
    client_message_id: str = ""
    reference_message_id: str = ""
    timestamp: str = ""
    mention_list: list[dict[str, Any]] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def content(self) -> str:
        return self.text
