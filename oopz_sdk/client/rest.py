from __future__ import annotations

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.services.area import AreaService
from oopz_sdk.services.channel import Channel
from oopz_sdk.services.media import Media
from oopz_sdk.services.member import Member
from oopz_sdk.services.message import Message
from oopz_sdk.services.moderation import Moderation
from oopz_sdk.services.privatemessage import PrivateMessage
from oopz_sdk.transport.http import HttpTransport


class OopzRESTClient:
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
        self.messages = Message(bot, config, self.transport, self.signer)
        self.private = PrivateMessage(bot, config, self.transport, self.signer)
        self.media = Media(bot, config, self.transport, self.signer)
        self.areas = AreaService(bot, config, self.transport, self.signer)
        self.channels = Channel(bot, config, self.transport, self.signer)
        self.members = Member(bot, config, self.transport, self.signer)
        self.moderation = Moderation(bot, config, self.transport, self.signer)

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> "OopzRESTClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
