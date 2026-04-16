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

        mention_list = data.get("mentionList")
        if mention_list is None:
            mention_list = data.get("mention_list", [])
        if not isinstance(mention_list, list):
            mention_list = []

        style_tags = data.get("styleTags")
        if style_tags is None:
            style_tags = data.get("style_tags", [])
        if not isinstance(style_tags, list):
            style_tags = []

        content = str(data.get("content") or "")
        text = str(data.get("text") or content)
        message_id = str(
            data.get("messageId")
            or data.get("message_id")
            or data.get("id")
            or ""
        )
        client_message_id = str(
            data.get("clientMessageId")
            or data.get("client_message_id")
            or ""
        )
        reference_message_id = str(
            data.get("referenceMessageId")
            or data.get("reference_message_id")
            or ""
        )
        person = str(data.get("person") or data.get("uid") or "")

        return cls(
            target=str(data.get("target") or ""),
            area=str(data.get("area") or ""),
            channel=str(data.get("channel") or ""),

            message_type=str(data.get("type") or data.get("message_type") or ""),
            client_message_id=client_message_id,
            message_id=message_id,
            timestamp=str(data.get("timestamp") or ""),

            person=person,

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
            reference_message_id=reference_message_id,

            attachments=attachments,

            payload=dict(data),
        )
