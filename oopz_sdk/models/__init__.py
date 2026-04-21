from .area import JoinedAreaInfo, AreaInfo, ChannelGroupInfo, AreaMembersPage
from .attachment import Attachment, AudioAttachment, ImageAttachment, UploadTicket, UploadedFileResult
from .base import BaseModel, OperationResult
from .channel import Channel, ChannelGroup
from .event import Event, MessageEvent
from .member import Member
from .message import Message, MessageSendResult, PrivateSession
from .response import (
    ApiResponse,
    AreaBlock,
    AreaBlocksResult,
    ChannelGroupsResult,
    ChannelSetting,
    DailySpeechResult,
    MessageListResult,
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
    "UploadTicket",
    "UploadedFileResult",
    "Member",
    "Message",
    "MessageListResult",
    "MessageEvent",
    "MessageSendResult",
    "OperationResult",
    "PersonDetail",
    "PersonInfo",
    "PrivateSession",
    "SelfDetail",
    "UploadResult",
    "VoiceChannelMembersResult",
]
