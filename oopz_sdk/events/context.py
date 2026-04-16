from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.models import Message


@dataclass(slots=True)
class EventContext:
    """
    事件上下文。

    目标：
    - handler 中可以通过 ctx.bot 访问完整 Bot
    - handler 中可以直接 ctx.reply(...)
    - 兼容 message 为 dict 或 model
    """
    bot: Any
    config: OopzConfig
    event: Any = None
    message: Message = None


    async def reply(self, text: str, **kwargs):
        """
        回复当前上下文中的消息
        """
        if self.message is None:
            raise RuntimeError("该上下文没有可以回复的消息, 无法 reply()")

        return self.bot.messages.send_message(
            text=text,
            area=self.message.area,
            channel=self.message.channel,
            referenceMessageId=self.message.message_id,
            **kwargs,
        )

    async def send(self, text: str, **kwargs):
        """
        在上下文中发送消息
        """
        return self.bot.messages.send_message(
            text=text,
            area= self.message.area,
            channel=self.message.channel,
            **kwargs
        )

    async def recall(self, **kwargs):
        """
        撤回当前上下文中的消息。
        """
        if self.message is None:
            raise RuntimeError("当前上下文中没有 message，无法 recall_current()")

        return self.bot.messages.recall_message(
            message_id=self.message.message_id,
            area=self.message.area,
            channel=self.message.channel,
            **kwargs,
        )