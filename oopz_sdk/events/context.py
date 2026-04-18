from __future__ import annotations

from dataclasses import dataclass
import inspect
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
            raise RuntimeError("当前上下文中没有 message，无法 reply()")
        if self.event.is_private:
            return await self.bot.messages.send_private_message(
                *text,
                channel=self.event.message.channel,
                target=self.event.message.person,
                reference_message_id=self.event.message.message_id,
                **kwargs,
            )

        return await self.bot.messages.send_message(
            *text,
            area=self.event.message.area,
            channel=self.event.message.channel,
            reference_message_id=self.event.message.message_id,
            **kwargs,
        )

    async def send(self, *texts: str | Segment, **kwargs):
        """
        在上下文中发送消息
        """
        if not isinstance(self.event, MessageEvent):
            raise RuntimeError("当前上下文中没有 message，无法 send()")
        if self.event.is_private:
            return await self.bot.messages.send_private_message(
                *texts,
                channel=self.event.message.channel,
                target=self.event.message.person,
                **kwargs,
            )

        return await self.bot.messages.send_message(
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
            raise RuntimeError("当前上下文中没有 message，无法 recall()")
        if self.event.is_private:
            # 撤回私信消息暂时未实现
            return None
        return await self.bot.messages.recall_message(
            message_id=self.event.message.message_id,
            area=self.event.message.area,
            channel=self.event.message.channel,
            **kwargs,
        )

    # async def send(self, *texts: str | Segment, **kwargs):
    #     if texts and all(isinstance(part, str) for part in texts):
    #         text = "".join(texts)
    #         if self.message is None:
    #             return await self._await_if_needed(
    #                 self.bot.messages.send_message(
    #                     text=text,
    #                     **kwargs,
    #                 )
    #             )
    #
    #         area = kwargs.pop("area", self._get_message_field(self.message, "area"))
    #         channel = kwargs.pop("channel", self._get_message_field(self.message, "channel"))
    #         return await self._await_if_needed(
    #             self.bot.messages.send_message(
    #                 text=text,
    #                 area=area,
    #                 channel=channel,
    #                 **kwargs,
    #             )
    #         )
    #
    #     if self.message is None:
    #         return await self._await_if_needed(
    #             self.bot.messages.send_message(
    #                 *texts,
    #                 **kwargs,
    #             )
    #         )
    #
    #     area = kwargs.pop("area", self._get_message_field(self.message, "area"))
    #     channel = kwargs.pop("channel", self._get_message_field(self.message, "channel"))
    #     return await self._await_if_needed(
    #         self.bot.messages.send_message(
    #             *texts,
    #             area=area,
    #             channel=channel,
    #             **kwargs,
    #         )
    #     )
