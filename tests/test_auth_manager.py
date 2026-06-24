"""AuthManager 及其在 HTTP/WS 集成点的离线测试。

覆盖：
- 续期能力判定（can_refresh）、临期检测（needs_refresh / seconds_until_expiry）
- ensure_fresh / handle_auth_error / refresh 的 single-flight 与不可恢复语义
- 续期成功后写回 config、通知监听者、token_version 自增
- HTTP 传输层在 401/428 恢复后单次重试
- WS 客户端鉴权失效恢复决策
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from types import SimpleNamespace

import pytest

from oopz_sdk.auth.manager import AuthManager, DEFAULT_REFRESH_THRESHOLD_SECONDS
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzAuthError, OopzPasswordLoginError
from oopz_sdk.transport.http import HttpResponse, HttpTransport


def _fake_jwt(exp: float) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("utf-8").rstrip("=")
    body = (
        base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )
    return f"{header}.{body}.sig"


def _config(exp_offset: float) -> OopzConfig:
    return OopzConfig(
        device_id="dev-1",
        person_uid="uid-1",
        jwt_token=_fake_jwt(time.time() + exp_offset),
        private_key="dummy-key",
    )


def _credentials(jwt_token: str) -> SimpleNamespace:
    return SimpleNamespace(
        device_id="dev-1",
        person_uid="uid-1",
        jwt_token=jwt_token,
        private_key_pem="dummy-key",
        app_version="",
    )


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _response(status: int, payload: dict | None = None) -> HttpResponse:
    text = json.dumps(payload or {})
    return HttpResponse(status_code=status, headers={}, content=text.encode("utf-8"), text=text)


# --------------------------------------------------------------------------- #
# 能力判定 / 临期检测
# --------------------------------------------------------------------------- #


def test_can_refresh_false_without_relogin() -> None:
    manager = AuthManager(_config(3600))
    assert manager.can_refresh is False


def test_can_refresh_true_with_relogin() -> None:
    async def _relogin():
        return _credentials(_fake_jwt(time.time() + 3600))

    manager = AuthManager(_config(3600), relogin=_relogin)
    assert manager.can_refresh is True


def test_seconds_until_expiry_and_needs_refresh() -> None:
    manager = AuthManager(_config(1000))
    remaining = manager.seconds_until_expiry()
    assert remaining is not None and 900 < remaining <= 1000
    assert manager.needs_refresh() is False

    near = AuthManager(_config(100))  # 100s < 默认阈值 300s
    assert near.needs_refresh() is True


def test_needs_refresh_false_without_exp_claim() -> None:
    config = OopzConfig(
        device_id="d", person_uid="p", jwt_token="no.exp.token", private_key="k"
    )
    manager = AuthManager(config)
    assert manager.seconds_until_expiry() is None
    assert manager.needs_refresh() is False


def test_default_threshold() -> None:
    manager = AuthManager(_config(3600))
    assert manager.refresh_threshold_seconds == DEFAULT_REFRESH_THRESHOLD_SECONDS


# --------------------------------------------------------------------------- #
# refresh / ensure_fresh / handle_auth_error
# --------------------------------------------------------------------------- #


def test_ensure_fresh_skips_when_not_near_expiry() -> None:
    calls = 0

    async def _relogin():
        nonlocal calls
        calls += 1
        return _credentials(_fake_jwt(time.time() + 3600))

    manager = AuthManager(_config(3600), relogin=_relogin)
    assert _run(manager.ensure_fresh()) is True
    assert calls == 0  # 未临期不应重登


def test_ensure_fresh_refreshes_when_near_expiry() -> None:
    new_token = _fake_jwt(time.time() + 3600)

    async def _relogin():
        return _credentials(new_token)

    config = _config(100)
    manager = AuthManager(config, relogin=_relogin)
    assert _run(manager.ensure_fresh()) is True
    assert config.jwt_token == new_token
    assert manager.token_version == 1


def test_ensure_fresh_returns_false_when_near_expiry_but_cannot_refresh() -> None:
    manager = AuthManager(_config(100))
    assert _run(manager.ensure_fresh()) is False


def test_refresh_applies_credentials_and_notifies_listener() -> None:
    new_token = _fake_jwt(time.time() + 7200)
    seen: list[str] = []

    async def _relogin():
        return _credentials(new_token)

    config = _config(100)
    manager = AuthManager(config, relogin=_relogin)
    manager.add_token_listener(lambda cfg: seen.append(cfg.jwt_token))

    assert _run(manager.refresh(force=True)) is True
    assert config.jwt_token == new_token
    assert seen == [new_token]
    assert manager.token_version == 1


def test_refresh_returns_false_when_cannot_refresh() -> None:
    manager = AuthManager(_config(100))
    assert _run(manager.refresh(force=True)) is False


def test_refresh_reraises_oopz_auth_error() -> None:
    async def _relogin():
        raise OopzPasswordLoginError("bad password")

    manager = AuthManager(_config(100), relogin=_relogin)
    with pytest.raises(OopzAuthError):
        _run(manager.refresh(force=True))


def test_refresh_swallows_generic_error_and_returns_false() -> None:
    async def _relogin():
        raise RuntimeError("network down")

    manager = AuthManager(_config(100), relogin=_relogin)
    assert _run(manager.refresh(force=True)) is False
    assert manager.token_version == 0


def test_handle_auth_error_false_without_relogin() -> None:
    manager = AuthManager(_config(100))
    assert _run(manager.handle_auth_error()) is False


def test_handle_auth_error_true_on_recovery() -> None:
    async def _relogin():
        return _credentials(_fake_jwt(time.time() + 3600))

    manager = AuthManager(_config(100), relogin=_relogin)
    assert _run(manager.handle_auth_error(OopzAuthError("x"))) is True


def test_concurrent_refresh_is_single_flight() -> None:
    calls = 0

    async def _relogin():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return _credentials(_fake_jwt(time.time() + 3600))

    async def _scenario():
        manager = AuthManager(_config(100), relogin=_relogin)
        results = await asyncio.gather(
            manager.refresh(force=True),
            manager.refresh(force=True),
            manager.refresh(force=True),
        )
        return manager, results

    manager, results = _run(_scenario())
    assert all(results)
    # 三个并发调用只真正触发一次重登。
    assert calls == 1
    assert manager.token_version == 1


# --------------------------------------------------------------------------- #
# HTTP 集成：401/428 恢复后单次重试
# --------------------------------------------------------------------------- #


class _FakeAuthManager:
    def __init__(self, *, recover: bool) -> None:
        self._recover = recover
        self.calls = 0

    def add_token_listener(self, listener) -> None:  # noqa: D401 - 接口占位
        pass

    async def handle_auth_error(self, error) -> bool:
        self.calls += 1
        return self._recover


class _SequenceTransport(HttpTransport):
    """按顺序返回受控响应，复用 HttpTransport.request_json。"""

    def __init__(self, responses, *, auth_manager=None) -> None:  # noqa: D401
        self._responses = list(responses)
        self._auth_manager = auth_manager
        self.requests = 0

    async def request(self, *args, **kwargs) -> HttpResponse:
        self.requests += 1
        return self._responses.pop(0)


def test_request_json_retries_once_after_recovery() -> None:
    auth = _FakeAuthManager(recover=True)
    transport = _SequenceTransport(
        [_response(401, {"message": "expired"}), _response(200, {"status": True, "data": 1})],
        auth_manager=auth,
    )
    result = _run(transport.request_json("GET", "/x"))
    assert result == {"status": True, "data": 1}
    assert auth.calls == 1
    assert transport.requests == 2


def test_request_json_raises_when_recovery_fails() -> None:
    auth = _FakeAuthManager(recover=False)
    transport = _SequenceTransport([_response(401, {"message": "expired"})], auth_manager=auth)
    with pytest.raises(OopzAuthError):
        _run(transport.request_json("GET", "/x"))
    assert auth.calls == 1
    assert transport.requests == 1


def test_request_json_retries_at_most_once() -> None:
    auth = _FakeAuthManager(recover=True)
    # 重试后仍然 401：不应无限循环，单次重试后即抛出。
    transport = _SequenceTransport(
        [_response(401, {"message": "expired"}), _response(401, {"message": "still bad"})],
        auth_manager=auth,
    )
    with pytest.raises(OopzAuthError):
        _run(transport.request_json("GET", "/x"))
    assert auth.calls == 1
    assert transport.requests == 2


# --------------------------------------------------------------------------- #
# WS 集成：鉴权失效恢复决策
# --------------------------------------------------------------------------- #


def test_ws_recover_from_auth_error_without_manager_is_false() -> None:
    from oopz_sdk.client.ws import OopzWSClient

    client = OopzWSClient(config=_config(3600))
    assert _run(client._recover_from_auth_error(OopzAuthError("x"))) is False


def test_ws_recover_from_auth_error_delegates_to_manager() -> None:
    from oopz_sdk.client.ws import OopzWSClient

    auth = _FakeAuthManager(recover=True)
    client = OopzWSClient(config=_config(3600), auth_manager=auth)
    assert _run(client._recover_from_auth_error(OopzAuthError("x"))) is True
    assert auth.calls == 1
