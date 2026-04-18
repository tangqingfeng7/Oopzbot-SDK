from .rest import OopzRESTClient


def _optional_dependency_message(exc: ModuleNotFoundError, *, feature: str) -> str:
    missing_name = getattr(exc, "name", "") or "optional dependency"
    if missing_name.startswith("oopz_sdk"):
        raise exc
    return f"{missing_name} is required for {feature}"


try:
    from .bot import OopzBot
    from .ws import OopzWSClient
except ModuleNotFoundError as exc:  # pragma: no cover - optional runtime dependency
    _missing_dependency_message = _optional_dependency_message(exc, feature="WebSocket features")

    class _MissingWebSocketDependency:
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError(_missing_dependency_message)

    OopzBot = _MissingWebSocketDependency
    OopzWSClient = _MissingWebSocketDependency

__all__ = ["OopzBot", "OopzRESTClient", "OopzWSClient"]
