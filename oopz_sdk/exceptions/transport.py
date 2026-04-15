from .base import OopzError


class OopzTransportError(OopzError):
    """Transport failure."""


class OopzConnectionError(OopzTransportError):
    """Connection failure."""
