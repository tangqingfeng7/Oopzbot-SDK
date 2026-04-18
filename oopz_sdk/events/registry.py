from __future__ import annotations

from collections import defaultdict
from typing import Awaitable, Callable, DefaultDict


EventHandler = Callable[..., Awaitable[None] | None]


class EventRegistry:
    def __init__(self):
        self._handlers: DefaultDict[str, list[EventHandler]] = defaultdict(list)

    def _add_handler(self, event_name: str, handler: EventHandler) -> EventHandler:
        handlers = self._handlers[event_name]
        if handler not in handlers:
            handlers.append(handler)
        return handler

    def on(self, event_name: str, handler: EventHandler | None = None):
        if handler is not None:
            return self._add_handler(event_name, handler)

        def decorator(fn: EventHandler):
            return self._add_handler(event_name, fn)

        return decorator

    def get_handlers(self, event_name: str) -> list[EventHandler]:
        return list(self._handlers.get(event_name, ()))
