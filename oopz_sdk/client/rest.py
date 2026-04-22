from __future__ import annotations

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.services.area import AreaService
from oopz_sdk.services.channel import Channel
from oopz_sdk.services.media import Media
from oopz_sdk.services.member import Member
from oopz_sdk.services.message import Message
from oopz_sdk.services.moderation import Moderation
from oopz_sdk.transport.http import HttpTransport


class OopzRESTClient:
    """REST 总入口，只负责共享连接和挂载各分类 service。"""

    def __init__(self, config_or_bot, config: OopzConfig | None = None):
        if config is None:
            bot = None
            config = config_or_bot
        else:
            bot = config_or_bot
        self._bot = bot
        self.config = config
        self.signer = Signer(config)
        self.transport = HttpTransport(config, self.signer)
        service_owner = bot or self
        self.messages = Message(service_owner, config, self.transport, self.signer)
        self.media = Media(service_owner, config, self.transport, self.signer)
        self.areas = AreaService(service_owner, config, self.transport, self.signer)
        self.channels = Channel(service_owner, config, self.transport, self.signer)
        self.members = Member(service_owner, config, self.transport, self.signer)
        self.moderation = Moderation(service_owner, config, self.transport, self.signer)

    async def start(self) -> None:
        await self.transport.start()

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self) -> "OopzRESTClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
