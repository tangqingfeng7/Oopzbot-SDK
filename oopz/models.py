"""Oopz SDK 公开类型与结果模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

import requests


JsonObject = dict[str, object]
JsonList = list[object]


class ChannelInfo(TypedDict, total=False):
    """频道信息。"""

    id: str
    name: str
    type: str
    group: str
    secret: bool


class ChannelGroup(TypedDict, total=False):
    """频道分组信息。"""

    id: str
    name: str
    channels: list[ChannelInfo]


class AreaInfo(TypedDict, total=False):
    """域信息。"""

    id: str
    name: str
    code: str
    description: str


class PersonInfo(TypedDict, total=False):
    """用户信息。"""

    uid: str
    id: str
    name: str
    online: int


class VoiceChannelMember(TypedDict, total=False):
    """语音频道成员信息。"""

    uid: str
    id: str
    name: str
    avatar: str
    online: int


class AreaMembersPage(TypedDict, total=False):
    """域成员分页结果。"""

    members: list[PersonInfo]
    onlineCount: int
    totalCount: int
    userCount: int
    fetchedCount: int
    stale: bool
    rateLimited: bool
    from_cache: bool


class ChatMessagePayload(TypedDict, total=False):
    """聊天消息原始载荷。"""

    messageId: str
    area: str
    channel: str
    person: str
    content: str
    timestamp: str
    attachments: list[JsonObject]


@dataclass(slots=True)
class OperationResult:
    """通用操作结果。"""

    ok: bool = True
    message: str = ""
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class MessageSendResult:
    """消息发送结果。"""

    message_id: str
    area: str
    channel: str
    target: str = ""
    client_message_id: str = ""
    timestamp: str = ""
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class UploadAttachment:
    """上传后的附件信息。"""

    file_key: str
    url: str
    attachment_type: str
    file_size: int = 0
    width: int = 0
    height: int = 0
    file_hash: str = ""
    animated: bool = False
    display_name: str = ""
    duration: int = 0

    def as_payload(self) -> JsonObject:
        """转换为平台接口所需的附件字典。"""
        payload: JsonObject = {
            "fileKey": self.file_key,
            "url": self.url,
            "fileSize": self.file_size,
            "hash": self.file_hash,
            "animated": self.animated,
            "displayName": self.display_name,
            "attachmentType": self.attachment_type,
        }
        if self.width:
            payload["width"] = self.width
        if self.height:
            payload["height"] = self.height
        if self.duration:
            payload["duration"] = self.duration
        return payload


@dataclass(slots=True)
class UploadResult:
    """上传结果。"""

    attachment: UploadAttachment
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class PrivateSessionResult:
    """私信会话结果。"""

    channel: str
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class ChannelGroupsResult:
    """域内频道分组结果。"""

    groups: list[ChannelGroup]
    from_cache: bool = False
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class JoinedAreasResult:
    """已加入域列表结果。"""

    areas: list[AreaInfo]
    from_cache: bool = False
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class PersonDetail:
    """用户资料结果。"""

    uid: str = ""
    name: str = ""
    avatar: str = ""
    common_id: str = ""
    bio: str = ""
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class SelfDetail:
    """当前登录用户资料结果。"""

    uid: str = ""
    name: str = ""
    avatar: str = ""
    mobile: str = ""
    from_cache: bool = False
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class ChannelSetting:
    """频道设置结果。"""

    channel: str
    area: str = ""
    name: str = ""
    text_gap_second: int = 0
    voice_quality: str = "64k"
    voice_delay: str = "LOW"
    max_member: int = 30000
    voice_control_enabled: bool = False
    text_control_enabled: bool = False
    text_roles: list[object] = field(default_factory=list)
    voice_roles: list[object] = field(default_factory=list)
    access_control_enabled: bool = False
    accessible: list[object] = field(default_factory=list)
    accessible_members: list[str] = field(default_factory=list)
    secret: bool = False
    has_password: bool = False
    password: str = ""
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)

    def to_edit_body(self, *, area: str | None = None) -> JsonObject:
        """转换为编辑频道设置时使用的请求体。"""
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
class VoiceChannelMembersResult:
    """语音频道成员结果。"""

    channels: dict[str, list[VoiceChannelMember]]
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class DailySpeechResult:
    """每日一句结果。"""

    words: str
    author: str = ""
    source: str = ""
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class ChannelMessage:
    """频道消息结果。"""

    message_id: str
    area: str = ""
    channel: str = ""
    person: str = ""
    content: str = ""
    timestamp: str = ""
    attachments: list[JsonObject] = field(default_factory=list)
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class AreaBlock:
    """域封禁成员结果。"""

    uid: str = ""
    name: str = ""
    reason: str = ""
    payload: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class AreaBlocksResult:
    """域封禁列表结果。"""

    blocks: list[AreaBlock]
    payload: JsonObject = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)


@dataclass(slots=True)
class ChatMessageEvent:
    """聊天事件。"""

    message_id: str
    area: str
    channel: str
    person: str
    content: str
    timestamp: str = ""
    attachments: list[JsonObject] = field(default_factory=list)
    raw: JsonObject = field(default_factory=dict)


@dataclass(slots=True)
class LifecycleEvent:
    """客户端生命周期事件。"""

    state: str
    attempt: int = 0
    code: int | None = None
    reason: str = ""
    error: str = ""
    payload: JsonObject = field(default_factory=dict)
