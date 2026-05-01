from __future__ import annotations

import logging
from typing import Any

import oopz_sdk.services.message as message_service
import oopz_sdk.services.voice as voice_service
from oopz_sdk.events.context import EventContext
from oopz_sdk.events.dispatcher import EventDispatcher
from oopz_sdk.events.parser import EventParser
from oopz_sdk.events.registry import EventRegistry

from .rest import OopzRESTClient
from .ws import CloseInfo, OopzWSClient
from ..models import Message, MessageEvent

logger = logging.getLogger(__name__)


class OopzBot:
    """
    高层 Bot 入口。

    职责：
    - 统一管理 REST / WS
    - 统一事件注册入口
    - 统一事件调度
    - 维护通用 adapter 列表，但不关心具体协议细节

    协议适配器，例如 OneBot v11/v12，应通过 add_adapter() 注册。
    Bot 只负责把 Oopz 事件广播给 adapter，以及统一管理 adapter server 生命周期。
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

        self.rest = OopzRESTClient(config, bot=self)
        self.messages: message_service.Message = self.rest.messages
        self.media = self.rest.media
        self.areas = self.rest.areas
        self.channels = self.rest.channels
        self.person = self.rest.person
        self.members = self.person
        self.moderation = self.rest.moderation
        self.voice: voice_service.Voice = voice_service.Voice(
            self,
            config,
            self.rest.transport,
            self.rest.signer,
        )

        # 通用 adapter 生命周期容器。
        # adapter: 负责协议转换 / action 处理 / event emit。
        # adapter server: 负责 HTTP / WS / webhook / reverse WS 等连接层。
        self.adapters: list[Any] = []
        self._adapter_servers: list[Any] = []

        self._install_configured_adapters()

        # WS 客户端只负责底层连接和回调。
        self.ws = OopzWSClient(
            config=config,
            on_message=self._handle_ws_message,
            on_open=self._handle_open,
            on_error=self._handle_error,
            on_close=self._handle_close,
            on_reconnect=self._handle_reconnect,
        )

        # 函数式事件注册。
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
    # Adapter 注册 API
    # -------------------------
    def add_adapter(self, adapter: Any, *, server: Any | None = None) -> Any:
        """
        注册协议适配器。

        adapter 只需要按需实现：
        - emit_event(event): 接收 Oopz 事件并转换/广播到目标协议。

        server 只需要按需实现：
        - start(): 启动 HTTP / WS / webhook / reverse WS 等连接层。
        - stop(): 停止连接层。

        返回 adapter 本身，方便调用方保留引用：
            onebot = bot.add_adapter(OneBotV12Adapter(bot, ...))
        """
        if adapter not in self.adapters:
            self.adapters.append(adapter)

        if server is not None and server not in self._adapter_servers:
            self._adapter_servers.append(server)

        return adapter

    def add_adapter_server(self, server: Any) -> Any:
        """只注册 adapter server。通常 install 函数内部使用。"""
        if server not in self._adapter_servers:
            self._adapter_servers.append(server)
        return server

    def _install_configured_adapters(self) -> None:
        """
        根据 config 安装内置 adapter。

        这里保持很薄的一层转发，避免 OopzBot 直接 import/构造 v11/v12 的
        Adapter、Server、ServerConfig。以后新增协议时，也应优先放到 adapters/ 下。
        """
        from oopz_sdk.adapters.onebot.install import install_onebot

        install_onebot(self)

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
    def on_private_recall(self):
        return self.registry.on("recall.private")

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
        rest_started = False
        adapter_servers_started = False

        try:
            await self.rest.start()
            rest_started = True

            await self._start_adapter_servers()
            adapter_servers_started = bool(self._adapter_servers)

            await self.ws.start()

        except BaseException:
            if adapter_servers_started:
                try:
                    await self._stop_adapter_servers()
                except BaseException as close_exc:
                    logger.exception("Failed to stop adapter servers after start failure: %s", close_exc)

            if rest_started:
                await self._close_rest_after_start_failure()

            raise

    async def run(self):
        await self.start()

    async def stop(self):
        stop_error = None
        try:
            await self.ws.stop()
        except BaseException as exc:
            stop_error = exc

        voice_error = None
        try:
            await self.voice.close()
        except BaseException as exc:
            voice_error = exc

        adapter_error = None
        try:
            await self._stop_adapter_servers()
        except BaseException as exc:
            adapter_error = exc

        if stop_error is None and voice_error is None and adapter_error is None:
            await self.rest.close()
            return

        await self._close_rest_after_stop_failure()

        if stop_error is not None:
            raise stop_error
        if voice_error is not None:
            raise voice_error
        raise adapter_error

    # -------------------------
    # 高层便捷方法
    # -------------------------
    async def send(self, text: str, area: str, channel: str, **kwargs):
        return await self.messages.send_message(
            text,
            area=area,
            channel=channel,
            **kwargs,
        )

    async def recall(
        self,
        message_id: str,
        area: str,
        channel: str,
        **kwargs,
    ):
        return await self.messages.recall_message(
            message_id,
            area=area,
            channel=channel,
            **kwargs,
        )

    async def reply(
        self,
        text: str,
        area: str,
        channel: str,
        reference_message_id: str = "",
        **kwargs,
    ):
        """对某条消息进行回复。"""
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
    def _make_context(self, *, event=None) -> EventContext:
        return EventContext(
            bot=self,
            config=self.config,
            event=event,
        )

    async def _close_rest_after_start_failure(self) -> None:
        try:
            await self.rest.close()
        except BaseException as close_exc:
            logger.exception("Failed to close REST client after start failure: %s", close_exc)

    async def _close_rest_after_stop_failure(self) -> None:
        try:
            await self.rest.close()
        except BaseException as close_exc:
            logger.exception("Failed to close REST client after stop failure: %s", close_exc)

    # -------------------------
    # WS 回调入口
    # -------------------------
    async def _handle_ws_message(self, raw: str) -> None:
        try:
            event = self.parser.parse(raw)
            ctx = self._make_context(event=event)

            if isinstance(event, MessageEvent) and self._should_ignore_self_message(event.message):
                return

            await self._emit_adapter_event(event)

            await self.dispatcher.dispatch("raw_event", event, ctx)
            await self.dispatcher.dispatch(event.event_name, event, ctx)

        except Exception as exc:
            logger.exception("Unhandled exception while processing websocket event: %s", exc)
            err_ctx = self._make_context(event=exc)
            await self.dispatcher.dispatch("error", exc, err_ctx)
            setattr(exc, "_oopz_error_dispatched", True)
            raise

    async def _handle_open(self) -> None:
        ctx = self._make_context()
        await self.dispatcher.dispatch("ready", None, ctx)

    async def _handle_error(self, error) -> None:
        ctx = self._make_context(event=error)
        await self.dispatcher.dispatch("error", error, ctx)

    async def _handle_close(self, close_info: CloseInfo) -> None:
        payload = {
            "code": close_info.code,
            "reason": close_info.reason,
            "error": close_info.error,
            "reconnecting": close_info.reconnecting,
        }
        ctx = self._make_context(event=payload)
        await self.dispatcher.dispatch("close", payload, ctx)

    async def _handle_reconnect(self) -> None:
        ctx = self._make_context()
        await self.dispatcher.dispatch("reconnect", None, ctx)

    def _should_ignore_self_message(self, message: Message) -> bool:
        """
        判断是否应该忽略自己发送的消息。
        如果设置不忽略消息，会导致在 on_message 中收到自己发送的消息并可能引发死循环。
        """
        if not self.config.ignore_self_messages:
            return False
        return message.sender_id == self.config.person_uid

    async def _emit_adapter_event(self, event: Any) -> None:
        """把 Oopz 事件广播给所有已注册 adapter。"""
        for adapter in list(self.adapters):
            emit_event = getattr(adapter, "emit_event", None)
            if emit_event is None:
                continue
            await emit_event(event)

    async def _start_adapter_servers(self) -> None:
        for server in list(self._adapter_servers):
            start = getattr(server, "start", None)
            if start is None:
                continue
            await start()

    async def _stop_adapter_servers(self) -> None:
        first_error = None

        for server in reversed(list(self._adapter_servers)):
            stop = getattr(server, "stop", None)
            if stop is None:
                continue
            try:
                await stop()
            except BaseException as exc:
                if first_error is None:
                    first_error = exc
                logger.exception("Failed to stop adapter server: %s", exc)

        if first_error is not None:
            raise first_error
