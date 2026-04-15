from __future__ import annotations

from collections import defaultdict
from typing import Awaitable, Callable, DefaultDict


EventHandler = Callable[..., Awaitable[None] | None]


class EventRegistry:
    def __init__(self):
        self._handlers: DefaultDict[str, list[EventHandler]] = defaultdict(list)

    def on(self, event_name: str, handler: EventHandler | None = None):
        if handler is not None:
            self._handlers[event_name].append(handler)
            return handler

        def decorator(fn: EventHandler):
            self._handlers[event_name].append(fn)
            return fn

        return decorator

    def get_handlers(self, event_name: str) -> list[EventHandler]:
        return list(self._handlers.get(event_name, ()))
