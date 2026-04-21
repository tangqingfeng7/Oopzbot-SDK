from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.models import MessageEvent
from oopz_sdk.models.segment import Segment


@dataclass(slots=True)
class EventContext:
    """
    事件上下文。

    目标：
    - handler 里可以通过 ctx.bot 访问完整 Bot
    - handler 里可以直接 ctx.reply(...)
    """

    bot: Any
    config: OopzConfig
    event: Any = None

    async def reply(self, *text: str, **kwargs):
        """
        回复当前上下文中的消息。
        """
        if not isinstance(self.event, MessageEvent):
            raise RuntimeError("reply() requires a message event context")
        channel = kwargs.pop("channel", self.event.message.channel)
        if self.event.is_private:
            target = kwargs.pop("target", self.event.message.sender_id)
            return await self.bot.messages.send_private_message(
                *text,
                channel=channel,
                target=target,
                reference_message_id=self.event.message.message_id,
                **kwargs,
            )

        area = kwargs.pop("area", self.event.message.area)
        return await self.bot.messages.send_message(
            *text,
            area=area,
            channel=channel,
            reference_message_id=self.event.message.message_id,
            **kwargs,
        )

    async def send(self, *texts: str | Segment, **kwargs):
        """
        在上下文中发送消息
        """
        if not isinstance(self.event, MessageEvent):
            raise RuntimeError("send() requires a message event context")
        channel = kwargs.pop("channel", self.event.message.channel)
        if self.event.is_private:
            target = kwargs.pop("target", self.event.message.sender_id)
            return await self.bot.messages.send_private_message(
                *texts,
                channel=channel,
                target=target,
                **kwargs,
            )

        area = kwargs.pop("area", self.event.message.area)
        return await self.bot.messages.send_message(
            *texts,
            area=area,
            channel=channel,
            **kwargs,
        )

    async def recall(self, **kwargs):
        """
        撤回当前上下文中的消息。
        """
        if not isinstance(self.event, MessageEvent):
            raise RuntimeError("recall() requires a message event context")
        if self.event.is_private:
            raise RuntimeError("recall() is not supported for private messages")
        return await self.bot.messages.recall_message(
            message_id=self.event.message.message_id,
            area=self.event.message.area,
            channel=self.event.message.channel,
            **kwargs,
        )
