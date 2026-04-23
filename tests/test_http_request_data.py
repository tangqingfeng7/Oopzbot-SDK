"""覆盖 `HttpTransport.request_data` 和 `request_data_with_retry` 的行为一致性。

重点是 `{"status": true, "data": null}` 这种合法的"空 data"响应，
两条路径都必须返回 None，而不是一看到 `data is None` 就抛 OopzApiError。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.transport.http import HttpTransport


class _FakeTransport:
    """只复用 HttpTransport 的 request_data / request_data_with_retry 实现，
    把底层 request_json 换成一个受控的返回，不走真实网络。"""

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    async def request_json(self, *args, **kwargs):
        return self._payload

    request_data = HttpTransport.request_data
    request_data_with_retry = HttpTransport.request_data_with_retry


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_request_data_returns_none_when_data_is_explicit_null() -> None:
    t = _FakeTransport({"status": True, "data": None})
    assert _run(t.request_data("GET", "/x")) is None


def test_request_data_raises_when_data_field_missing() -> None:
    t = _FakeTransport({"status": True})
    with pytest.raises(OopzApiError):
        _run(t.request_data("GET", "/x"))


def test_request_data_with_retry_returns_none_when_data_is_null() -> None:
    t = _FakeTransport({"status": True, "data": None})
    assert _run(t.request_data_with_retry("GET", "/x")) is None


def test_request_data_and_retry_agree_on_missing_data() -> None:
    t = _FakeTransport({"status": True})
    with pytest.raises(OopzApiError):
        _run(t.request_data_with_retry("GET", "/x"))
