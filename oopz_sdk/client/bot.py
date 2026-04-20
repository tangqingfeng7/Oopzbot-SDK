from __future__ import annotations

import json
import logging
from typing import Any

from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.events.context import EventContext
from oopz_sdk.events.dispatcher import EventDispatcher
from oopz_sdk.events.parser import EventParser
from oopz_sdk.events.registry import EventRegistry

from .rest import OopzRESTClient
from .ws import OopzWSClient
from ..models import MessageEvent, Message

logger = logging.getLogger("oopz_sdk.client.bot")


class OopzBot:
    """
    高层 Bot 入口。

    职责：
    - 统一管理 REST / WS
    - 统一事件注册入口
    - 统一事件调度
    """

    def __init__(
        self,
        config,
        *,
        on_message=None,
        on_ready=None,
        on_error=None,
        on_close=None,
        on_reconnect=None,
        on_raw_event=None,
    ):
        self.config = config
        self.registry = EventRegistry()
        self.dispatcher = EventDispatcher(self.registry)
        self.parser = EventParser()
        self.rest = OopzRESTClient(self, config)
        self.messages = self.rest.messages
        self.media = self.rest.media
        self.areas = self.rest.areas
        self.channels = self.rest.channels
        self.members = self.rest.members
        self.moderation = self.rest.moderation

        # WS 客户端只负责底层连接和回调
        self.ws = OopzWSClient(
            config=config,
            on_message=self._handle_ws_message,
            on_open=self._handle_open,
            on_error=self._handle_error,
            on_close=self._handle_close,
            on_reconnect=self._handle_reconnect,
        )

        # 函数式事件注册
        if on_message is not None:
            self.registry.on("message", on_message)
        if on_ready is not None:
            self.registry.on("ready", on_ready)
        if on_error is not None:
            self.registry.on("error", on_error)
        if on_close is not None:
            self.registry.on("close", on_close)
        if on_reconnect is not None:
            self.registry.on("reconnect", on_reconnect)
        if on_raw_event is not None:
            self.registry.on("raw_event", on_raw_event)

    # -------------------------
    # 事件注册 API
    # -------------------------
    def _hook(self, event_name: str):
        return self.registry.on(event_name)

    def on(self, event_name: str):
        return self._hook(event_name)

    def event(self, name: str):
        return self.on(name)

    @property
    def on_ready(self):
        return self.on("ready")

    @property
    def on_message(self):
        return self.on("message")

    @property
    def on_message_edit(self):
        return self.on("message.edit")

    @property
    def on_private_message(self):
        return self.registry.on("message.private")

    @property
    def on_private_message_edit(self):
        return self.registry.on("message.private.edit")

    @property
    def on_recall(self):
        return self.registry.on("recall")

    @property
    def on_error(self):
        return self.on("error")

    @property
    def on_close(self):
        return self.on("close")

    @property
    def on_reconnect(self):
        return self.on("reconnect")

    @property
    def on_raw_event(self):
        return self.on("raw_event")

    # -------------------------
    # 生命周期
    # -------------------------

    async def start(self):
        await self.rest.start()
        await self.ws.start()

    async def run(self):
        await self.start()

    async def stop(self):
        await self.ws.stop()
        await self.rest.close()

    # -------------------------
    # 高层便捷方法
    # -------------------------
    async def send(
        self, text: str, area: str | None = None, channel: str | None = None, **kwargs
    ):
        return await self.messages.send_message(
            text, area=area, channel=channel, **kwargs
        )

    async def recall(
        self,
        message_id: str,
        area: str | None = None,
        channel: str | None = None,
        **kwargs,
    ):
        return await self.messages.recall_message(
            message_id, area=area, channel=channel, **kwargs
        )

    async def reply(
        self,
        text: str,
        area: str | None = None,
        channel: str | None = None,
        reference_message_id: str = "",
        **kwargs,
    ):
        """
        对某条消息进行回复
        """
        return await self.messages.send_message(
            text,
            area=area,
            channel=channel,
            reference_message_id=reference_message_id,
            **kwargs,
        )

    # -------------------------
    # 内部工具
    # -------------------------
    @staticmethod
    def _get_message_field(message: Any, name: str, default=None):
        if message is None:
            return default
        if isinstance(message, dict):
            return message.get(name, default)
        return getattr(message, name, default)

    def _make_context(self, *, event=None, trace_id: str = "") -> EventContext:
        return EventContext(
            bot=self,
            config=self.config,
            event=event
        )

    # -------------------------
    # WS 回调入口
    # -------------------------
    async def _handle_ws_message(self, raw: str) -> None:
        try:
            event = self.parser.parse(raw)
            ctx = self._make_context(event=event)

            if isinstance(event, MessageEvent) and self._should_ignore_self_message(event.message):
                return

            await self.dispatcher.dispatch("raw_event", event, ctx)
            await self.dispatcher.dispatch(event.name, event, ctx)

        except Exception as exc:
            logger.exception("Event handling failed: %s", exc)
            err_ctx = self._make_context(event=exc)
            try:
                await self.dispatcher.dispatch("error", exc, err_ctx)
                setattr(exc, "_oopz_error_dispatched", True)
            except Exception as e:
                logger.exception("Error handler execution failed", e)
            raise

    async def _handle_open(self) -> None:
        ctx = self._make_context()
        await self.dispatcher.dispatch("ready", None, ctx)

    async def _handle_error(self, error) -> None:
        ctx = self._make_context(event=error)
        await self.dispatcher.dispatch("error", error, ctx)

    async def _handle_close(self, code, reason) -> None:
        payload = {"code": code, "reason": reason}
        ctx = self._make_context(event=payload)
        await self.dispatcher.dispatch("close", payload, ctx)

    async def _handle_reconnect(self) -> None:
        ctx = self._make_context()
        await self.dispatcher.dispatch("reconnect", None, ctx)

    def _should_ignore_self_message(self, message: Message) -> bool:
        """
        判断是否应该忽略自己发送的消息。如果设置不忽略消息, 会导致在 on_message 中收到自己发送的消息引发死循环。
        """
        if not self.config.ignore_self_messages:
            return False
        return message.person == self.config.person_uid
