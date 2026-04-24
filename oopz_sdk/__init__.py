"""Modern Oopz SDK package layout."""

from .auth import Signer
from .client import OopzRESTClient
from .config import (
    DEFAULT_HEADERS,
    EVENT_AUTH,
    EVENT_CHAT_MESSAGE,
    EVENT_HEARTBEAT,
    EVENT_SERVER_ID,
    AutoRecallConfig,
    HeartbeatConfig,
    OopzConfig,
    ProxyConfig,
    RetryConfig,
)
from .exceptions import (
    OopzApiError,
    OopzAuthError,
    OopzConnectionError,
    OopzError,
    OopzParseError,
    OopzRateLimitError,
    OopzTransportError,
)
from .models import (
    JoinedAreaInfo,
    AreaMembersPage,
    Attachment,
    ChannelSetting,
    Event,
    ImageAttachment,
    JsonList,
    JsonObject,
    Message as MessageModel,
    MessageEvent,
    MessageSendResult,
    OperationResult,
    VoiceChannelMembersResult,
)
from .services.area import AreaService
from .services.channel import Channel
from .services.media import Media
from .services.member import Member
from .services.message import Message as MessageService
from .services.moderation import Moderation
from .services.voice import Voice

from .version import __version__

from .client.bot import OopzBot
from .client.ws import OopzWSClient

Message = MessageService

__all__ = [
    "AreaMembersPage",
    "AreaService",
    "Attachment",
    "AutoRecallConfig",
    "Channel",
    "ChannelSetting",
    "DEFAULT_HEADERS",
    "EVENT_AUTH",
    "EVENT_CHAT_MESSAGE",
    "EVENT_HEARTBEAT",
    "EVENT_SERVER_ID",
    "Event",
    "HeartbeatConfig",
    "ImageAttachment",
    "JoinedAreaInfo",
    "JsonList",
    "JsonObject",
    "Media",
    "Member",
    "Message",
    "MessageEvent",
    "MessageModel",
    "MessageSendResult",
    "Moderation",
    "OopzApiError",
    "OopzAuthError",
    "OopzBot",
    "OopzConfig",
    "OopzConnectionError",
    "OopzError",
    "OopzParseError",
    "OopzRESTClient",
    "OopzRateLimitError",
    "OopzTransportError",
    "OopzWSClient",
    "OperationResult",
    "ProxyConfig",
    "RetryConfig",
    "Signer",
    "Voice",
    "VoiceChannelMembersResult",
    "__version__",
]
