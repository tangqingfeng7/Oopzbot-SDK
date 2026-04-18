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
        coroutine = self.dispatch(event_name, event, context)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coroutine)
            return

        loop.create_task(coroutine)

    @staticmethod
    def _invoke_handler(handler, event_name: str, event: Any, context: EventContext):
        """
        定义事件的调用方式。
        """
        preferred_args = EventDispatcher._build_preferred_args(event_name, event, context)

        try:
            sig = inspect.signature(handler)
        except (TypeError, ValueError):
            return handler(*preferred_args)

        positional_params = [
            param
            for param in sig.parameters.values()
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        has_varargs = any(
            param.kind == inspect.Parameter.VAR_POSITIONAL
            for param in sig.parameters.values()
        )

        if has_varargs:
            return handler(*preferred_args)

        argc = len(positional_params)
        if argc <= 0:
            return handler()
        if argc == 1:
            return handler(preferred_args[0])
        if argc == 2:
            return handler(*preferred_args[:2])
        return handler(*preferred_args)

    @staticmethod
    def _build_preferred_args(event_name: str, event: Any, context: EventContext):
        """
        为不同事件构建推荐参数。
        """
        if event_name == "message":
            message = getattr(event, "message", None)
            return (message, context)

        if event_name in {"ready", "reconnect"}:
            return (context,)

        return (event, context)
