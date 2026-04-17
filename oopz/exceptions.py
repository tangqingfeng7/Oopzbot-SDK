"""Legacy exception exports backed by oopz_sdk."""

from oopz_sdk.exceptions import (
    OopzApiError,
    OopzAuthError,
    OopzConnectionError,
    OopzError,
    OopzParseError,
    OopzRateLimitError,
    OopzTransportError,
)

__all__ = [
    "OopzApiError",
    "OopzAuthError",
    "OopzConnectionError",
    "OopzError",
    "OopzParseError",
    "OopzRateLimitError",
    "OopzTransportError",
]
