from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

from .base import BaseModel
from oopz_sdk.exceptions import OopzApiError

if TYPE_CHECKING:
    from .message import Message


class Event(BaseModel):
    """
    所有事件的公共基类。

    注意：
    - 这里不用 `name`，而是用 `event_name`
    - 因为很多事件 body 里本身也有 `name` 字段（例如频道名）
    """
    event_name: str
    event_type: int
    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def validate_common_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise OopzApiError(f"invalid {cls.__name__} payload: expected dict", payload=data)

        normalized = dict(data)
        normalized["event_name"] = str(normalized.get("event_name") or "")
        try:
            normalized["event_type"] = int(normalized.get("event_type") or 0)
        except (TypeError, ValueError):
            normalized["event_type"] = 0

        raw = normalized.get("raw", {})
        normalized["raw"] = dict(raw) if isinstance(raw, dict) else {}
        return normalized


class UnknownEvent(Event):
    """
    未建模事件的兜底类型。
    """
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        payload = normalized.get("payload", {})
        normalized["payload"] = dict(payload) if isinstance(payload, dict) else {}
        return normalized


class MessageEvent(Event):
    message: "Message | None" = None
    is_private: bool = False

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        return {
            **data,
            **normalized,
        }


class ServerIdEvent(Event):
    server_id: str = Field(default="", alias="serverId")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        normalized["serverId"] = str(normalized.get("serverId") or "")
        return normalized


class HeartbeatEvent(Event):

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        return normalized


class AuthEvent(Event):
    code: int = 0
    message: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        try:
            normalized["code"] = int(normalized.get("code") or 0)
        except (TypeError, ValueError):
            normalized["code"] = 0
        normalized["message"] = str(normalized.get("message") or "")
        return normalized


class MessageDeleteEvent(Event):
    area: str = ""
    channel: str = ""
    message_id: str = Field(default="", alias="messageId")
    person: str = ""
    isMentionAll: bool = False
    mentionList: list[Any] = Field(default_factory=list, alias="mentionList")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        normalized["area"] = str(normalized.get("area") or "")
        normalized["channel"] = str(normalized.get("channel") or "")
        normalized["messageId"] = str(normalized.get("messageId") or "")
        normalized["isMentionAll"] = bool(normalized.get("isMentionAll") or "")
        normalized["person"] = str(normalized.get("person") or "")
        normalized["mentionList"] = list(normalized.get("mentionList") or [])
        return normalized


class AreaDisableEvent(Event):
    ack_id: str = Field(default="", alias="ackId")
    type: str = ""
    area: str = ""
    disable_to: str = Field(default="", alias="disableTo")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        normalized["ackId"] = str(normalized.get("ackId") or "")
        normalized["type"] = str(normalized.get("type") or "")
        normalized["area"] = str(normalized.get("area") or "")
        normalized["disableTo"] = "" if normalized.get("disableTo") is None else str(normalized.get("disableTo"))
        return normalized


class ChannelUpdateEvent(Event):
    area: str = ""
    channel: str = ""
    secret: bool = False
    member_public: bool = Field(default=False, alias="memberPublic")
    text_gap_second: int = Field(default=0, alias="textGapSecond")
    voice_control_enabled: bool = Field(default=False, alias="voiceControlEnabled")
    text_control_enabled: bool = Field(default=False, alias="textControlEnabled")
    voice_roles: list[Any] = Field(default_factory=list, alias="voiceRoles")
    text_roles: list[Any] = Field(default_factory=list, alias="textRoles")
    accessible_roles: list[Any] = Field(default_factory=list, alias="accessibleRoles")
    accessible: list[Any] = Field(default_factory=list)
    disable_voice: list[Any] = Field(default_factory=list, alias="disableVoice")
    disable_text: list[Any] = Field(default_factory=list, alias="disableText")
    name: str = ""
    channel_type: str = Field(default="", alias="type")
    max_member: int = Field(default=30000, alias="maxMember")
    access_control_enabled: bool = Field(default=False, alias="accessControlEnabled")
    has_password: bool = Field(default=False, alias="hasPassword")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        normalized["area"] = str(normalized.get("area") or "")
        normalized["channel"] = str(normalized.get("channel") or "")
        normalized["name"] = str(normalized.get("name") or "")
        normalized["type"] = str(normalized.get("type") or "")

        for key in (
                "voiceRoles",
                "textRoles",
                "accessibleRoles",
                "accessible",
                "disableVoice",
                "disableText",
        ):
            value = normalized.get(key, [])
            normalized[key] = value if isinstance(value, list) else []

        for key in (
                "secret",
                "memberPublic",
                "voiceControlEnabled",
                "textControlEnabled",
                "accessControlEnabled",
                "hasPassword",
        ):
            normalized[key] = bool(normalized.get(key, False))

        for key, default in (
                ("textGapSecond", 0),
                ("maxMember", 30000),
        ):
            try:
                normalized[key] = int(normalized.get(key) or default)
            except (TypeError, ValueError):
                normalized[key] = default

        return normalized


class VoiceChannelPresenceEvent(Event):
    area: str = ""
    channel: str = ""
    persons: list[str] = Field(default_factory=list)
    active_num: int = Field(default=0, alias="activeNum")
    sound: str = ""
    from_channel: str = Field(default="", alias="fromChannel")
    from_area: str = Field(default="", alias="fromArea")
    sort: int = 0

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        normalized["area"] = str(normalized.get("area") or "")
        normalized["channel"] = str(normalized.get("channel") or "")
        normalized["sound"] = str(normalized.get("sound") or "")
        normalized["fromChannel"] = str(normalized.get("fromChannel") or "")
        normalized["fromArea"] = str(normalized.get("fromArea") or "")

        persons = normalized.get("persons", [])
        normalized["persons"] = [str(x) for x in persons] if isinstance(persons, list) else []

        for key in ("activeNum", "sort"):
            try:
                normalized[key] = int(normalized.get(key) or 0)
            except (TypeError, ValueError):
                normalized[key] = 0

        return normalized


class ChannelCreateEvent(Event):
    area: str = ""
    channel: str = ""
    type: str = ""
    name: str = ""
    member_public: bool = Field(default=False, alias="memberPublic")
    voice_control_enabled: bool = Field(default=False, alias="voiceControlEnabled")
    text_control_enabled: bool = Field(default=False, alias="textControlEnabled")
    voice_roles: list[Any] = Field(default_factory=list, alias="voiceRoles")
    text_roles: list[Any] = Field(default_factory=list, alias="textRoles")
    text_gap_second: int = Field(default=0, alias="textGapSecond")
    channel_type: str = Field(default="", alias="channelType")
    password: str = ""
    voice_quality: str = Field(default="64k", alias="voiceQuality")
    voice_delay: str = Field(default="LOW", alias="voiceDelay")
    max_member: int = Field(default=0, alias="maxMember")
    group_id: str = Field(default="", alias="groupId")
    secret: bool = False
    accessible_roles: list[Any] = Field(default_factory=list, alias="accessibleRoles")
    accessible_members: list[str] = Field(default_factory=list, alias="accessibleMembers")
    has_password: bool = Field(default=False, alias="hasPassword")
    access_control_enabled: bool = Field(default=False, alias="accessControlEnabled")
    is_temp: bool = Field(default=False, alias="isTemp")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)

        for key in (
                "area",
                "channel",
                "type",
                "name",
                "channelType",
                "password",
                "voiceQuality",
                "voiceDelay",
                "groupId",
        ):
            normalized[key] = str(normalized.get(key) or "")

        for key in (
                "memberPublic",
                "voiceControlEnabled",
                "textControlEnabled",
                "secret",
                "hasPassword",
                "accessControlEnabled",
                "isTemp",
        ):
            normalized[key] = bool(normalized.get(key, False))

        for key, default in (
                ("textGapSecond", 0),
                ("maxMember", 0),
        ):
            try:
                normalized[key] = int(normalized.get(key) or default)
            except (TypeError, ValueError):
                normalized[key] = default

        vr = normalized.get("voiceRoles", [])
        tr = normalized.get("textRoles", [])
        ar = normalized.get("accessibleRoles", [])
        am = normalized.get("accessibleMembers", [])

        normalized["voiceRoles"] = vr if isinstance(vr, list) else []
        normalized["textRoles"] = tr if isinstance(tr, list) else []
        normalized["accessibleRoles"] = ar if isinstance(ar, list) else []
        normalized["accessibleMembers"] = [str(x) for x in am] if isinstance(am, list) else []

        return normalized


class UserUpdateEvent(Event):
    person: str = ""
    updates: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        normalized["person"] = str(normalized.get("person") or "")
        updates = normalized.get("updates", {})
        normalized["updates"] = dict(updates) if isinstance(updates, dict) else {}
        return normalized


class UserLoginStateEvent(Event):
    person: str = ""
    type: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        normalized["person"] = str(normalized.get("person") or "")
        normalized["type"] = str(normalized.get("type") or "")
        return normalized


class AreaUpdateEvent(Event):
    area: str = ""
    code: str = ""
    name: str = ""
    avatar: str = ""
    owner: str = ""
    desc: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)
        for key in ("area", "code", "name", "avatar", "owner", "desc"):
            normalized[key] = str(normalized.get(key) or "")
        return normalized


class RoleChangedEvent(Event):
    ack_id: str = Field(default="", alias="ackId")
    area: str = ""
    role_id: int = Field(default=0, alias="roleID")
    type: str = ""
    name: str = ""
    description: str = ""
    privilege_keys: list[Any] = Field(default_factory=list, alias="privilegeKeys")
    is_display: bool = Field(default=False, alias="isDisplay")
    sort: int = 0
    role_type: int = Field(default=0, alias="roleType")
    category_keys: list[Any] = Field(default_factory=list, alias="categoryKeys")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        normalized = Event.validate_common_fields(data)

        for key in ("ackId", "area", "type", "name", "description"):
            normalized[key] = str(normalized.get(key) or "")

        for key, default in (
                ("roleID", 0),
                ("sort", 0),
                ("roleType", 0),
        ):
            try:
                normalized[key] = int(normalized.get(key) or default)
            except (TypeError, ValueError):
                normalized[key] = default

        normalized["isDisplay"] = bool(normalized.get("isDisplay", False))

        pk = normalized.get("privilegeKeys", [])
        ck = normalized.get("categoryKeys", [])
        normalized["privilegeKeys"] = pk if isinstance(pk, list) else []
        normalized["categoryKeys"] = ck if isinstance(ck, list) else []

        return normalized


from .message import Message

MessageEvent.model_rebuild()
