from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any

from .context import EventContext
from .registry import EventRegistry

logger = logging.getLogger("oopz_sdk.events.dispatcher")


class EventDispatcher:
    """
    事件分发器。

    设计目标：
    - message 事件：handler(message, ctx)
    - ready / reconnect：handler(ctx)
    - error / close / raw_event / 其他：handler(event, ctx)

    兼容性：
    - 如果 handler 参数个数不一致，会尽量降级调用
    - 支持同步 / 异步 handler
    """

    def __init__(self, registry: EventRegistry):
        self.registry = registry

    async def dispatch(self, event_name: str, event: Any, context: EventContext) -> None:
        handlers = self.registry.get_handlers(event_name)

        for handler in handlers:
            try:
                result = self._invoke_handler(handler, event_name, event, context)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("事件处理器执行失败: event=%s handler=%r", event_name, handler)

    def dispatch_sync(self, event_name: str, event: Any, context: EventContext) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.dispatch(event_name, event, context))
            return

        loop.create_task(self.dispatch(event_name, event, context))

    @staticmethod
    def _invoke_handler(handler, event_name: str, event: Any, context: EventContext):
        """
        定义事件的调用方式。
        """
        if event_name == "message":
            message = getattr(event, "message", None)
            return handler(message, context)

        if event_name in {"ready", "reconnect"}:
            return handler(context)

        if event_name in {"close", "error", "raw_event"}:
            return handler(context, event)

        return handler(context, event)

    # def _invoke_handler(self, handler, event_name: str, event: Any, context: EventContext):
    #     """
    #     根据事件类型和 handler 签名，选择最合适的调用方式。
    #     """
    #
    #     # 优先按事件语义调用
    #     preferred_args = self._build_preferred_args(event_name, event, context)
    #
    #     # 如果签名正常可分析，尽量按参数数量做兼容裁剪
    #     try:
    #         sig = inspect.signature(handler)
    #         positional_params = [
    #             p for p in sig.parameters.values()
    #             if p.kind in (
    #                 inspect.Parameter.POSITIONAL_ONLY,
    #                 inspect.Parameter.POSITIONAL_OR_KEYWORD,
    #             )
    #         ]
    #         has_varargs = any(
    #             p.kind == inspect.Parameter.VAR_POSITIONAL
    #             for p in sig.parameters.values()
    #         )
    #
    #         if has_varargs:
    #             return handler(*preferred_args)
    #
    #         argc = len(positional_params)
    #
    #         if argc <= 0:
    #             return handler()
    #         if argc == 1:
    #             # message/ready 事件优先给第一个核心对象
    #             return handler(preferred_args[0])
    #         if argc == 2:
    #             return handler(*preferred_args[:2])
    #
    #         # >= 3 时，仍按 preferred_args 调，多余参数交给 Python 报错更清晰
    #         return handler(*preferred_args)
    #
    #     except (TypeError, ValueError):
    #         # 某些可调用对象签名不可分析时，直接按语义调用
    #         return handler(*preferred_args)
    #
    # @staticmethod
    # def _build_preferred_args(event_name: str, event: Any, context: EventContext):
    #     """
    #     为不同事件构建推荐参数。
    #     """
    #     if event_name == "message":
    #         message = getattr(event, "message", None)
    #         return (message, context)
    #
    #     if event_name in {"ready", "reconnect"}:
    #         return (context,)
    #
    #     if event_name == "close":
    #         return (event, context)
    #
    #     if event_name == "error":
    #         return (event, context)
    #
    #     if event_name == "raw_event":
    #         return (event, context)
    #
    #     return (event, context)
