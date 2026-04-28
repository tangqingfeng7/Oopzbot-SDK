from __future__ import annotations

from typing import Any, Mapping

from pydantic import Field, model_validator

from .base import BaseModel

from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.utils.payload import coerce_bool


class UserInfo(BaseModel):
    avatar: str = ""
    avatar_frame: str = Field(default="", alias="avatarFrame")
    avatar_frame_animation: str = Field(default="", alias="avatarFrameAnimation")
    avatar_frame_expire_time: int = Field(default=0, alias="avatarFrameExpireTime")

    badges: Any = None
    introduction: str = ""
    mark: str = ""
    mark_expire_time: int = Field(default=0, alias="markExpireTime")
    mark_name: str = Field(default="", alias="markName")

    name: str = ""
    online: bool = False

    memberLevel: int = Field(default=0, alias="memberLevel")

    person_role: str = Field(default="", alias="personRole")
    person_type: str = Field(default="", alias="personType")

    pid: str = ""
    status: str = ""
    uid: str = ""
    user_common_id: str = Field(default="", alias="userCommonId")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid area member profile payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["avatar"] = str(normalized.get("avatar") or "")
        normalized["avatarFrame"] = str(normalized.get("avatarFrame") or "")
        normalized["avatarFrameAnimation"] = str(normalized.get("avatarFrameAnimation") or "")
        normalized["introduction"] = str(normalized.get("introduction") or "")
        normalized["mark"] = str(normalized.get("mark") or "")
        normalized["markName"] = str(normalized.get("markName") or "")
        normalized["name"] = str(normalized.get("name") or "")
        normalized["personRole"] = str(normalized.get("personRole") or "")
        normalized["personType"] = str(normalized.get("personType") or "")
        normalized["pid"] = str(normalized.get("pid") or "")
        normalized["status"] = str(normalized.get("status") or "")
        normalized["uid"] = str(normalized.get("uid") or "")
        normalized["userCommonId"] = str(normalized.get("userCommonId") or "")
        normalized["memberLevel"] = int(normalized.get("memberLevel") or 0)

        normalized["online"] = coerce_bool(normalized.get("online"), default=False)

        try:
            normalized["avatarFrameExpireTime"] = int(normalized.get("avatarFrameExpireTime") or 0)
        except (TypeError, ValueError):
            normalized["avatarFrameExpireTime"] = 0

        try:
            normalized["markExpireTime"] = int(normalized.get("markExpireTime") or 0)
        except (TypeError, ValueError):
            normalized["markExpireTime"] = 0

        normalized["badges"] = normalized.get("badges")

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "UserInfo":
        return cls.model_validate(data)


class Profile(BaseModel):
    area_avatar: str = Field(default="", alias="areaAvatar")
    area_max_num: int = Field(default=0, alias="areaMaxNum")
    area_name: str = Field(default="", alias="areaName")

    avatar: str = ""
    avatar_frame: str = Field(default="", alias="avatarFrame")
    avatar_frame_animation: str = Field(default="", alias="avatarFrameAnimation")
    avatar_frame_expire_time: int = Field(default=0, alias="avatarFrameExpireTime")

    badges: list[Any] = Field(default_factory=list)

    banner: str = ""
    card_decoration: str = Field(default="", alias="cardDecoration")
    card_decoration_expire_time: int = Field(default=0, alias="cardDecorationExpireTime")

    community_personal_rec: bool = Field(default=False, alias="communityPersonalRec")
    default_avatar: bool = Field(default=False, alias="defaultAvatar")
    default_name: bool = Field(default=False, alias="defaultName")

    disabled_end_time: int = Field(default=0, alias="disabledEndTime")
    disabled_start_time: int = Field(default=0, alias="disabledStartTime")

    display_playing_state: Any = Field(default=None, alias="displayPlayingState")
    display_type: str = Field(default="", alias="displayType")

    fans_count: int = Field(default=0, alias="fansCount")
    fixed_private_message: bool = Field(default=False, alias="fixedPrivateMessage")
    follow_count: int = Field(default=0, alias="followCount")
    follow_private: bool = Field(default=False, alias="followPrivate")

    greeting: str = ""
    introduction: str = ""
    ip_address: str = Field(default="", alias="ipAddress")
    is_abroad: bool = Field(default=False, alias="isAbroad")

    like_count: int = Field(default=0, alias="likeCount")

    mark: str = ""
    mark_expire_time: int = Field(default=0, alias="markExpireTime")
    mark_name: str = Field(default="", alias="markName")

    mobile_banner: str = Field(default="", alias="mobileBanner")
    music_state: str = Field(default="", alias="musicState")
    mute: Any = None
    mutual_follow_count: int = Field(default=0, alias="mutualFollowCount")

    name: str = ""
    online: bool = False

    person_role: str = Field(default="", alias="personRole")
    person_type: str = Field(default="", alias="personType")
    person_vip_end_time: int = Field(default=0, alias="personVIPEndTime")
    person_vip_start_time: int = Field(default=0, alias="personVIPStartTime")

    phone: str = ""
    pid: str = ""
    pid_level_name: str = Field(default="", alias="pidLevelName")
    pid_tag_black: str = Field(default="", alias="pidTagBlack")
    pid_tag_white: str = Field(default="", alias="pidTagWhite")

    playing_game_image: str = Field(default="", alias="playingGameImage")
    playing_state: str = Field(default="", alias="playingState")
    playing_time: int = Field(default=0, alias="playingTime")

    pwd_set_time: int = Field(default=0, alias="pwdSetTime")
    recommend_area: str = Field(default="", alias="recommendArea")
    song_state: str = Field(default="", alias="songState")

    status: str = ""
    stealth: bool = False

    uid: str = ""
    use_booster: bool = Field(default=False, alias="useBooster")
    user_common_id: str = Field(default="", alias="userCommonId")
    user_level: int = Field(default=0, alias="userLevel")

    vip_id: str = Field(default="", alias="vipId")
    voice_disable: int = Field(default=0, alias="voiceDisable")

    wx_nickname: str = Field(default="", alias="wxNickname")
    wx_union_id: str = Field(default="", alias="wxUnionId")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid person profile payload: expected dict", payload=data)

        normalized = dict(data)

        str_fields = (
            "areaAvatar", "areaName", "avatar", "avatarFrame", "avatarFrameAnimation",
            "banner", "cardDecoration", "displayType", "greeting", "introduction",
            "ipAddress", "mark", "markName", "mobileBanner", "musicState", "name",
            "personRole", "personType", "phone", "pid", "pidLevelName", "pidTagBlack",
            "pidTagWhite", "playingGameImage", "playingState", "recommendArea",
            "songState", "status", "uid", "userCommonId", "vipId", "wxNickname",
            "wxUnionId",
        )
        for key in str_fields:
            normalized[key] = str(normalized.get(key) or "")

        int_fields = {
            "areaMaxNum": 0,
            "avatarFrameExpireTime": 0,
            "cardDecorationExpireTime": 0,
            "disabledEndTime": 0,
            "disabledStartTime": 0,
            "fansCount": 0,
            "followCount": 0,
            "likeCount": 0,
            "markExpireTime": 0,
            "mutualFollowCount": 0,
            "personVIPEndTime": 0,
            "personVIPStartTime": 0,
            "playingTime": 0,
            "pwdSetTime": 0,
            "userLevel": 0,
            "voiceDisable": 0,
        }
        for key, default in int_fields.items():
            try:
                normalized[key] = int(normalized.get(key) or default)
            except (TypeError, ValueError):
                normalized[key] = default

        bool_fields = (
            "communityPersonalRec",
            "defaultAvatar",
            "defaultName",
            "fixedPrivateMessage",
            "followPrivate",
            "isAbroad",
            "online",
            "stealth",
            "useBooster",
        )
        for key in bool_fields:
            normalized[key] = coerce_bool(normalized.get(key), default=False)

        badges = normalized.get("badges", [])
        normalized["badges"] = badges if isinstance(badges, list) else []

        normalized["displayPlayingState"] = normalized.get("displayPlayingState")
        normalized["mute"] = normalized.get("mute")

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Profile":
        return cls.model_validate(data)


class UserLevelInfo(BaseModel):
    auth_desc: str = Field(default="", alias="authDesc")
    auth_state: int = Field(default=0, alias="authState")

    current_level: int = Field(default=0, alias="currentLevel")
    current_level_full_points: int = Field(default=0, alias="currentLevelFullPoints")

    has_not_receive_prize: bool = Field(default=False, alias="hasNotReceivePrize")

    next_level: int = Field(default=0, alias="nextLevel")
    next_level_distance: int = Field(default=0, alias="nextLevelDistance")

    pay_points: int = Field(default=0, alias="payPoints")
    sign_in_points: int = Field(default=0, alias="signInPoints")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid user level progress payload: expected dict", payload=data)

        normalized = dict(data)

        normalized["authDesc"] = str(normalized.get("authDesc") or "")

        int_fields = {
            "authState": 0,
            "currentLevel": 0,
            "currentLevelFullPoints": 0,
            "nextLevel": 0,
            "nextLevelDistance": 0,
            "payPoints": 0,
            "signInPoints": 0,
        }
        for key, default in int_fields.items():
            try:
                normalized[key] = int(normalized.get(key) or default)
            except (TypeError, ValueError):
                normalized[key] = default

        normalized["hasNotReceivePrize"] = coerce_bool(
            normalized.get("hasNotReceivePrize"), default=False
        )

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "UserLevelInfo":
        return cls.model_validate(data)


class Friendship(BaseModel):
    uid: str = ""
    online: bool = False
    name: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise OopzApiError("invalid friendship payload: expected dict", payload=data)

        normalized = dict(data)
        normalized["uid"] = str(normalized.get("uid") or "")
        normalized["online"] = coerce_bool(normalized.get("online"), default=False)
        normalized["name"] = str(normalized.get("name") or "")

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Friendship":
        return Friendship.model_validate(data)


class FriendshipRequest(BaseModel):
    friend_request_id: int = Field(default=0, alias="friendRequestId")
    uid: str = ""
    create_time: str = Field(default="", alias="createTime")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid friendship request payload: expected dict", payload=data)

        normalized = dict(data)

        try:
            normalized["friendRequestId"] = int(normalized.get("friendRequestId") or 0)
        except (TypeError, ValueError):
            normalized["friendRequestId"] = 0

        normalized["uid"] = str(normalized.get("uid") or "")
        normalized["createTime"] = str(normalized.get("createTime") or "")

        return normalized

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "FriendshipRequest":
        return cls.model_validate(data)