"""测试被服务端限流（HTTP 429）时的两件事：异常能不能正常抛出，以及会不会自动重试。

以前 OopzRateLimitError 里把 status_code=429 写死了，调用它的地方又传了一遍同名
参数，两边打架，实际抛出来的是 TypeError 而不是 OopzRateLimitError。负责重试的
代码只认 OopzRateLimitError，接不住 TypeError，所以重试一次都没跑起来过。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from oopz_sdk.exceptions import OopzApiError, OopzRateLimitError
from oopz_sdk.testing.factories import make_config
from oopz_sdk.transport.http import HttpResponse, HttpTransport


def _response(status_code: int, payload: dict, headers: dict | None = None) -> HttpResponse:
    text = json.dumps(payload)
    return HttpResponse(
        status_code=status_code,
        headers=headers or {},
        content=text.encode(),
        text=text,
    )


def _transport(responses: list[HttpResponse]):
    """按顺序返回 responses，用尽后重复最后一个。"""
    transport = HttpTransport(make_config(), object())
    calls: list[tuple[str, str]] = []

    async def fake_request(method, path, **kwargs):
        calls.append((method, path))
        return responses[min(len(calls) - 1, len(responses) - 1)]

    transport.request = fake_request
    return transport, calls


@pytest.fixture
def waits(monkeypatch):
    recorded: list[float] = []

    async def fake_sleep(seconds, *args, **kwargs):
        recorded.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return recorded


# ---------------------------------------------------------------------------
# 异常构造
# ---------------------------------------------------------------------------


def test_rate_limit_error_accepts_explicit_status_code() -> None:
    error = OopzRateLimitError(message="slow down", retry_after=3, status_code=429)

    assert isinstance(error, OopzApiError)
    assert error.status_code == 429
    assert error.retry_after == 3
    assert error.message == "slow down"


def test_rate_limit_error_defaults_to_429() -> None:
    error = OopzRateLimitError()

    assert error.status_code == 429
    assert error.retry_after == 0


# ---------------------------------------------------------------------------
# request_json
# ---------------------------------------------------------------------------


def test_request_json_raises_rate_limit_error_on_429() -> None:
    transport, _ = _transport(
        [_response(429, {"message": "slow down"}, {"Retry-After": "7"})]
    )

    with pytest.raises(OopzRateLimitError) as excinfo:
        asyncio.run(transport.request_json("GET", "/x"))

    assert excinfo.value.status_code == 429
    assert excinfo.value.retry_after == 7
    assert "slow down" in str(excinfo.value)


# ---------------------------------------------------------------------------
# request_data_with_retry
# ---------------------------------------------------------------------------


def test_retry_backs_off_and_exhausts_attempts(waits) -> None:
    transport, calls = _transport([_response(429, {"message": "slow down"})])

    with pytest.raises(OopzRateLimitError):
        asyncio.run(
            transport.request_data_with_retry(
                "GET", "/x", max_attempts=3, retry_on_429=True
            )
        )

    assert len(calls) == 3
    assert waits == [1, 2]


def test_retry_honours_retry_after_header(waits) -> None:
    transport, calls = _transport(
        [_response(429, {"message": "slow down"}, {"Retry-After": "5"})]
    )

    with pytest.raises(OopzRateLimitError):
        asyncio.run(
            transport.request_data_with_retry(
                "GET", "/x", max_attempts=3, retry_on_429=True
            )
        )

    assert len(calls) == 3
    assert waits == [5, 5]


def test_no_retry_when_disabled(waits) -> None:
    transport, calls = _transport([_response(429, {"message": "slow down"})])

    with pytest.raises(OopzRateLimitError):
        asyncio.run(
            transport.request_data_with_retry(
                "GET", "/x", max_attempts=3, retry_on_429=False
            )
        )

    assert len(calls) == 1
    assert waits == []


def test_retry_returns_data_once_limit_clears(waits) -> None:
    transport, calls = _transport(
        [
            _response(429, {"message": "slow down"}),
            _response(200, {"status": True, "data": {"ok": 1}}),
        ]
    )

    data = asyncio.run(
        transport.request_data_with_retry(
            "GET", "/x", max_attempts=3, retry_on_429=True
        )
    )

    assert data == {"ok": 1}
    assert len(calls) == 2
    assert waits == [1]
