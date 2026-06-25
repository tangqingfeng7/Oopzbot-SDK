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
from oopz_sdk.exceptions import OopzAuthError, OopzConnectionError, OopzPasswordLoginError
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


def test_refresh_treats_connection_error_as_transient() -> None:
    """续期时的瞬时连接错误应有限次退避重试后返回 False，而非永久停机。"""
    calls = 0

    async def _relogin():
        nonlocal calls
        calls += 1
        raise OopzConnectionError("OOPZ 登录服务暂时不可用 (HTTP 503)")

    manager = AuthManager(
        _config(100),
        relogin=_relogin,
        relogin_max_attempts=3,
        relogin_backoff_seconds=0,  # 测试免去真实退避等待
    )
    # OopzConnectionError 非 OopzAuthError 子类 → 不上抛、退避重试耗尽后返回 False。
    assert _run(manager.refresh(force=True)) is False
    assert manager.token_version == 0
    # 应按配置重试到上限，而非一次失败即放弃。
    assert calls == 3


def test_handle_auth_error_false_without_relogin() -> None:
    manager = AuthManager(_config(100))
    assert _run(manager.handle_auth_error()) is False


def test_handle_auth_error_true_on_recovery() -> None:
    async def _relogin():
        return _credentials(_fake_jwt(time.time() + 3600))

    manager = AuthManager(_config(100), relogin=_relogin)
    assert _run(manager.handle_auth_error(OopzAuthError("x"))) is True


def test_handle_auth_error_skips_relogin_when_token_already_rotated() -> None:
    """token 在请求在途期间已被轮换：直接复用当前 token，不再重登。"""
    calls = {"n": 0}

    async def _relogin():
        calls["n"] += 1
        return _credentials(_fake_jwt(time.time() + 3600))

    manager = AuthManager(_config(100), relogin=_relogin)
    assert _run(manager.refresh(force=True)) is True
    assert manager.token_version == 1
    assert calls["n"] == 1

    # 失败请求所用的是续期前版本(0)，当前已是 1 → 直接返回 True，不触发额外重登。
    assert (
        _run(manager.handle_auth_error(OopzAuthError("x"), observed_token_version=0))
        is True
    )
    assert calls["n"] == 1


def test_handle_auth_error_relogins_when_version_matches() -> None:
    """观察到的版本与当前一致：确属当前 token 被拒，仍需强制重登。"""
    calls = {"n": 0}

    async def _relogin():
        calls["n"] += 1
        return _credentials(_fake_jwt(time.time() + 3600))

    manager = AuthManager(_config(100), relogin=_relogin)
    assert (
        _run(manager.handle_auth_error(OopzAuthError("x"), observed_token_version=0))
        is True
    )
    assert calls["n"] == 1
    assert manager.token_version == 1


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
    def __init__(self, *, recover: bool, token_version: int = 0) -> None:
        self._recover = recover
        self._token_version = token_version
        self.calls = 0
        self.observed_versions: list[int | None] = []

    @property
    def token_version(self) -> int:
        return self._token_version

    def add_token_listener(self, listener) -> None:  # noqa: D401 - 接口占位
        pass

    async def handle_auth_error(self, error, *, observed_token_version=None) -> bool:
        self.calls += 1
        self.observed_versions.append(observed_token_version)
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


# --------------------------------------------------------------------------- #
# WS 传输层：握手鉴权拒绝 → OopzAuthError（让反应式恢复可达）
# --------------------------------------------------------------------------- #


def _handshake_error(status: int):
    from aiohttp import RequestInfo, WSServerHandshakeError
    from multidict import CIMultiDict, CIMultiDictProxy
    from yarl import URL

    url = URL("wss://ws.oopz.cn")
    request_info = RequestInfo(url, "GET", CIMultiDictProxy(CIMultiDict()), url)
    return WSServerHandshakeError(request_info, (), status=status, message="handshake rejected")


class _StubWsSession:
    """伪 aiohttp 会话：ws_connect 直接抛出预设异常。"""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.closed = False

    async def ws_connect(self, *args, **kwargs):
        raise self._exc


@pytest.mark.parametrize("status", [401, 428])
def test_ws_transport_handshake_auth_status_maps_to_auth_error(status: int) -> None:
    from oopz_sdk.transport.ws import WebSocketTransport

    transport = WebSocketTransport(_config(3600))
    transport._session = _StubWsSession(_handshake_error(status))
    with pytest.raises(OopzAuthError) as exc_info:
        _run(transport.connect())
    assert exc_info.value.status_code == status


def test_ws_transport_handshake_non_auth_status_wrapped_as_connection_error() -> None:
    from oopz_sdk.transport.ws import WebSocketTransport

    transport = WebSocketTransport(_config(3600))
    transport._session = _StubWsSession(_handshake_error(503))
    # 非鉴权握手失败统一包装为 OopzConnectionError（与 HTTP 传输层一致）。
    with pytest.raises(OopzConnectionError):
        _run(transport.connect())


def test_ws_transport_client_error_wrapped_as_connection_error() -> None:
    import aiohttp

    from oopz_sdk.transport.ws import WebSocketTransport

    transport = WebSocketTransport(_config(3600))
    transport._session = _StubWsSession(aiohttp.ClientConnectionError("refused"))
    with pytest.raises(OopzConnectionError):
        _run(transport.connect())


# --------------------------------------------------------------------------- #
# WS 客户端：主动续期断连属计划内（不当作错误）
# --------------------------------------------------------------------------- #


def test_is_planned_refresh_close_predicate() -> None:
    from oopz_sdk.client.ws import OopzWSClient
    from oopz_sdk.transport.ws import WebSocketClosedError

    client = OopzWSClient(config=_config(3600))
    closed = WebSocketClosedError(code=1000, reason="x")

    # 默认无计划内续期标记：不是计划内断连。
    assert client._is_planned_refresh_close(closed) is False

    # 计划内续期标记指向当前连接代 + WebSocketClosedError：计划内断连。
    client._connection_generation = 5
    client._planned_refresh_generation = 5
    assert client._is_planned_refresh_close(closed) is True

    # 标记属于旧连接代（已重连到新代）：不算计划内，按真实断连处理。
    client._connection_generation = 6
    assert client._is_planned_refresh_close(closed) is False

    # 标记对齐当前代，但异常类型不符：不算计划内（应正常按错误处理）。
    client._planned_refresh_generation = client._connection_generation
    assert client._is_planned_refresh_close(RuntimeError("y")) is False


# --------------------------------------------------------------------------- #
# WS 客户端：运行期鉴权校验事件（event=21, checkRes=false）→ OopzAuthError
# --------------------------------------------------------------------------- #


def test_raise_if_auth_rejected_on_check_failure() -> None:
    from oopz_sdk.client.ws import OopzWSClient

    # 服务端实测帧：event=21，body 为字符串化 JSON {"checkRes": false}
    raw = json.dumps({"time": "1", "event": 21, "body": json.dumps({"checkRes": False})})
    with pytest.raises(OopzAuthError):
        OopzWSClient._raise_if_auth_rejected(raw)


def test_raise_if_auth_rejected_body_as_object() -> None:
    from oopz_sdk.client.ws import OopzWSClient

    # body 已是对象（非字符串）时同样应识别。
    raw = json.dumps({"event": 21, "body": {"checkRes": False}})
    with pytest.raises(OopzAuthError):
        OopzWSClient._raise_if_auth_rejected(raw)


def test_raise_if_auth_rejected_passes_through_non_failures() -> None:
    from oopz_sdk.client.ws import OopzWSClient

    # checkRes=true、其它事件、非 JSON 都不应抛出。
    OopzWSClient._raise_if_auth_rejected(json.dumps({"event": 21, "body": {"checkRes": True}}))
    OopzWSClient._raise_if_auth_rejected(json.dumps({"event": 9, "body": "{}"}))
    OopzWSClient._raise_if_auth_rejected("not-json")
    OopzWSClient._raise_if_auth_rejected(json.dumps({"event": 21, "body": "not-json"}))


def test_receive_loop_clears_fresh_token_unverified_on_success() -> None:
    """收到一条正常帧后应清除「续期待验证」标记，避免误升级为致命停机。"""
    from oopz_sdk.client.ws import OopzWSClient
    from oopz_sdk.transport.ws import WebSocketClosedError

    class _OneFrameTransport:
        def __init__(self) -> None:
            self._frames = [json.dumps({"event": 9, "body": "{}"})]

        async def recv(self) -> str:
            if self._frames:
                return self._frames.pop(0)
            raise WebSocketClosedError(code=1000, reason="done")

    client = OopzWSClient(config=_config(3600))
    client._running = True
    client._fresh_token_unverified = True
    client.transport = _OneFrameTransport()

    # 第一帧正常 → 清标记；第二次 recv 抛 WebSocketClosedError 退出循环。
    with pytest.raises(WebSocketClosedError):
        _run(client._receive_loop())
    assert client._fresh_token_unverified is False


def test_start_escalates_when_refreshed_token_still_rejected() -> None:
    """续期后的新 token 仍被运行期拒绝时，应在一次恢复后升级停机，而非无限重登。"""
    from oopz_sdk.client.ws import OopzWSClient
    from oopz_sdk.config.settings import HeartbeatConfig

    reject_frame = json.dumps({"event": 21, "body": json.dumps({"checkRes": False})})

    class _RejectTransport:
        def __init__(self) -> None:
            self.closed = False
            self.connects = 0

        async def connect(self) -> None:
            self.connects += 1
            self.closed = False

        async def send_json(self, data) -> None:
            pass

        async def recv(self) -> str:
            return reject_frame  # 每次都返回鉴权拒绝（模拟新 token 仍被拒）

        async def close(self) -> None:
            self.closed = True

    class _AlwaysRecoverManager:
        can_refresh = True

        def __init__(self) -> None:
            self.calls = 0

        def add_token_listener(self, listener) -> None:
            pass

        @property
        def refresh_threshold_seconds(self) -> float:
            return 300.0

        def needs_refresh(self, **_kw) -> bool:
            return False

        async def refresh(self, **_kw) -> bool:
            return False

        async def handle_auth_error(self, _error) -> bool:
            self.calls += 1
            return True  # 声称恢复成功，但 token 仍被拒

    cfg = _config(3600)
    cfg.heartbeat = HeartbeatConfig(interval=999, reconnect_interval=0, max_reconnect_interval=0)
    manager = _AlwaysRecoverManager()
    client = OopzWSClient(config=cfg, auth_manager=manager)
    client.transport = _RejectTransport()

    with pytest.raises(OopzAuthError):
        _run(client.start())

    # 第一轮失败→恢复并重连；第二轮失败→因新 token 未验证而升级停机。
    assert manager.calls == 1
    assert client.transport.connects == 2


def test_start_does_not_relogin_on_callback_auth_error() -> None:
    """来自用户回调的 OopzAuthError 应直接升级致命，不做无谓重登。"""
    from oopz_sdk.client.ws import OopzWSClient
    from oopz_sdk.config.settings import HeartbeatConfig

    benign_frame = json.dumps({"event": 1, "body": "{}"})

    class _NormalTransport:
        def __init__(self) -> None:
            self.closed = False

        async def connect(self) -> None:
            self.closed = False

        async def send_json(self, data) -> None:
            pass

        async def recv(self) -> str:
            return benign_frame

        async def close(self) -> None:
            self.closed = True

    class _CountingManager:
        can_refresh = True

        def __init__(self) -> None:
            self.calls = 0

        def add_token_listener(self, listener) -> None:
            pass

        @property
        def refresh_threshold_seconds(self) -> float:
            return 300.0

        def needs_refresh(self, **_kw) -> bool:
            return False

        async def refresh(self, **_kw) -> bool:
            return False

        async def handle_auth_error(self, _error) -> bool:
            self.calls += 1
            return True

    async def _raise_auth(_raw: str) -> None:
        raise OopzAuthError("鉴权失效来自回调")

    cfg = _config(3600)
    cfg.heartbeat = HeartbeatConfig(interval=999, reconnect_interval=0, max_reconnect_interval=0)
    manager = _CountingManager()
    client = OopzWSClient(config=cfg, on_message=_raise_auth, auth_manager=manager)
    client.transport = _NormalTransport()

    with pytest.raises(OopzAuthError):
        _run(client.start())

    # 回调来源的鉴权错误：不应触发任何重登，直接致命停机。
    assert manager.calls == 0
