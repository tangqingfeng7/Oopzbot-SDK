from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .attachment import Attachment
from .base import BaseModel


@dataclass(slots=True)
class Message(BaseModel):
    target: str = ""

    area: str = ""
    channel: str = ""

    message_type: str = ""
    client_message_id: str = "" # todo
    message_id: str = ""
    timestamp: str = ""

    person: str = ""

    content: str = ""
    text: str = ""

    edit_time: int = 0
    top_time: str = ""

    cards: Any = None
    mention_list: list[dict[str, Any]] = field(default_factory=list)
    is_mention_all: bool = False
    sender_is_bot: bool = False
    sender_bot_type: str = ""

    style_tags: list = field(default_factory=list)

    reference_message: Any = None
    reference_message_id: str = ""

    attachments: list[Attachment] = field(default_factory=list)

    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        if not isinstance(data, dict):
            return cls()

        attachments_raw = data.get("attachments", [])
        if not isinstance(attachments_raw, list):
            attachments_raw = []

        attachments = [
            Attachment.from_dict(item)
            for item in attachments_raw
            if isinstance(item, dict)
        ]

        mention_list = data.get("mentionList", [])
        if not isinstance(mention_list, list):
            mention_list = []

        style_tags = data.get("styleTags", [])
        if not isinstance(style_tags, list):
            style_tags = []

        content = str(data.get("content") or "")
        text = str(data.get("text") or content)

        return cls(
            target=str(data.get("target") or ""),
            area=str(data.get("area") or ""),
            channel=str(data.get("channel") or ""),

            message_type=str(data.get("type") or ""),
            client_message_id=str(data.get("clientMessageId") or ""),
            message_id=str(data.get("messageId") or ""),
            timestamp=str(data.get("timestamp") or ""),

            person=str(data.get("person") or ""),

            content=content,
            text=text,

            edit_time=int(data.get("editTime") or 0),
            top_time=str(data.get("topTime") or ""),

            cards=data.get("cards"),
            mention_list=mention_list,
            is_mention_all=bool(data.get("isMentionAll", False)),
            sender_is_bot=bool(data.get("senderIsBot", False)),
            sender_bot_type=str(data.get("senderBotType") or ""),

            style_tags=style_tags,

            reference_message=data.get("referenceMessage"),
            reference_message_id=str(data.get("referenceMessageId") or ""),

            attachments=attachments,

            payload=dict(data),
        )