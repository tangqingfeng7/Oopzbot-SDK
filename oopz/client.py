"""Legacy WebSocket client exports backed by oopz_sdk."""

from oopz_sdk.client import OopzClient
from oopz_sdk.config import EVENT_AUTH, EVENT_CHAT_MESSAGE, EVENT_HEARTBEAT, EVENT_SERVER_ID

__all__ = [
    "EVENT_AUTH",
    "EVENT_CHAT_MESSAGE",
    "EVENT_HEARTBEAT",
    "EVENT_SERVER_ID",
    "OopzClient",
]
