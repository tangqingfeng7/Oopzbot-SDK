from .area import JoinedAreaInfo, AreaInfo, ChannelGroupInfo, AreaMembersPage
from .attachment import Attachment, AudioAttachment, ImageAttachment, UploadTicket, UploadedFileResult
from .base import BaseModel, OperationResult
from .channel import (Channel, ChannelGroup, ChannelSetting, ChannelType,
                      CreateChannelResult, ChannelEdit, ChannelSign, VoiceChannelMembersResult)
from .event import Event, MessageEvent
from .member import Member
from .message import Message, MessageSendResult, PrivateSession
from .response import (
    AreaBlock,
    AreaBlocksResult,
    DailySpeechResult,
    MessageListResult,
    PersonDetail,
    SelfDetail,
)

JsonObject = dict[str, object]
JsonList = list[object]
PersonInfo = Member

__all__ = [
    "JoinedAreaInfo",
    "AreaInfo",
    "AreaBlock",
    "AreaBlocksResult",
    "Attachment",
    "AudioAttachment",
    "AreaMembersPage",
    "BaseModel",
    "ChannelSetting",
    "ChannelGroupInfo",
    "ChannelEdit",
    "CreateChannelResult",
    "ChannelType",
    "ChannelSign",
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
    "VoiceChannelMembersResult",
    "PersonInfo",
    "PrivateSession",
    "SelfDetail",
    "VoiceChannelMembersResult",
]
