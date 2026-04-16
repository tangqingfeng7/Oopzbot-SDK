from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from oopz_sdk.config.settings import OopzConfig


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
    message: Any = None

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
        if self.message is None:
            raise RuntimeError("该上下文没有可以回复的消息, 无法 reply()")

        area = self._get_message_field(self.message, "area") or self.config.default_area
        channel = self._get_message_field(self.message, "channel") or self.config.default_channel
        reference_message_id = (
            self._get_message_field(self.message, "message_id")
            or self._get_message_field(self.message, "messageId")
            or self._get_message_field(self.message, "id")
        )

        return self.bot.messages.send_message(
            text=text,
            area=area,
            channel=channel,
            referenceMessageId=reference_message_id,
            **kwargs,
        )

    async def send(self, text: str, **kwargs):
        """
        在上下文中发送消息
        """
        return self.bot.messages.send_message(text=text, **kwargs)

    async def recall(self, **kwargs):
        """
        撤回当前上下文中的消息。
        """
        if self.message is None:
            raise RuntimeError("当前上下文中没有 message，无法 recall()")

        message_id = (
            self._get_message_field(self.message, "message_id")
            or self._get_message_field(self.message, "messageId")
            or self._get_message_field(self.message, "id")
        )
        if not message_id:
            raise RuntimeError("当前 message 中没有可用的 message_id")

        area = self._get_message_field(self.message, "area") or self.config.default_area
        channel = self._get_message_field(self.message, "channel") or self.config.default_channel

        return self.bot.messages.recall_message(
            message_id=message_id,
            area=area,
            channel=channel,
            **kwargs,
        )
