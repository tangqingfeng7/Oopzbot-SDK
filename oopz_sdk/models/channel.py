from __future__ import annotations

from dataclasses import dataclass, field

from typing import Any, Mapping

from pydantic import Field, model_validator
from .base import BaseModel
from oopz_sdk.exceptions import OopzApiError
from enum import Enum

class ChannelType(Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"



class ChannelSetting(BaseModel):
    channel: str

    area_id: str = Field(default="", alias="areaId")
    group_id: str = Field(default="", alias="groupId")

    name: str = ""
    channel_type: str = Field(default="", alias="type")

    text_gap_second: int = Field(default=0, alias="textGapSecond")
    voice_quality: str = Field(default="64k", alias="voiceQuality")
    voice_delay: str = Field(default="LOW", alias="voiceDelay")
    max_member: int = Field(default=30000, alias="maxMember")

    voice_control_enabled: bool = Field(default=False, alias="voiceControlEnabled")
    text_control_enabled: bool = Field(default=False, alias="textControlEnabled")

    text_roles: list[Any] = Field(default_factory=list, alias="textRoles")
    voice_roles: list[Any] = Field(default_factory=list, alias="voiceRoles")

    access_control_enabled: bool = Field(default=False, alias="accessControlEnabled")
    accessible_roles: list[int] = Field(default_factory=list, alias="accessibleRoles")
    accessible_members: list[str] = Field(default_factory=list, alias="accessibleMembers")

    member_public: bool = Field(default=False, alias="memberPublic")
    secret: bool = False
    has_password: bool = Field(default=False, alias="hasPassword")
    password: str = ""


    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid channel setting payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["channel"] = str(normalized.get("channel") or "")
        normalized["areaId"] = str(normalized.get("areaId") or "")
        normalized["groupId"] = str(normalized.get("groupId") or "")
        normalized["name"] = str(normalized.get("name") or "")
        normalized["type"] = str(normalized.get("type") or "")
        normalized["voiceQuality"] = str(normalized.get("voiceQuality") or "64k")
        normalized["voiceDelay"] = str(normalized.get("voiceDelay") or "LOW")
        normalized["password"] = str(normalized.get("password") or "")

        try:
            normalized["textGapSecond"] = int(normalized.get("textGapSecond") or 0)
        except (TypeError, ValueError):
            normalized["textGapSecond"] = 0

        try:
            normalized["maxMember"] = int(normalized.get("maxMember") or 30000)
        except (TypeError, ValueError):
            normalized["maxMember"] = 30000

        normalized["voiceControlEnabled"] = bool(normalized.get("voiceControlEnabled", False))
        normalized["textControlEnabled"] = bool(normalized.get("textControlEnabled", False))
        normalized["accessControlEnabled"] = bool(normalized.get("accessControlEnabled", False))
        normalized["memberPublic"] = bool(normalized.get("memberPublic", False))
        normalized["secret"] = bool(normalized.get("secret", False))
        normalized["hasPassword"] = bool(normalized.get("hasPassword", False))

        text_roles = normalized.get("textRoles", [])
        normalized["textRoles"] = text_roles if isinstance(text_roles, list) else []

        voice_roles = normalized.get("voiceRoles", [])
        normalized["voiceRoles"] = voice_roles if isinstance(voice_roles, list) else []

        accessible_roles = normalized.get("accessibleRoles", [])
        normalized["accessibleRoles"] = accessible_roles if isinstance(accessible_roles, list) else []

        accessible_members = normalized.get("accessibleMembers", [])
        if isinstance(accessible_members, list):
            normalized["accessibleMembers"] = [str(x) for x in accessible_members]
        else:
            normalized["accessibleMembers"] = []

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ChannelSetting":
        return cls.model_validate(data)



class ChannelEdit(BaseModel):
    channel: str
    area: str = ""
    name: str = ""

    text_gap_second: int = Field(default=0, alias="textGapSecond")
    voice_quality: str = Field(default="64k", alias="voiceQuality")
    voice_delay: str = Field(default="LOW", alias="voiceDelay")
    max_member: int = Field(default=30000, alias="maxMember")

    voice_control_enabled: bool = Field(default=False, alias="voiceControlEnabled")
    text_control_enabled: bool = Field(default=False, alias="textControlEnabled")

    text_roles: list[int] = Field(default_factory=list, alias="textRoles")
    voice_roles: list[int] = Field(default_factory=list, alias="voiceRoles")

    access_control_enabled: bool = Field(default=False, alias="accessControlEnabled")
    accessible: list[int] = Field(default_factory=list, alias="accessible")
    accessible_members: list[str] = Field(default_factory=list, alias="accessibleMembers")

    secret: bool = False
    has_password: bool = Field(default=False, alias="hasPassword")
    password: str = ""

    @classmethod
    def from_setting(
        cls,
        setting: "ChannelSetting",
        *,
        area: str | None = None,
        channel: str | None = None,
    ) -> "ChannelEdit":
        return cls(
            channel=channel or setting.channel,
            area=area or setting.area_id,
            name=setting.name,
            text_gap_second=setting.text_gap_second,
            voice_quality=setting.voice_quality,
            voice_delay=setting.voice_delay,
            max_member=setting.max_member,
            voice_control_enabled=setting.voice_control_enabled,
            text_control_enabled=setting.text_control_enabled,
            text_roles=[int(x) for x in setting.text_roles],
            voice_roles=[int(x) for x in setting.voice_roles],
            access_control_enabled=setting.access_control_enabled,
            accessible=[int(x) for x in setting.accessible_roles],
            accessible_members=[str(x) for x in setting.accessible_members],
            secret=setting.secret,
            has_password=setting.has_password,
            password=setting.password,
        )

    def to_request_body(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)



class ChannelSign(BaseModel):
    agora_sign: str = Field(default="", alias="agoraSign")
    agora_sign_pid: str = Field(default="", alias="agoraSignPid")
    app_id: int = Field(default=0, alias="appId")

    disable_text_to: Any = Field(default=None, alias="disableTextTo")
    disable_voice_to: Any = Field(default=None, alias="disableVoiceTo")

    expire_seconds: int = Field(default=86400, alias="expireSeconds")
    now: int = 0
    role_sort: int = Field(default=0, alias="roleSort")

    room_id: str = Field(default="", alias="roomId")
    supplier: str = ""
    supplier_sign: str = Field(default="", alias="supplierSign")
    user_sign: str = Field(default="", alias="userSign")

    voice_delay: str = Field(default="LOW", alias="voiceDelay")
    voice_quality: str = Field(default="64k", alias="voiceQuality")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid channel voice sign payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["agoraSign"] = str(normalized.get("agoraSign") or "")
        normalized["agoraSignPid"] = str(normalized.get("agoraSignPid") or "")
        normalized["roomId"] = str(normalized.get("roomId") or "")
        normalized["supplier"] = str(normalized.get("supplier") or "")
        normalized["supplierSign"] = str(normalized.get("supplierSign") or "")
        normalized["userSign"] = str(normalized.get("userSign") or "")
        normalized["voiceDelay"] = str(normalized.get("voiceDelay") or "LOW")
        normalized["voiceQuality"] = str(normalized.get("voiceQuality") or "64k")

        try:
            normalized["appId"] = int(normalized.get("appId") or 0)
        except (TypeError, ValueError):
            normalized["appId"] = 0

        try:
            normalized["expireSeconds"] = int(normalized.get("expireSeconds") or 86400)
        except (TypeError, ValueError):
            normalized["expireSeconds"] = 86400

        try:
            normalized["now"] = int(normalized.get("now") or 0)
        except (TypeError, ValueError):
            normalized["now"] = 0

        try:
            normalized["roleSort"] = int(normalized.get("roleSort") or 0)
        except (TypeError, ValueError):
            normalized["roleSort"] = 0

        normalized["disableTextTo"] = normalized.get("disableTextTo")
        normalized["disableVoiceTo"] = normalized.get("disableVoiceTo")

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ChannelSign":
        return cls.model_validate(data)

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=False)


class CreateChannelResult(BaseModel):
    area: str = ""
    group_id: str = Field(default="", alias="group")
    max_member: int = Field(default=100, alias="maxMember")
    name: str = ""
    secret: bool = False
    channel_type: ChannelType = Field(default=ChannelType.TEXT, alias="type")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid create channel payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["area"] = str(normalized.get("area") or "")
        normalized["group"] = str(normalized.get("group") or "")
        normalized["name"] = str(normalized.get("name") or "").strip()

        try:
            normalized["maxMember"] = int(normalized.get("maxMember") or 100)
        except (TypeError, ValueError):
            normalized["maxMember"] = 100

        normalized["secret"] = bool(normalized.get("secret", False))

        channel_type = normalized.get("type", ChannelType.TEXT)
        if isinstance(channel_type, str):
            try:
                normalized["type"] = ChannelType(channel_type.upper())
            except ValueError as exc:
                allowed = ", ".join(member.value for member in ChannelType)
                raise OopzApiError(
                    f"invalid create channel payload: unsupported type {channel_type!r}, allowed: {allowed}",
                    payload=data,
                ) from exc
        else:
            normalized["type"] = channel_type

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "CreateChannelBody":
        return cls.model_validate(data)



class VoiceChanelMemberInfo(BaseModel):
    uid: str = ""

    bot_type: str = Field(default="", alias="botType")
    dimensions: str = ""
    enter_time: str = Field(default="", alias="enterTime")
    framerate: str = ""

    is_bot: bool = Field(default=False, alias="isBot")
    people_limit: int = Field(default=0, alias="peopleLimit")

    screen_sharing_state: str = Field(default="", alias="screenSharingState")
    screen_type: str = Field(default="", alias="screenType")

    sort: int = 0

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid member payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["uid"] = str(normalized.get("uid") or "")
        normalized["botType"] = str(normalized.get("botType") or "")
        normalized["dimensions"] = str(normalized.get("dimensions") or "")
        normalized["enterTime"] = str(normalized.get("enterTime") or "")
        normalized["framerate"] = str(normalized.get("framerate") or "")
        normalized["screenSharingState"] = str(normalized.get("screenSharingState") or "")
        normalized["screenType"] = str(normalized.get("screenType") or "")

        normalized["isBot"] = bool(normalized.get("isBot", False))

        try:
            normalized["peopleLimit"] = int(normalized.get("peopleLimit") or 0)
        except (TypeError, ValueError):
            normalized["peopleLimit"] = 0

        try:
            normalized["sort"] = int(normalized.get("sort") or 0)
        except (TypeError, ValueError):
            normalized["sort"] = 0

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "VoiceChanelMemberInfo":
        return cls.model_validate(data)

class VoiceChannelMembersResult(BaseModel):
    channel_members: dict[str, list[VoiceChanelMemberInfo]] = Field(default_factory=dict, alias="channelMembers")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError(
                "invalid voice channel members payload: expected dict",
                payload=data,
            )

        normalized = dict(data)
        raw_members = normalized.get("channelMembers", {})

        if not isinstance(raw_members, Mapping):
            normalized["channelMembers"] = {}
            return normalized

        channel_members: dict[str, list[Any]] = {}
        for channel_id, members in raw_members.items():
            key = str(channel_id or "")
            if not key:
                continue

            if isinstance(members, list):
                channel_members[key] = members
            else:
                channel_members[key] = []

        normalized["channelMembers"] = channel_members
        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "VoiceChannelMembersResult":
        return cls.model_validate(data)
