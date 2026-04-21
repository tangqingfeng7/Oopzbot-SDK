from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from typing_extensions import Self

from pydantic import Field, model_validator

from .attachment import Attachment
from .base import BaseModel, SDKBaseModel
from oopz_sdk.exceptions import OopzApiError

class Message(SDKBaseModel):
    target: str = ""

    area: str = ""
    channel: str = ""

    message_type: str = Field(default="", alias="type")
    client_message_id: str = Field(default="", alias="clientMessageId")
    message_id: str = Field(default="", alias="messageId")
    timestamp: str = ""

    sender_id: str = Field(default="", alias="person")

    content: str = ""
    text: str = ""

    edit_time: int = Field(default=0, alias="editTime")
    top_time: str = Field(default="", alias="topTime")

    cards: Any = None
    mention_list: list[dict[str, Any]] = Field(default_factory=list, alias="mentionList")
    is_mention_all: bool = Field(default=False, alias="isMentionAll")
    sender_is_bot: bool = Field(default=False, alias="senderIsBot")
    sender_bot_type: str = Field(default="", alias="senderBotType")

    style_tags: list[Any] = Field(default_factory=list, alias="styleTags")

    reference_message: Any = Field(default=None, alias="referenceMessage")
    reference_message_id: str = Field(default="", alias="referenceMessageId")

    attachments: list[Attachment] = Field(default_factory=list)


    @model_validator(mode="before")
    @classmethod
    def validate_and_fill_payload(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid message payload: expected dict", payload=data)

        normalized = dict(data)
        attachments_raw = normalized.get("attachments", [])
        if not isinstance(attachments_raw, list):
            normalized["attachments"] = []

        mention_list = normalized.get("mentionList", [])
        if not isinstance(mention_list, list):
            normalized["mentionList"] = []

        style_tags = normalized.get("styleTags", [])
        if not isinstance(style_tags, list):
            normalized["styleTags"] = []
        normalized["referenceMessageId"] = str(normalized.get("referenceMessageId") or "")

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Message":
        return cls.model_validate(data)



class MessageSendResult(SDKBaseModel):
    message_id: str = Field(alias="messageId")
    timestamp: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid message send result payload: expected dict", payload=data)

        normalized = dict(data)
        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "MessageSendResult":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid message send result payload: expected dict", payload=data)
        return cls.model_validate(data)

class PrivateSession(SDKBaseModel):
    last_time: str = Field(default="", alias="lastTime")
    mute: bool = False
    session_id: str = Field(default="", alias="sessionId")
    uid: str = ""

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "PrivateSession":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid private session payload: expected dict", payload=data)
        return cls.model_validate(data)