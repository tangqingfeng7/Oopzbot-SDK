"""Modern Oopz SDK package layout."""

try:
    from .services.media import UploadMixin, get_image_info
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class UploadMixin:  # type: ignore[override]
        """Fallback mixin when optional media dependencies are unavailable."""

    def get_image_info(*args, **kwargs):
        raise ModuleNotFoundError("Pillow is required for image helpers")

from .auth import Signer
from .client.rest import OopzRESTClient
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
from .services.message import Message
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

OopzSender = Message
OopzClient = OopzWSClient

__all__ = [
    "AutoRecallConfig",
    "DEFAULT_HEADERS",
    "EVENT_AUTH",
    "EVENT_CHAT_MESSAGE",
    "EVENT_HEARTBEAT",
    "EVENT_SERVER_ID",
    "HeartbeatConfig",
    "Message",
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
    "ProxyConfig",
    "RetryConfig",
    "Signer",
    "UploadMixin",
    "__version__",
    "get_image_info",
]
