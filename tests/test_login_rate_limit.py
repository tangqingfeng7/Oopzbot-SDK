"""登录接口返回 429 时应按瞬时错误处理，而不是当成凭据失效。

429 若归入 4xx 分支会变成 OopzAuthError，AuthManager 直接上报停机，
无人值守的 Bot 会被一次限流打死；而 5xx 和网络错误早就归为可重试。
"""

from __future__ import annotations

import asyncio

import pytest

import oopz_sdk.auth.api_password_login as apl
from oopz_sdk.auth.manager import AuthManager
from oopz_sdk.exceptions import OopzAuthError, OopzConnectionError
from oopz_sdk.testing.factories import make_config


class _Response:
    def __init__(self, status_code: int, headers: dict | None = None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload if payload is not None else {"status": False}

    def json(self):
        return self._payload


def _login(monkeypatch, response: _Response):
    monkeypatch.setattr(apl.requests, "post", lambda *a, **kw: response)
    return lambda: apl.login_with_api_password("13800000000", "pw", device_id="d")


def test_429_is_transient_not_auth_error(monkeypatch) -> None:
    call = _login(monkeypatch, _Response(429))

    with pytest.raises(OopzConnectionError) as excinfo:
        call()

    # 关键：不能是 OopzAuthError 子类，否则 AuthManager 会直接停机
    assert not isinstance(excinfo.value, OopzAuthError)


def test_429_carries_retry_after(monkeypatch) -> None:
    call = _login(monkeypatch, _Response(429, {"Retry-After": "7"}))

    with pytest.raises(OopzConnectionError) as excinfo:
        call()

    assert excinfo.value.retry_after == 7


def test_429_without_retry_after_defaults_to_zero(monkeypatch) -> None:
    call = _login(monkeypatch, _Response(429))

    with pytest.raises(OopzConnectionError) as excinfo:
        call()

    assert excinfo.value.retry_after == 0


@pytest.mark.parametrize("raw", ["", None, "abc", "-5", "Wed, 21 Oct 2015 07:28:00 GMT"])
def test_retry_after_parsing_is_defensive(raw) -> None:
    assert apl._parse_retry_after(raw) == 0


def test_401_stays_permanent(monkeypatch) -> None:
    # 对照：真正的凭据问题仍应是 OopzAuthError，不能被顺手改成可重试
    call = _login(monkeypatch, _Response(401))

    with pytest.raises(OopzAuthError):
        call()


def test_5xx_still_transient(monkeypatch) -> None:
    call = _login(monkeypatch, _Response(503))

    with pytest.raises(OopzConnectionError):
        call()


def test_auth_manager_retries_on_429_instead_of_stopping() -> None:
    attempts = {"n": 0}

    async def relogin():
        attempts["n"] += 1
        error = OopzConnectionError("限流")
        error.retry_after = 0
        raise error

    manager = AuthManager(make_config(), relogin=relogin)
    manager._relogin_backoff_seconds = 0

    result = asyncio.run(manager.refresh(force=True))

    # 返回 False 表示「这次没续上，可以稍后再试」，而不是抛异常上报停机
    assert result is False
    assert attempts["n"] == manager._relogin_max_attempts


def test_auth_manager_waits_at_least_retry_after() -> None:
    waits: list[float] = []

    async def relogin():
        error = OopzConnectionError("限流")
        error.retry_after = 30
        raise error

    manager = AuthManager(make_config(), relogin=relogin)
    manager._relogin_backoff_seconds = 1  # 远小于 Retry-After

    real_sleep = asyncio.sleep

    async def fake_sleep(seconds, *a, **kw):
        waits.append(seconds)
        return await real_sleep(0)

    asyncio.sleep = fake_sleep
    try:
        asyncio.run(manager.refresh(force=True))
    finally:
        asyncio.sleep = real_sleep

    assert waits, "应该有退避等待"
    assert all(w >= 30 for w in waits), f"退避应不小于 Retry-After，实际 {waits}"
