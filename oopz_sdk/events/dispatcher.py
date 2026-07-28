from __future__ import annotations

import inspect
import logging
from typing import Any

from .context import EventContext
from .registry import EventRegistry
from ..exceptions import OopzAuthError
from ..state.cache import CacheStore

logger = logging.getLogger(__name__)


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
        await self._update_cache_before_dispatch(event_name, event, context)
        handlers = self.registry.get_handlers(event_name)

        for handler in handlers:
            try:
                result = self._invoke_handler(handler, event_name, event, context)
                if inspect.isawaitable(result):
                    await result
            except OopzAuthError:
                # 不可恢复的鉴权失效（HTTP 层已做过单次重登重试仍失败）不能在此吞掉：
                # 否则 Bot 会带着死凭据继续运行，连接仍在但后续鉴权请求持续失败。
                # 向上传播，由 WS 客户端按回调致命错误升级为全局停机
                logger.error(
                    "事件处理器遇到不可恢复的鉴权失效，升级为致命错误: event=%s handler=%r",
                    event_name,
                    handler,
                )
                raise
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

    @staticmethod
    async def _update_cache_before_dispatch(
            event_name: str,
            event: Any,
            context: EventContext,
    ) -> None:
        bot = context.bot
        cache: CacheStore = context.bot.cache
        if cache is None:
            return
        # 用户资料更新：清理用户缓存
        if event_name == "user.update":
            uid = getattr(event, "person", None)

            if uid == bot.config.person_uid:
                cache.invalidate_identity()
            if uid:
                cache.invalidate_userinfo(str(uid))
                cache.invalidate_person_profile(str(uid))


        # 频道创建 / 更新 / 删除：清理 area_channels
        elif event_name in {"channel.create", "channel.update", "channel.delete"}:
            area = getattr(event, "area", None) or getattr(event, "area_id", None)
            if area:
                cache.invalidate_area_channels(str(area))