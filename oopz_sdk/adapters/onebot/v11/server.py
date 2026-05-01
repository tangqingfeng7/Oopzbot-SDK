from __future__ import annotations

from dataclasses import dataclass

from oopz_sdk.adapters.onebot.server import OneBotServer, OneBotServerConfig


@dataclass(slots=True)
class OneBotV11ServerConfig(OneBotServerConfig):
    version: str = "v11"


class OneBotV11Server(OneBotServer):
    pass
