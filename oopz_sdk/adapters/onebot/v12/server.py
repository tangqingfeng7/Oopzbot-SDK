from __future__ import annotations

from dataclasses import dataclass

from oopz_sdk.adapters.onebot.server import OneBotServer, OneBotServerConfig


@dataclass(slots=True)
class OneBotV12ServerConfig(OneBotServerConfig):
    """OneBot v12 server 配置。保留旧导入路径兼容。"""

    version: str = "v12"


class OneBotV12Server(OneBotServer):
    """OneBot v12 server。实际通信逻辑在 adapters.onebot.server.OneBotServer。"""
