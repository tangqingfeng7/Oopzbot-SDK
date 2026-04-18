"""Modern Oopz SDK package layout."""

try:
    from .services.media import UploadMixin, get_image_info
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class UploadMixin:  # type: ignore[override]
        """Fallback mixin when optional media dependencies are unavailable."""

    def get_image_info(*args, **kwargs):
        raise ModuleNotFoundError("Pillow is required for image helpers")

from .api import OopzApiMixin
from .auth import Signer
from .client import OopzClient, OopzRESTClient
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
    ApiResponse,
    Attachment,
    AudioAttachment,
    BaseModel,
    Channel,
    ChannelGroup,
    ChannelGroupsResult,
    ChannelInfo,
    ChannelMessage,
    ChannelSetting,
    ChatMessageEvent,
    DailySpeechResult,
    Event,
    ImageAttachment,
    JsonList,
    JsonObject,
    JoinedAreasResult,
    LifecycleEvent,
    Member,
    Message as MessageModel,
    MessageEvent,
    MessageListResult,
    MessageSendResult,
    OperationResult,
    PersonDetail,
    PersonInfo,
    PrivateSessionResult,
    SelfDetail,
    UploadAttachment,
    UploadResult,
    VoiceChannelMember,
    VoiceChannelMembersResult,
)
from .services.message import Message as MessageService
from .response import (
    SUCCESS_CODES,
    ensure_http_ok,
    ensure_success_payload,
    error_message_from_payload,
    is_success_payload,
    raise_api_error,
    raise_connection_error,
    raise_payload_error,
    require_dict_data,
    require_list_data,
    response_preview,
    retry_delay_from_exception,
    safe_json,
    safe_json_object,
)
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
    "ApiResponse",
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
    "ensure_http_ok",
    "ensure_success_payload",
    "error_message_from_payload",
    "Event",
    "is_success_payload",
    "LifecycleEvent",
    "JsonList",
    "JsonObject",
    "MessageEvent",
    "OopzApiMixin",
    "PersonInfo",
    "raise_api_error",
    "raise_connection_error",
    "raise_payload_error",
    "require_dict_data",
    "require_list_data",
    "response_preview",
    "retry_delay_from_exception",
    "safe_json",
    "safe_json_object",
    "SUCCESS_CODES",
    "get_image_info",
    "UploadAttachment",
    "VoiceChannelMember",
]
