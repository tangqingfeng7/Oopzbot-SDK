from .rest import OopzRESTClient
from oopz_sdk.compat.sender import OopzSender
try:
    from .bot import OopzBot
    from .ws import OopzWSClient
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class _MissingWebSocketDependency:
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("websocket-client is required for WebSocket features")

    OopzBot = _MissingWebSocketDependency
    OopzWSClient = _MissingWebSocketDependency

__all__ = ["OopzBot",  "OopzRESTClient", "OopzSender", "OopzWSClient"]
