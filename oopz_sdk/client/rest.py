from __future__ import annotations

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.services.area import AreaService
from oopz_sdk.services.channel import Channel
from oopz_sdk.services.media import Media
from oopz_sdk.services.person import Person
from oopz_sdk.services.message import Message
from oopz_sdk.services.moderation import Moderation
from oopz_sdk.transport.http import HttpTransport


class OopzRESTClient:
    """REST 总入口，只负责共享连接和挂载各分类 service。"""

    def __init__(self, config: OopzConfig, *, bot=None):
        # `bot` 是外部可选入参：当被 OopzBot 构造时会把自己传进来；
        # 纯 REST 场景下调用方不传，owner 就是 OopzRESTClient 自己。
        # 无论哪种情况，owner 都持有 messages/media/... 属性，可以供 service 间互相取用。
        if not isinstance(config, OopzConfig):
            # v0.5 起构造签名从 `(config_or_bot, config=None)` 改为 `(config, *, bot=None)`。
            # 旧代码如果仍按 `OopzRESTClient(bot, config)` 调用，会把 bot 当成 config 传进来，
            # 然后在 `Signer(config)` 里炸出看不懂的 PEM 报错，这里直接拦下给出明确提示。
            raise TypeError(
                "OopzRESTClient(config, *, bot=None): 第一个位置参数必须是 OopzConfig，"
                f"收到的是 {type(config).__name__}。"
                "如果你在 v0.5 之前用过 OopzRESTClient(bot, config) 的老签名，请改成 "
                "OopzRESTClient(config, bot=bot)。"
            )
        self.config = config
        self.signer = Signer(config)
        self.transport = HttpTransport(config, self.signer)
        owner = bot if bot is not None else self
        self.messages = Message(owner, config, self.transport, self.signer)
        self.media = Media(owner, config, self.transport, self.signer)
        self.areas = AreaService(owner, config, self.transport, self.signer)
        self.channels = Channel(owner, config, self.transport, self.signer)
        self.person = Person(owner, config, self.transport, self.signer)
        self.moderation = Moderation(owner, config, self.transport, self.signer)

    async def start(self) -> None:
        await self.transport.start()

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self) -> "OopzRESTClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
