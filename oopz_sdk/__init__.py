"""Modern Oopz SDK package layout."""


def _optional_dependency_message(exc: ModuleNotFoundError, *, feature: str) -> str:
    missing_name = getattr(exc, "name", "") or "optional dependency"
    if missing_name.startswith("oopz_sdk"):
        raise exc
    return f"{missing_name} is required for {feature}"

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
    AudioAttachment,
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

try:
    from .client.bot import OopzBot
    from .client.ws import OopzWSClient
except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency
    _missing_ws_dependency_message = _optional_dependency_message(exc, feature="WebSocket features")

    class _MissingWebSocketDependency:
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError(_missing_ws_dependency_message)

    OopzBot = _MissingWebSocketDependency
    OopzWSClient = _MissingWebSocketDependency

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
    "AudioAttachment",
    "ChannelSetting",
    "Event",
    "JsonList",
    "JsonObject",
    "MessageEvent",
]
