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
from .services.message import Message as MessageService

from .version import __version__

from .client.bot import OopzBot
from .client.ws import OopzWSClient

Message = MessageService

__all__ = [
    "AutoRecallConfig",
    "DEFAULT_HEADERS",
    "EVENT_AUTH",
    "EVENT_CHAT_MESSAGE",
    "EVENT_HEARTBEAT",
    "EVENT_SERVER_ID",
    "HeartbeatConfig",
    "ImageAttachment",
    "Message",
    "MessageModel",
    "MessageSendResult",
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
    "VoiceChannelMembersResult",
    "__version__",
    "JoinedAreaInfo",
    "AreaMembersPage",
    "Attachment",
    "ChannelSetting",
    "Event",
    "JsonList",
    "JsonObject",
    "MessageEvent",
]
