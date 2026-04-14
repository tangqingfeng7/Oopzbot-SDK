"""Oopz SDK -- Oopz 平台通信核心库。

用法::

    from oopz import OopzConfig, OopzClient, OopzSender

    config = OopzConfig(
        device_id="...",
        person_uid="...",
        jwt_token="...",
        private_key="-----BEGIN RSA PRIVATE KEY-----\\n...",
        default_area="...",
        default_channel="...",
    )

    sender = OopzSender(config)
    sender.send_message("Hello!")

    client = OopzClient(config, on_chat_message=lambda msg: print(msg))
    client.start()
"""

from .config import DEFAULT_HEADERS, OopzConfig
from .client import (
    EVENT_AUTH,
    EVENT_CHAT_MESSAGE,
    EVENT_HEARTBEAT,
    EVENT_SERVER_ID,
    OopzClient,
)
from .models import (
    AreaInfo,
    AreaMembersPage,
    ChannelGroup,
    ChannelInfo,
    ChatMessageEvent,
    LifecycleEvent,
    MessageSendResult,
    OperationResult,
    PrivateSessionResult,
    UploadAttachment,
    UploadResult,
)
from .exceptions import (
    OopzApiError,
    OopzAuthError,
    OopzConnectionError,
    OopzError,
    OopzRateLimitError,
)
from .sender import OopzSender
from .signer import Signer
from .upload import UploadMixin, get_image_info

__all__ = [
    "AreaInfo",
    "AreaMembersPage",
    "ChannelGroup",
    "ChannelInfo",
    "ChatMessageEvent",
    "DEFAULT_HEADERS",
    "EVENT_AUTH",
    "EVENT_CHAT_MESSAGE",
    "EVENT_HEARTBEAT",
    "EVENT_SERVER_ID",
    "LifecycleEvent",
    "MessageSendResult",
    "OopzApiError",
    "OopzAuthError",
    "OopzClient",
    "OopzConfig",
    "OopzConnectionError",
    "OopzError",
    "OopzRateLimitError",
    "OopzSender",
    "OperationResult",
    "PrivateSessionResult",
    "Signer",
    "UploadAttachment",
    "UploadResult",
    "UploadMixin",
    "get_image_info",
]

__version__ = "0.3.0"
