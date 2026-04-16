from .api import OopzApiError, OopzRateLimitError
from .auth import OopzAuthError
from .base import OopzError
from .parse import OopzParseError
from .transport import OopzConnectionError, OopzTransportError

__all__ = [
    "OopzApiError",
    "OopzAuthError",
    "OopzConnectionError",
    "OopzError",
    "OopzParseError",
    "OopzRateLimitError",
    "OopzTransportError",
]
