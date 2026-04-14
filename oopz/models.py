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


class AreaMembersPage(TypedDict, total=False):
    """域成员分页结果。"""

    members: list[PersonInfo]
    onlineCount: int
    totalCount: int
    userCount: int
    fetchedCount: int
    stale: bool
    rateLimited: bool


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
