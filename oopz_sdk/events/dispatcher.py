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
    - error / close / raw_event / 其他：handler(ctx, event)

    说明：
    - 支持同步 / 异步 handler
    - 不同事件名使用固定调用方式
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
            except Exception as exc:
                logger.exception("事件处理器执行失败: event=%s handler=%r", event_name, handler)
                if event_name == "error":
                    continue
                # 触发 error 事件
                error_context = EventContext(bot=context.bot, config=context.config, event=exc)
                await self.dispatch("error", exc, error_context)


    @staticmethod
    def _invoke_handler(handler, event_name: str, event: Any, context: EventContext):
        """
        定义事件的调用方式。
        """
        if event_name in {"message", "message.private", "message.edit", "message.private.edit"}:
            message = getattr(event, "message", None)
            return handler(message, context)

        if event_name in {"ready", "reconnect"}:
            return handler(context)

        if event_name in {"close", "error", "raw_event"}:
            return handler(context, event)

        return handler(context, event)
