"""Modern Oopz SDK package layout."""

try:
    from .services.media import UploadMixin, get_image_info
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class UploadMixin:  # type: ignore[override]
        """Fallback mixin when optional media dependencies are unavailable."""

    def get_image_info(*args, **kwargs):
        raise ModuleNotFoundError("Pillow is required for image helpers")

from .auth import Signer
from .client import OopzClient, OopzRESTClient, OopzSender
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
    Area,
    AreaBlock,
    AreaBlocksResult,
    AreaInfo,
    AreaMembersPage,
    Attachment,
    AudioAttachment,
    Channel,
    ChannelGroup,
    ChannelGroupsResult,
    ChannelInfo,
    ChannelMessage,
    ChannelSetting,
    ChatMessageEvent,
    DailySpeechResult,
    ImageAttachment,
    JoinedAreasResult,
    LifecycleEvent,
    Member,
    Message as MessageModel,
    MessageListResult,
    MessageSendResult,
    OperationResult,
    PersonDetail,
    PrivateSessionResult,
    SelfDetail,
    UploadAttachment,
    UploadResult,
    VoiceChannelMember,
    VoiceChannelMembersResult,
)
from .services.message import Message as MessageService
from .version import __version__

try:
    from .client.bot import OopzBot
    from .client.ws import OopzWSClient
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class _MissingWebSocketDependency:
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("websocket-client is required for WebSocket features")

    OopzBot = _MissingWebSocketDependency
    OopzWSClient = _MissingWebSocketDependency

Message = MessageService

__all__ = [
    "AreaInfo",
    "AutoRecallConfig",
    "DEFAULT_HEADERS",
    "EVENT_AUTH",
    "EVENT_CHAT_MESSAGE",
    "EVENT_HEARTBEAT",
    "EVENT_SERVER_ID",
    "HeartbeatConfig",
    "ImageAttachment",
    "JoinedAreasResult",
    "Member",
    "Message",
    "MessageModel",
    "MessageListResult",
    "MessageSendResult",
    "OopzApiError",
    "OopzAuthError",
    "OopzBot",
    "OopzClient",
    "OopzConfig",
    "OopzConnectionError",
    "OopzError",
    "OopzParseError",
    "OopzRESTClient",
    "OopzRateLimitError",
    "OopzSender",
    "OopzTransportError",
    "OopzWSClient",
    "OperationResult",
    "PersonDetail",
    "PrivateSessionResult",
    "ProxyConfig",
    "RetryConfig",
    "SelfDetail",
    "Signer",
    "UploadResult",
    "UploadMixin",
    "VoiceChannelMembersResult",
    "__version__",
    "Area",
    "AreaBlock",
    "AreaBlocksResult",
    "AreaMembersPage",
    "Attachment",
    "AudioAttachment",
    "Channel",
    "ChannelInfo",
    "ChannelMessage",
    "ChannelGroup",
    "ChannelGroupsResult",
    "ChannelSetting",
    "ChatMessageEvent",
    "DailySpeechResult",
    "LifecycleEvent",
    "get_image_info",
    "UploadAttachment",
    "VoiceChannelMember",
]
