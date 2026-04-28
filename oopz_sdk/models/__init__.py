from .area import JoinedAreaInfo, AreaInfo, ChannelGroupInfo, AreaMembersPage, AreaUserDetail, RoleInfo
from .attachment import (
    Attachment,
    AudioAttachment,
    FileAttachment,
    ImageAttachment,
    UploadTicket,
    UploadedFileResult,
)
from .base import OperationResult
from .channel import (ChannelSetting, ChannelType,
                      CreateChannelResult, ChannelEdit, ChannelSign, VoiceChannelMembersResult)
from .event import Event, MessageEvent
from .person import UserInfo, Profile, UserLevelInfo, Friendship, FriendshipRequest, UserRemarkNamesResponse
from .message import Message, MessageSendResult, PrivateSession
from .moderation import TextMuteInterval, VoiceMuteInterval
from .segment import build_segments, normalize_message_parts

JsonObject = dict[str, object]
JsonList = list[object]

__all__ = [
    "JoinedAreaInfo",
    "AreaInfo",
    "Attachment",
    "AudioAttachment",
    "FileAttachment",
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
    "Friendship",
    "normalize_message_parts",
    "FriendshipRequest",
    "UserRemarkNamesResponse"
]
