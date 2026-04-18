from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from .area import Area
from .attachment import Attachment
from .channel import Channel, ChannelGroup
from .base import BaseModel
from .member import Member
from .message import Message
from ..transport.http import HttpResponse


@dataclass(slots=True)
class ApiResponse(BaseModel):
    status: bool = False
    message: str = ""
    data: Any = field(default_factory=dict)
    code: str | int | None = None


@dataclass(slots=True)
class OperationResult(BaseModel):
    ok: bool = True
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class MessageSendResult(BaseModel):
    message_id: str
    area: str
    channel: str
    target: str = ""
    client_message_id: str = ""
    timestamp: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class UploadResult(BaseModel):
    attachment: Attachment
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class PrivateSessionResult(BaseModel):
    channel: str
    target: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    response: HttpResponse | None = field(default=None, repr=False)


@dataclass(slots=True)
class AreaMembersPage(BaseModel):
    members: list[Member] = field(default_factory=list)
    online_count: int = 0
    total_count: int = 0
    user_count: int = 0
    fetched_count: int = 0
    stale: bool = False
    rate_limited: bool = False
    from_cache: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class JoinedAreasResult(BaseModel):
    areas: list[Area] = field(default_factory=list)
    from_cache: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class ChannelGroupsResult(BaseModel):
    groups: list[ChannelGroup] = field(default_factory=list)
    from_cache: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class PersonDetail(BaseModel):
    uid: str = ""
    name: str = ""
    avatar: str = ""
    common_id: str = ""
    bio: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class SelfDetail(BaseModel):
    uid: str = ""
    name: str = ""
    avatar: str = ""
    mobile: str = ""
    from_cache: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class ChannelSetting(BaseModel):
    channel: str
    area: str = ""
    name: str = ""
    text_gap_second: int = 0
    voice_quality: str = "64k"
    voice_delay: str = "LOW"
    max_member: int = 30000
    voice_control_enabled: bool = False
    text_control_enabled: bool = False
    text_roles: list[Any] = field(default_factory=list)
    voice_roles: list[Any] = field(default_factory=list)
    access_control_enabled: bool = False
    accessible: list[Any] = field(default_factory=list)
    accessible_members: list[str] = field(default_factory=list)
    secret: bool = False
    has_password: bool = False
    password: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)

    def to_edit_body(self, *, area: str | None = None) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "area": area or self.area,
            "name": self.name,
            "textGapSecond": self.text_gap_second,
            "voiceQuality": self.voice_quality,
            "voiceDelay": self.voice_delay,
            "maxMember": self.max_member,
            "voiceControlEnabled": self.voice_control_enabled,
            "textControlEnabled": self.text_control_enabled,
            "textRoles": list(self.text_roles),
            "voiceRoles": list(self.voice_roles),
            "accessControlEnabled": self.access_control_enabled,
            "accessible": list(self.accessible),
            "accessibleMembers": list(self.accessible_members),
            "secret": self.secret,
            "hasPassword": self.has_password,
            "password": self.password,
        }


@dataclass(slots=True)
class VoiceChannelMembersResult(BaseModel):
    channels: dict[str, list[Member]] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class DailySpeechResult(BaseModel):
    words: str
    author: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class AreaBlock(BaseModel):
    uid: str = ""
    name: str = ""
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AreaBlocksResult(BaseModel):
    blocks: list[AreaBlock] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class MessageListResult(BaseModel):
    messages: list[Message] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)
