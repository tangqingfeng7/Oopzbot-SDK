"""跨组件集成 / 端到端测试。
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from types import SimpleNamespace

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from oopz_sdk.auth.headers import build_oopz_headers
from oopz_sdk.auth.manager import AuthManager
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpResponse, HttpTransport


def _rsa_pem():
    """生成一把全新的 RSA 私钥，返回 (PEM 字符串, 对应公钥)。"""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    return pem, key.public_key()


def _fake_jwt(exp: float) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("utf-8").rstrip("=")
    body = (
        base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )
    return f"{header}.{body}.sig"


def _response(status: int, payload: dict | None = None) -> HttpResponse:
    text = json.dumps(payload or {})
    return HttpResponse(
        status_code=status, headers={}, content=text.encode("utf-8"), text=text
    )


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _signature_valid(public_key, signature_b64: str, message: str) -> bool:
    """用给定公钥验证 Oopz-Sign 是否由对应私钥对 message 所签。"""
    try:
        public_key.verify(
            base64.b64decode(signature_b64),
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


class _SequenceTransport(HttpTransport):
    """复用真实 HttpTransport.request_json，但把底层 request 换成按序回放。"""

    def __init__(self, responses, *, config, signer, auth_manager) -> None:
        super().__init__(config, signer, auth_manager=auth_manager)
        self._responses = list(responses)
        self.request_calls = 0

    async def request(self, *args, **kwargs) -> HttpResponse:
        self.request_calls += 1
        return self._responses.pop(0)


def test_http_401_relogin_rotates_token_and_signing_key_end_to_end() -> None:
    old_pem, old_pub = _rsa_pem()
    new_pem, new_pub = _rsa_pem()
    old_jwt = _fake_jwt(time.time() + 3600)
    # 故意给新 jwt 包上引号与空白，顺带验证续期写回也走 _normalize_jwt_token 归一化。
    raw_new_jwt = _fake_jwt(time.time() + 7200)
    quoted_new_jwt = f"  '{raw_new_jwt}'  "

    config = OopzConfig(
        device_id="dev-stable",
        person_uid="uid-1",
        jwt_token=old_jwt,
        private_key=old_pem,
    )
    signer = Signer(config)

    relogin_calls = {"n": 0}

    async def _relogin():
        relogin_calls["n"] += 1
        # 续期沿用同一 device_id 保持身份稳定，但换发新 jwt 与新签名私钥。
        return SimpleNamespace(
            device_id="dev-stable",
            person_uid="uid-1",
            jwt_token=quoted_new_jwt,
            private_key_pem=new_pem,
            app_version="",
        )

    manager = AuthManager(config, relogin=_relogin)
    transport = _SequenceTransport(
        [_response(401, {"message": "expired"}), _response(200, {"status": True, "data": 7})],
        config=config,
        signer=signer,
        auth_manager=manager,
    )

    # 续期前：请求头携带旧 jwt，签名可被旧公钥验证。
    headers_before = build_oopz_headers(config, signer, "/ping", "{}")
    assert headers_before["Oopz-Signature"] == old_jwt
    msg_before = signer.body_md5("/ping", "{}") + headers_before["Oopz-Time"]
    assert _signature_valid(old_pub, headers_before["Oopz-Sign"], msg_before) is True

    # 触发：401 → 续期 → 重试一次拿到 200。
    result = _run(transport.request_json("GET", "/ping"))

    assert result == {"status": True, "data": 7}
    assert transport.request_calls == 2  # 首请求 + 续期后重试一次
    assert relogin_calls["n"] == 1
    assert manager.token_version == 1

    # 新凭据已就地写回，jwt 归一化去掉引号/空白，device_id 未漂移。
    assert config.jwt_token == raw_new_jwt
    assert config.device_id == "dev-stable"

    # 续期后：请求头随即用新 jwt，且签名由新私钥而非旧私钥产生。
    headers_after = build_oopz_headers(config, signer, "/ping", "{}")
    assert headers_after["Oopz-Signature"] == raw_new_jwt
    msg_after = signer.body_md5("/ping", "{}") + headers_after["Oopz-Time"]
    assert _signature_valid(new_pub, headers_after["Oopz-Sign"], msg_after) is True
    assert _signature_valid(old_pub, headers_after["Oopz-Sign"], msg_after) is False


def test_http_401_without_auth_manager_raises_and_keeps_old_key() -> None:
    """无 AuthManager 时维持原行为：401 直接上抛，签名私钥保持不变。"""
    from oopz_sdk.exceptions import OopzAuthError

    old_pem, old_pub = _rsa_pem()
    jwt = _fake_jwt(time.time() + 3600)
    config = OopzConfig(
        device_id="dev-1", person_uid="uid-1", jwt_token=jwt, private_key=old_pem
    )
    signer = Signer(config)
    transport = _SequenceTransport(
        [_response(401, {"message": "expired"})],
        config=config,
        signer=signer,
        auth_manager=None,
    )

    raised = False
    try:
        _run(transport.request_json("GET", "/ping"))
    except OopzAuthError:
        raised = True
    assert raised is True
    assert transport.request_calls == 1  # 无续期能力，不重试

    headers = build_oopz_headers(config, signer, "/ping", "{}")
    message = signer.body_md5("/ping", "{}") + headers["Oopz-Time"]
    assert _signature_valid(old_pub, headers["Oopz-Sign"], message) is True
