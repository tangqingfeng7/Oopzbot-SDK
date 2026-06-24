"""登录 token 失效处理相关的离线测试。

覆盖：
- `decode_jwt_payload` / `jwt_expired`（含时钟容差 leeway）
- HTTP 传输层鉴权失败状态码映射（401/428 -> OopzAuthError，403 不是鉴权失效）
- `OopzAuthError` 携带结构化信息
- `OopzConfig` 的 JWT 归一化与启动期过期预检
"""

from __future__ import annotations

import asyncio
import base64
import json
import time

import pytest

from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzAuthError, OopzPasswordLoginError
from oopz_sdk.transport.http import AUTH_FAILURE_STATUS_CODES, HttpResponse, HttpTransport
from oopz_sdk.utils.jwt import decode_jwt_payload, jwt_expired


def _fake_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("utf-8").rstrip("=")
    body = (
        base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )
    return f"{header}.{body}.sig"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _StubTransport(HttpTransport):
    """复用 HttpTransport.request_json，但把底层 request 换成受控响应。"""

    def __init__(self, response: HttpResponse, *, auth_manager=None) -> None:  # noqa: D401
        self._response = response
        self._auth_manager = auth_manager

    async def request(self, *args, **kwargs) -> HttpResponse:
        return self._response


def _response(status: int, payload: dict | None = None) -> HttpResponse:
    text = json.dumps(payload or {})
    return HttpResponse(
        status_code=status,
        headers={},
        content=text.encode("utf-8"),
        text=text,
    )


# --------------------------------------------------------------------------- #
# decode_jwt_payload / jwt_expired
# --------------------------------------------------------------------------- #


def test_decode_jwt_payload_valid() -> None:
    token = _fake_jwt({"exp": 123, "uid": "abc"})
    assert decode_jwt_payload(token) == {"exp": 123, "uid": "abc"}


def test_decode_jwt_payload_malformed_returns_empty() -> None:
    assert decode_jwt_payload("not-a-jwt") == {}
    assert decode_jwt_payload("") == {}
    assert decode_jwt_payload("a.b") == {}


def test_decode_jwt_payload_non_dict_returns_empty() -> None:
    body = base64.urlsafe_b64encode(b"[1, 2, 3]").decode("utf-8").rstrip("=")
    token = f"h.{body}.s"
    assert decode_jwt_payload(token) == {}


def test_jwt_expired_true_when_past() -> None:
    token = _fake_jwt({"exp": time.time() - 10})
    assert jwt_expired(token) is True


def test_jwt_expired_false_when_future() -> None:
    token = _fake_jwt({"exp": time.time() + 3600})
    assert jwt_expired(token) is False


def test_jwt_expired_false_when_no_exp_claim() -> None:
    token = _fake_jwt({"uid": "abc"})
    assert jwt_expired(token) is False


def test_jwt_expired_leeway_tolerates_recent_expiry() -> None:
    # 刚过期 10 秒，但 leeway=60，应视为仍有效（容忍时钟偏快）。
    token = _fake_jwt({"exp": 1000})
    assert jwt_expired(token, now=1010, leeway=60) is False
    assert jwt_expired(token, now=1010, leeway=0) is True
    assert jwt_expired(token, now=1100, leeway=60) is True


# --------------------------------------------------------------------------- #
# HTTP 状态码 -> 异常映射
# --------------------------------------------------------------------------- #


def test_auth_failure_status_codes_excludes_403() -> None:
    assert 401 in AUTH_FAILURE_STATUS_CODES
    assert 428 in AUTH_FAILURE_STATUS_CODES
    assert 403 not in AUTH_FAILURE_STATUS_CODES


@pytest.mark.parametrize("status", [401, 428])
def test_request_json_maps_auth_failure_to_oopz_auth_error(status: int) -> None:
    transport = _StubTransport(_response(status, {"message": "bad token"}))
    with pytest.raises(OopzAuthError) as excinfo:
        _run(transport.request_json("GET", "/x"))
    err = excinfo.value
    assert err.status_code == status
    assert isinstance(err.payload, dict)
    assert err.response is not None


def test_request_json_403_is_api_error_not_auth_error() -> None:
    transport = _StubTransport(_response(403, {"message": "forbidden"}))
    with pytest.raises(OopzApiError) as excinfo:
        _run(transport.request_json("GET", "/x"))
    assert not isinstance(excinfo.value, OopzAuthError)
    assert excinfo.value.status_code == 403


def test_request_json_success_returns_payload() -> None:
    transport = _StubTransport(_response(200, {"status": True, "data": {"ok": 1}}))
    assert _run(transport.request_json("GET", "/x")) == {"status": True, "data": {"ok": 1}}


# --------------------------------------------------------------------------- #
# OopzAuthError 结构化信息
# --------------------------------------------------------------------------- #


def test_oopz_auth_error_carries_structured_fields() -> None:
    err = OopzAuthError("boom", status_code=401, payload={"a": 1}, response="resp")
    assert str(err) == "boom"
    assert err.status_code == 401
    assert err.payload == {"a": 1}
    assert err.response == "resp"


def test_oopz_auth_error_defaults_are_none() -> None:
    err = OopzAuthError("boom")
    assert err.status_code is None
    assert err.payload is None
    assert err.response is None


def test_password_login_error_still_compatible() -> None:
    err = OopzPasswordLoginError("login failed", code=10001, payload={"x": 1})
    assert isinstance(err, OopzAuthError)
    assert err.code == 10001
    assert err.payload == {"x": 1}
    # 整数 code 同步映射到父类 status_code，统一 on_error 的判别方式
    assert err.status_code == 10001
    assert err.response is None


def test_password_login_error_non_int_code_keeps_status_none() -> None:
    err = OopzPasswordLoginError("login failed", code="E_BLOCKED")
    assert err.code == "E_BLOCKED"
    # 非整数 code 无法作为 HTTP 状态码，status_code 保持 None
    assert err.status_code is None
    assert err.response is None


# --------------------------------------------------------------------------- #
# OopzConfig：JWT 归一化 + 启动期过期预检
# --------------------------------------------------------------------------- #


def test_normalize_jwt_token_strips_surrounding_quotes() -> None:
    assert OopzConfig._normalize_jwt_token("'abc'") == "abc"
    assert OopzConfig._normalize_jwt_token('"abc"') == "abc"
    assert OopzConfig._normalize_jwt_token("  abc  ") == "abc"
    assert OopzConfig._normalize_jwt_token(None) == ""


def test_ensure_credentials_raises_on_expired_jwt() -> None:
    token = _fake_jwt({"exp": time.time() - 3600})
    config = OopzConfig(
        device_id="d",
        person_uid="p",
        jwt_token=token,
        private_key="dummy-key",
    )
    with pytest.raises(OopzAuthError, match="expired"):
        config.ensure_credentials()


def test_ensure_credentials_passes_for_valid_jwt() -> None:
    token = _fake_jwt({"exp": time.time() + 3600})
    config = OopzConfig(
        device_id="d",
        person_uid="p",
        jwt_token=token,
        private_key="dummy-key",
    )
    # 不应抛出
    config.ensure_credentials()


def test_ensure_credentials_tolerates_recent_expiry_within_leeway() -> None:
    # exp 刚过去几秒，在 JWT_EXPIRY_LEEWAY_SECONDS 容差内不应被拒。
    token = _fake_jwt({"exp": time.time() - 5})
    config = OopzConfig(
        device_id="d",
        person_uid="p",
        jwt_token=token,
        private_key="dummy-key",
    )
    config.ensure_credentials()
