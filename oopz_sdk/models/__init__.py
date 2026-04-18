from .area import Area
from .attachment import Attachment, AudioAttachment, ImageAttachment
from .base import BaseModel
from .channel import Channel, ChannelGroup
from .compat import (
    AreaInfo,
    ChannelInfo,
    ChannelMessage,
    ChatMessageEvent,
    LifecycleEvent,
    UploadAttachment,
    VoiceChannelMember,
)
from .event import Event, MessageEvent
from .member import Member
from .message import Message
from .response import (
    ApiResponse,
    AreaBlock,
    AreaBlocksResult,
    AreaMembersPage,
    ChannelGroupsResult,
    ChannelSetting,
    DailySpeechResult,
    JoinedAreasResult,
    MessageListResult,
    MessageSendResult,
    OperationResult,
    PersonDetail,
    PrivateSessionResult,
    SelfDetail,
    UploadResult,
    VoiceChannelMembersResult,
)

JsonObject = dict[str, object]
JsonList = list[object]
PersonInfo = Member

__all__ = [
    "ApiResponse",
    "Area",
    "AreaBlock",
    "AreaBlocksResult",
    "AreaInfo",
    "AreaMembersPage",
    "Attachment",
    "AudioAttachment",
    "BaseModel",
    "Channel",
    "ChannelInfo",
    "ChannelMessage",
    "ChannelGroup",
    "ChannelGroupsResult",
    "ChannelSetting",
    "ChatMessageEvent",
    "DailySpeechResult",
    "Event",
    "ImageAttachment",
    "JoinedAreasResult",
    "JsonList",
    "JsonObject",
    "LifecycleEvent",
    "Member",
    "Message",
    "MessageListResult",
    "MessageEvent",
    "MessageSendResult",
    "OperationResult",
    "PersonDetail",
    "PersonInfo",
    "PrivateSessionResult",
    "SelfDetail",
    "UploadAttachment",
    "UploadResult",
    "VoiceChannelMember",
    "VoiceChannelMembersResult",
]
