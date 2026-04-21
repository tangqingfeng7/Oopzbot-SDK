"""Modern Oopz SDK package layout."""


def _optional_dependency_message(exc: ModuleNotFoundError, *, feature: str) -> str:
    missing_name = getattr(exc, "name", "") or "optional dependency"
    if missing_name.startswith("oopz_sdk"):
        raise exc
    return f"{missing_name} is required for {feature}"

from .api import OopzApiMixin
from .auth import Signer
from .client import  OopzRESTClient
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
    AreaBlock,
    AreaBlocksResult,
    AreaMembersPage,
    ApiResponse,
    Attachment,
    AudioAttachment,
    BaseModel,
    Channel,
    ChannelGroup,
    ChannelGroupsResult,
    ChannelSetting,
    DailySpeechResult,
    Event,
    ImageAttachment,
    JsonList,
    JsonObject,
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
    UploadResult,
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
    "Member",
    "Message",
    "MessageModel",
    "MessageListResult",
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
    "PersonDetail",
    "PrivateSessionResult",
    "ProxyConfig",
    "RetryConfig",
    "SelfDetail",
    "Signer",
    "UploadResult",
    "VoiceChannelMembersResult",
    "__version__",
    "JoinedAreaInfo",
    "AreaBlock",
    "AreaBlocksResult",
    "AreaMembersPage",
    "ApiResponse",
    "Attachment",
    "AudioAttachment",
    "BaseModel",
    "Channel",
    "ChannelGroup",
    "ChannelGroupsResult",
    "ChannelSetting",
    "DailySpeechResult",
    "ensure_http_ok",
    "ensure_success_payload",
    "error_message_from_payload",
    "Event",
    "is_success_payload",
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
]
