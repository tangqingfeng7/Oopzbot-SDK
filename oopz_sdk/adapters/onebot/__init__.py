from __future__ import annotations

from .install import install_onebot, install_onebot_v11, install_onebot_v12
from .v11 import OneBotV11Adapter, OneBotV11Server, OneBotV11ServerConfig
from .v12 import OneBotV12Adapter, OneBotV12Server, OneBotV12ServerConfig

__all__ = [
    "install_onebot",
    "install_onebot_v11",
    "install_onebot_v12",
    "OneBotV11Adapter",
    "OneBotV11Server",
    "OneBotV11ServerConfig",
    "OneBotV12Adapter",
    "OneBotV12Server",
    "OneBotV12ServerConfig",
]
