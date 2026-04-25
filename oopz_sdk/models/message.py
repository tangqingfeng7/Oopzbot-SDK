from __future__ import annotations

import logging
from functools import cached_property
from typing import Any, Mapping

from pydantic import Field, model_validator

from .attachment import Attachment
from .base import BaseModel
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.utils.payload import coerce_bool
from .segment import parse_message_segments, Text

logger = logging.getLogger(__name__)


class MediaInfo(BaseModel):
    file_key: str = Field(default="", alias="fileKey")
    file_size: int = Field(default=0, alias="fileSize")
    hash: str = ""
    url: str = ""
    width: int = 0
    height: int = 0

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid media info payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["fileKey"] = str(normalized.get("fileKey") or "")
        normalized["hash"] = str(normalized.get("hash") or "")
        normalized["url"] = str(normalized.get("url") or "")

        for key in ("fileSize", "width", "height"):
            try:
                normalized[key] = int(normalized.get(key) or 0)
            except (TypeError, ValueError):
                normalized[key] = 0

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "MediaInfo":
        return cls.model_validate(data)

logger = logging.getLogger("oopz_sdk.models.message")

class Message(BaseModel):
    target: str = ""

    area: str = ""
    area_page: str = Field(default="", alias="areaPage")
    area_count: int = Field(default=0, alias="areaCount")

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

    duration: int = 0
    display_name: str = Field(default="", alias="displayName")

    preview_image: MediaInfo | None = Field(default=None, alias="previewImage")
    raw_video: MediaInfo | None = Field(default=None, alias="rawVideo")

    cards: Any = None
    mention_list: list[MentionInfo] = Field(default_factory=list, alias="mentionList")
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

        # 基础字符串字段
        for key in (
                "target",
                "area",
                "areaPage",
                "channel",
                "type",
                "clientMessageId",
                "messageId",
                "timestamp",
                "person",
                "content",
                "text",
                "topTime",
                "displayName",
                "referenceMessageId",
                "senderBotType",
        ):
            normalized[key] = str(normalized.get(key) or "")

        # 基础整数
        for key in ("editTime", "areaCount", "duration"):
            try:
                normalized[key] = int(normalized.get(key) or 0)
            except (TypeError, ValueError):
                normalized[key] = 0

        normalized["isMentionAll"] = coerce_bool(normalized.get("isMentionAll"), default=False)
        normalized["senderIsBot"] = coerce_bool(normalized.get("senderIsBot"), default=False)

        # attachments
        attachments_raw = normalized.get("attachments", [])
        if not isinstance(attachments_raw, list):
            normalized["attachments"] = []
        else:
            parsed_attachments: list[Attachment] = []
            for item in attachments_raw:
                if not isinstance(item, Mapping):
                    continue
                try:
                    parsed_attachments.append(Attachment.parse(item))
                except OopzApiError as exc:
                    logger.warning(
                        "attachmentType=%r: %s unknown, skipped",
                        item.get("attachmentType"),
                        exc,
                    )
                    continue
            normalized["attachments"] = parsed_attachments

        # mentionList
        mention_list = normalized.get("mentionList", [])
        if not isinstance(mention_list, list):
            normalized["mentionList"] = []
        else:
            normalized["mentionList"] = mention_list

        # styleTags
        style_tags = normalized.get("styleTags", [])
        if not isinstance(style_tags, list):
            normalized["styleTags"] = []

        # video fields
        preview_image = normalized.get("previewImage")
        if preview_image is not None and not isinstance(preview_image, Mapping):
            normalized["previewImage"] = None

        raw_video = normalized.get("rawVideo")
        if raw_video is not None and not isinstance(raw_video, Mapping):
            normalized["rawVideo"] = None

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Message":
        return cls.model_validate(data)

    @cached_property
    def segments(self):
        source_text = self.text or self.content or ""
        return parse_message_segments(
            source_text,
            attachments=self.attachments,
            mention_list=self.mention_list,
        )

    @cached_property
    def plain_text(self) -> str:
        parts: list[str] = []
        for seg in self.segments:
            if isinstance(seg, Text):
                parts.append(seg.plain_text)
        return "".join(parts)


class MentionInfo(BaseModel):
    person: str = ""
    is_bot: bool = Field(default=False, alias="isBot")
    bot_type: str = Field(default="", alias="botType")
    offset: int = -1

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid mention info payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["person"] = str(normalized.get("person") or "")
        normalized["isBot"] = coerce_bool(normalized.get("isBot"), default=False)
        normalized["botType"] = str(normalized.get("botType") or "")

        try:
            normalized["offset"] = int(normalized.get("offset") or 0)
        except (TypeError, ValueError):
            normalized["offset"] = -1

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "MentionInfo":
        return cls.model_validate(data)

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=False)


class MessageSendResult(BaseModel):
    message_id: str = Field(alias="messageId")
    timestamp: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid message send result payload: expected dict", payload=data)

        normalized = dict(data)
        if "messageId" in normalized:
            normalized["messageId"] = str(normalized["messageId"])
        if "timestamp" in normalized:
            normalized["timestamp"] = str(normalized["timestamp"])
        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "MessageSendResult":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid message send result payload: expected dict", payload=data)
        return cls.model_validate(data)


class PrivateSession(BaseModel):
    last_time: str = Field(default="", alias="lastTime")
    mute: bool = False
    session_id: str = Field(default="", alias="sessionId")
    uid: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid private session payload: expected dict", payload=data)

        normalized = dict(data)

        # sessionId / lastTime / uid 在协议里偶尔会以整数下发（例如 uid 为数值，
        # sessionId 为时间戳数字），不归一化会导致 Pydantic 的 str 字段直接 ValidationError。
        for key in ("sessionId", "lastTime", "uid"):
            value = normalized.get(key)
            if value is None:
                normalized[key] = ""
            elif isinstance(value, bool):
                # bool 也是 int 的子类，避免 True/False 被写成 "True"
                normalized[key] = "true" if value else "false"
            elif isinstance(value, float):
                normalized[key] = str(int(value)) if value.is_integer() else str(value)
            else:
                normalized[key] = str(value)

        normalized["mute"] = coerce_bool(normalized.get("mute"), default=False)
        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "PrivateSession":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid private session payload: expected dict", payload=data)
        return cls.model_validate(data)
