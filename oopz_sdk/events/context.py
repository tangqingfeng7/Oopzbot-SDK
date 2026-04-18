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
    - handler 中可以通过 ctx.bot 访问完整 Bot
    - handler 中可以直接 ctx.reply(...)
    """
    bot: Any
    config: OopzConfig
    event: Any = None

    @staticmethod
    def _get_message_field(message: Any, name: str, default=None):
        if message is None:
            return default
        if isinstance(message, dict):
            return message.get(name, default)
        return getattr(message, name, default)

    async def reply(self, text: str, **kwargs):
        """
        回复当前上下文中的消息
        """
        if not isinstance(self.event, MessageEvent):
            raise RuntimeError("当前上下文中没有 message，无法 send()")

        area = self._get_message_field(self.event.message, "area")
        channel = self._get_message_field(self.event.message, "channel")
        reference_message_id = (
            self._get_message_field(self.event.message, "message_id")
            or self._get_message_field(self.event.message, "messageId")
            or self._get_message_field(self.event.message, "id")
        )

        return self.bot.messages.send_message(
            text=text,
            area=area,
            channel=channel,
            referenceMessageId=reference_message_id,
            **kwargs,
        )

    async def send(self, *texts: str | Segment, **kwargs):
        """
        在上下文中发送消息
        """
        if not isinstance(self.event, MessageEvent):
            raise RuntimeError("当前上下文中没有 message，无法 send()")
        if self.event.is_private:
            return self.bot.messages.send_private_message(
                *texts,
                channel=self.event.message.channel,
                target=self.event.message.person,
                **kwargs,
            )

        return self.bot.messages.send_message(
            *texts,
            area=self.event.message.area,
            channel=self.event.message.channel,
            **kwargs,
        )
        # area = self._get_message_field(self.message, "area")
        # channel = self._get_message_field(self.message, "channel")
        # return self.bot.messages.send_message(*texts, area=area, channel=channel, **kwargs)

    async def recall(self, **kwargs):
        """
        撤回当前上下文中的消息。
        """
        if not isinstance(self.event, MessageEvent):
            raise RuntimeError("当前上下文中没有 message，无法 send()")

        message_id = (
            self._get_message_field(self.event.message, "message_id")
            or self._get_message_field(self.event.message, "messageId")
            or self._get_message_field(self.event.message, "id")
        )
        if not message_id:
            raise RuntimeError("当前 message 中没有可用的 message_id")

        area = self._get_message_field(self.event.message, "area")
        channel = self._get_message_field(self.event.message, "channel")

        return self.bot.messages.recall_message(
            message_id=message_id,
            area=area,
            channel=channel,
            **kwargs,
        )

    # async def send(self, *texts: str | Segment, **kwargs):
    #     if texts and all(isinstance(part, str) for part in texts):
    #         text = "".join(texts)
    #         if self.message is None:
    #             return self.bot.messages.send_message(text=text, **kwargs)
    #
    #         area = kwargs.pop("area", self._get_message_field(self.message, "area"))
    #         channel = kwargs.pop("channel", self._get_message_field(self.message, "channel"))
    #         return self.bot.messages.send_message(text=text, area=area, channel=channel, **kwargs)
    #
    #     if self.message is None:
    #         return self.bot.messages.send_message(*texts, **kwargs)
    #
    #     area = kwargs.pop("area", self._get_message_field(self.message, "area"))
    #     channel = kwargs.pop("channel", self._get_message_field(self.message, "channel"))
    #     return self.bot.messages.send_message(*texts, area=area, channel=channel, **kwargs)
