from .area import JoinedAreaInfo, AreaInfo, ChannelGroupInfo, AreaMembersPage, AreaUserDetail, RoleInfo
from .attachment import Attachment, ImageAttachment, UploadTicket, UploadedFileResult
from .base import OperationResult
from .channel import (ChannelSetting, ChannelType,
                      CreateChannelResult, ChannelEdit, ChannelSign, VoiceChannelMembersResult)
from .event import Event, MessageEvent
from .member import UserInfo, Profile, UserLevelInfo
from .message import Message, MessageSendResult, PrivateSession
from .moderation import TextMuteInterval, VoiceMuteInterval
from .segment import build_segments, normalize_message_parts

JsonObject = dict[str, object]
JsonList = list[object]

__all__ = [
    "JoinedAreaInfo",
    "AreaInfo",
    "Attachment",
    "RoleInfo",
    "AreaMembersPage",
    "ChannelSetting",
    "ChannelGroupInfo",
    "ChannelEdit",
    "AreaUserDetail",
    "CreateChannelResult",
    "ChannelType",
    "ChannelSign",
    "Event",
    "ImageAttachment",
    "JsonList",
    "JsonObject",
    "UploadTicket",
    "UploadedFileResult",
    "UserInfo",
    "Message",
    "MessageEvent",
    "MessageSendResult",
    "OperationResult",
    "VoiceChannelMembersResult",
    "PrivateSession",
    "TextMuteInterval",
    "VoiceMuteInterval",
    "Profile",
    "UserLevelInfo",
    "build_segments",
    "normalize_message_parts"
]
