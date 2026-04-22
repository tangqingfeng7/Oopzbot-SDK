from enum import Enum
from typing import Mapping, Any

from pydantic import Field, model_validator

from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.models.base import SDKBaseModel


class TextMuteInterval(Enum):
    S60 = (1, 1, "60秒")
    M5 = (5, 2, "5分钟")
    H1 = (60, 3, "1小时")
    D1 = (1440, 4, "1天")
    D3 = (4320, 5, "3天")
    D7 = (10080, 6, "7天")

    def __init__(self, minutes: int, interval_id: int, label: str):
        self.minutes = minutes
        self.interval_id = interval_id
        self.label = label

    @classmethod
    def pick(cls, minutes: int) -> "TextMuteInterval":
        for item in cls:
            if minutes <= item.minutes:
                return item
        return list(cls)[-1]


class VoiceMuteInterval(Enum):
    S60 = (1, 7, "60秒")
    M5 = (5, 8, "5分钟")
    H1 = (60, 9, "1小时")
    D1 = (1440, 10, "1天")
    D3 = (4320, 11, "3天")
    D7 = (10080, 12, "7天")

    def __init__(self, minutes: int, interval_id: int, label: str):
        self.minutes = minutes
        self.interval_id = interval_id
        self.label = label

    @classmethod
    def pick(cls, minutes: int) -> "VoiceMuteInterval":
        for item in cls:
            if minutes <= item.minutes:
                return item
        return list(cls)[-1]

class AreaBlockUserInfo(SDKBaseModel):
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

        normalized["online"] = bool(normalized.get("online", False))

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
    def from_api(cls, data: Mapping[str, Any]) -> "AreaMemberProfile":
        return cls.model_validate(data)
