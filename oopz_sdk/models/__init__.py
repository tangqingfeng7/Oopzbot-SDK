from .area import JoinedAreaInfo, AreaInfo, ChannelGroupInfo, AreaMembersPage
from .attachment import Attachment, AudioAttachment, ImageAttachment
from .base import BaseModel
from .channel import Channel, ChannelGroup
from .event import Event, MessageEvent
from .member import Member
from .message import Message
from .response import (
    ApiResponse,
    AreaBlock,
    AreaBlocksResult,
    ChannelGroupsResult,
    ChannelSetting,
    DailySpeechResult,
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
    "JoinedAreaInfo",
    "AreaInfo",
    "AreaBlock",
    "AreaBlocksResult",
    "Attachment",
    "AudioAttachment",
    "AreaMembersPage",
    "BaseModel",
    "ChannelGroupsResult",
    "ChannelSetting",
    "ChannelGroupInfo",
    "DailySpeechResult",
    "Event",
    "ImageAttachment",
    "JsonList",
    "JsonObject",
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
    "UploadResult",
    "VoiceChannelMembersResult",
]
