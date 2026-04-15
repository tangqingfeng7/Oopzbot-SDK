from .rest import OopzRESTClient
try:
    from .bot import OopzBot
    from .ws import OopzWSClient
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class _MissingWebSocketDependency:
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("websocket-client is required for WebSocket features")

    OopzBot = _MissingWebSocketDependency
    OopzWSClient = _MissingWebSocketDependency

__all__ = ["OopzBot", "OopzRESTClient", "OopzWSClient"]
