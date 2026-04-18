from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any, Optional

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzRateLimitError
from oopz_sdk.services.area import AreaService
from oopz_sdk.services.channel import Channel
from oopz_sdk.services.media import Media
from oopz_sdk.services.member import Member
from oopz_sdk.services.message import Message
from oopz_sdk.services.moderation import Moderation
from oopz_sdk.transport.http import HttpTransport

_SUCCESS_CODES = (0, "0", 200, "200", "success")


class OopzRESTClient:
    def __init__(self, config_or_bot, config: OopzConfig | None = None):
        if config is None:
            bot = None
            config = config_or_bot
        else:
            bot = config_or_bot
        self._bot = bot
        self._config = config
        self.config = config
        self.signer = Signer(config)
        self.transport = HttpTransport(config, self.signer)
        self.messages = Message(bot, config, self.transport, self.signer)
        self.media = Media(bot, config, self.transport, self.signer)
        self.areas = AreaService(bot, config, self.transport, self.signer)
        self.channels = Channel(bot, config, self.transport, self.signer)
        self.members = Member(bot, config, self.transport, self.signer)
        self.moderation = Moderation(bot, config, self.transport, self.signer)

    async def start(self) -> None:
        await self.transport.start()

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self) -> "OopzRESTClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()