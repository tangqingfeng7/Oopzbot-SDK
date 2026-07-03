"""EventDispatcher 异常语义测试。

- 普通异常：吞掉并派发 error 事件（Bot 继续运行）。
- OopzAuthError：不可恢复鉴权失效，必须向上传播以触发全局停机
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from oopz_sdk.events.context import EventContext
from oopz_sdk.events.dispatcher import EventDispatcher
from oopz_sdk.events.registry import EventRegistry
from oopz_sdk.exceptions import OopzAuthError


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _make_dispatcher() -> tuple[EventDispatcher, EventRegistry, EventContext]:
    registry = EventRegistry()
    dispatcher = EventDispatcher(registry)
    bot = SimpleNamespace(cache=None)
    ctx = EventContext(bot=bot, config=None, event=None)
    return dispatcher, registry, ctx


def test_generic_handler_error_is_swallowed_and_dispatched_as_error_event() -> None:
    dispatcher, registry, ctx = _make_dispatcher()
    seen: list[Exception] = []

    @registry.on("message")
    async def _boom(_message, _ctx):
        raise RuntimeError("handler failed")

    @registry.on("error")
    async def _on_error(_ctx, exc):
        seen.append(exc)

    # 普通异常不向上传播，Bot 不因单个 handler 出错而停机。
    _run(dispatcher.dispatch("message", SimpleNamespace(message=None), ctx))
    assert len(seen) == 1
    assert isinstance(seen[0], RuntimeError)


def test_auth_error_from_handler_propagates() -> None:
    dispatcher, registry, ctx = _make_dispatcher()
    error_handler_calls: list[Exception] = []

    @registry.on("message")
    async def _dead_credentials(_message, _ctx):
        raise OopzAuthError("relogin rejected", status_code=401)

    @registry.on("error")
    async def _on_error(_ctx, exc):
        error_handler_calls.append(exc)

    # 不可恢复鉴权失效必须向上传播（由 WS 客户端升级为致命停机），
    # 而不是只派发 error 事件后继续运行。
    with pytest.raises(OopzAuthError):
        _run(dispatcher.dispatch("message", SimpleNamespace(message=None), ctx))
    assert error_handler_calls == []


def test_auth_error_from_error_handler_propagates() -> None:
    dispatcher, registry, ctx = _make_dispatcher()

    @registry.on("error")
    async def _error_handler_with_dead_credentials(_ctx, _exc):
        raise OopzAuthError("relogin rejected", status_code=401)

    with pytest.raises(OopzAuthError):
        _run(dispatcher.dispatch("error", RuntimeError("origin"), ctx))


def test_sync_handler_auth_error_propagates() -> None:
    dispatcher, registry, ctx = _make_dispatcher()

    @registry.on("ready")
    def _sync_dead_credentials(_ctx):
        raise OopzAuthError("relogin rejected", status_code=428)

    with pytest.raises(OopzAuthError):
        _run(dispatcher.dispatch("ready", None, ctx))
