from __future__ import annotations

from typing import Any, Mapping

from pydantic import AliasChoices, Field, model_validator

from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.utils.payload import coerce_bool
from .base import BaseModel


class JoinedAreaInfo(BaseModel):
    area_id: str = Field(default="", alias="id")
    code: str = ""
    name: str = ""
    avatar: str = ""
    banner: str = ""
    level: int = 0
    owner: str = ""
    group_id: str = Field(default="", alias="groupID")
    group_name: str = Field(default="", alias="groupName")
    subscript: int = 0

    @model_validator(mode="after")
    def validate_required_fields(self) -> "JoinedAreaInfo":
        if not self.area_id:
            raise OopzApiError("invalid area payload: missing id", payload=self.model_dump(by_alias=True))
        if not self.name:
            raise OopzApiError("invalid area payload: missing name", payload=self.model_dump(by_alias=True))
        if not self.owner:
            raise OopzApiError("invalid area payload: missing owner", payload=self.model_dump(by_alias=True))
        return self

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "JoinedAreaInfo":
        if not isinstance(data, dict):
            raise OopzApiError("invalid area payload: expected dict", payload=data)
        return cls.model_validate(data)


class AreaRoleInfo(BaseModel):
    category_keys: list[str] = Field(default_factory=list, alias="categoryKeys")
    is_owner: bool = Field(default=False, alias="isOwner")
    max_role: int = Field(default=0, alias="maxRole")
    privilege_keys: list[str] = Field(default_factory=list, alias="privilegeKeys")
    roles: list[int] = Field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> "AreaRoleInfo":
        return cls.model_validate(data or {})


class AreaRole(BaseModel):
    description: str = ""
    is_display: bool = Field(default=False, alias="isDisplay")
    name: str = ""
    role_id: int = Field(default=0, alias="roleID")
    sort: int = 0
    type: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> "AreaRole":
        return cls.model_validate(data or {})


class AreaInfo(BaseModel):
    area_role_infos: AreaRoleInfo = Field(default_factory=AreaRoleInfo, alias="areaRoleInfos")
    avatar: str = ""
    banner: str = ""
    code: str = ""
    desc: str = ""
    disable_text_to: str | None = Field(default=None, alias="disableTextTo")
    disable_voice_to: str | None = Field(default=None, alias="disableVoiceTo")
    edit_count: int = Field(default=0, alias="editCount")
    home_page_channel_id: str = Field(default="", alias="homePageChannelId")
    area_id: str = Field(default="", alias="id")
    is_public: bool = Field(default=False, alias="isPublic")
    name: str = ""
    now: int = 0
    private_channels: list[str] = Field(default_factory=list, alias="privateChannels")
    role_list: list[AreaRole] = Field(default_factory=list, alias="roleList")
    subscribed: bool = False

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AreaInfo":
        if not isinstance(data, dict):
            raise OopzApiError("invalid area detail payload: expected dict", payload=data)
        return cls.model_validate(data)


class AreaMemberInfo(BaseModel):
    display_type: str = Field(default="", alias="displayType")
    online: int = 0
    playing_state: str = Field(default="", alias="playingState")
    role: int = 0
    role_sort: int = Field(default=0, alias="roleSort")
    role_status: int = Field(default=0, alias="roleStatus")
    uid: str = ""

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "AreaMemberInfo":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid area member payload: expected dict", payload=data)
        return cls.model_validate(data)


class AreaRoleCountInfo(BaseModel):
    count: int = 0
    role: int = 0

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "AreaRoleCountInfo":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid area role count payload: expected dict", payload=data)
        return cls.model_validate(data)


class AreaMembersPage(BaseModel):
    members: list[AreaMemberInfo] = Field(default_factory=list)
    role_count: list[AreaRoleCountInfo] = Field(default_factory=list, alias="roleCount")
    total_count: int = Field(default=0, alias="totalCount")
    from_cache: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid area members payload: expected dict", payload=data)

        members_raw = data.get("members", [])
        if not isinstance(members_raw, list):
            raise OopzApiError("invalid area members payload: members must be a list", payload=data)

        role_count_raw = data.get("roleCount", [])
        if not isinstance(role_count_raw, list):
            raise OopzApiError("invalid area members payload: roleCount must be a list", payload=data)

        normalized = dict(data)
        normalized.setdefault("payload", dict(data))
        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "AreaMembersPage":
        return cls.model_validate(data)


class ChannelInfoSettings(BaseModel):
    disable_text_levels: list[int] | None = Field(default=None, alias="disableTextLevels")
    disable_voice_levels: list[int] | None = Field(default=None, alias="disableVoiceLevels")
    max_member: int = Field(default=0, alias="maxMember")
    member_public: bool = Field(default=False, alias="memberPublic")
    text_control_enabled: bool = Field(default=False, alias="textControlEnabled")
    text_gap_second: int = Field(default=0, alias="textGapSecond")
    text_roles: list[int] = Field(default_factory=list, alias="textRoles")
    voice_control_enabled: bool = Field(default=False, alias="voiceControlEnabled")
    voice_delay: str = Field(default="", alias="voiceDelay")
    voice_quality: str = Field(default="", alias="voiceQuality")
    voice_roles: list[int] = Field(default_factory=list, alias="voiceRoles")

    @classmethod
    def from_api(cls, data: dict[str, Any] | None) -> "ChannelInfoSettings":
        return cls.model_validate(data or {})


class ChannelInfo(BaseModel):
    area_id: str = Field(default="", alias="areaId")
    group_id: str = Field(default="", alias="groupId")
    channel_id: str = Field(default="", alias="id")
    is_temp: bool = Field(default=False, alias="isTemp")
    name: str = ""
    number: int = 0
    secret: bool = False
    settings: ChannelInfoSettings = Field(default_factory=ChannelInfoSettings)
    system: bool = False
    tag: str = ""
    channel_type: str = Field(default="", alias="type")

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "ChannelInfo":
        if not isinstance(data, dict):
            raise OopzApiError("invalid channel payload: expected dict", payload=data)
        return cls.model_validate(data)


class ChannelGroupInfo(BaseModel):
    # 接口实际返回的键在不同版本间可能是 `IsEnableTemp`（大驼峰）或 `isEnableTemp`
    # （与本模型其它小驼峰字段一致）。用 AliasChoices 两边都兼容；序列化仍按
    # 历史字段名 `IsEnableTemp` 输出，避免回写破坏。
    is_enable_temp: bool = Field(
        default=False,
        validation_alias=AliasChoices("IsEnableTemp", "isEnableTemp"),
        serialization_alias="IsEnableTemp",
    )
    area: str = ""
    channels: list[ChannelInfo] = Field(default_factory=list)
    group_id: str = Field(default="", alias="id")
    name: str = ""
    sort: int = 0
    system: bool = False
    temp_channel_default_max_member: int = Field(default=0, alias="tempChannelDefaultMaxMember")
    temp_channel_max_limit_member: int = Field(default=0, alias="tempChannelMaxLimitMember")

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "ChannelGroupInfo":
        if not isinstance(data, dict):
            raise OopzApiError("invalid channel group payload: expected dict", payload=data)
        return cls.model_validate(data)


class AreaUserDetail(BaseModel):
    disable_text_to: int = Field(default=0, alias="disableTextTo")
    disable_voice_to: int = Field(default=0, alias="disableVoiceTo")
    higher_uid: str = Field(default="", alias="higherUid")
    roles: list[RoleInfo] = Field(default_factory=list, alias="list")
    now: int = 0

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid higher uid info payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["higherUid"] = str(normalized.get("higherUid") or "")

        raw_list = normalized.get("list", [])
        normalized["list"] = raw_list if isinstance(raw_list, list) else []

        try:
            normalized["now"] = int(normalized.get("now") or 0)
        except (TypeError, ValueError):
            normalized["now"] = 0

        normalized["disableTextTo"] = normalized.get("disableTextTo")
        normalized["disableVoiceTo"] = normalized.get("disableVoiceTo")

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "AreaUserDetail":
        return cls.model_validate(data)


class RoleInfo(BaseModel):
    description: str = ""
    name: str = ""
    owned: bool = False
    role_id: int = Field(default=0, alias="roleID")
    sort: int = 0

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid role info payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["description"] = str(normalized.get("description") or "")
        normalized["name"] = str(normalized.get("name") or "")
        normalized["owned"] = coerce_bool(normalized.get("owned"), default=False)

        try:
            normalized["roleID"] = int(normalized.get("roleID") or 0)
        except (TypeError, ValueError):
            normalized["roleID"] = 0

        try:
            normalized["sort"] = int(normalized.get("sort") or 0)
        except (TypeError, ValueError):
            normalized["sort"] = 0

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "RoleInfo":
        return cls.model_validate(data)
