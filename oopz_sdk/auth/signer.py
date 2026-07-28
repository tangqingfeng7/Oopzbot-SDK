from __future__ import annotations

import base64
import hashlib
from dataclasses import replace
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions.auth import OopzAuthError

from .ids import ClientMessageIdGenerator, request_id, timestamp_ms, timestamp_us


class Signer:
    def __init__(self, config: OopzConfig):
        self._config = config
        self.private_key = self._resolve_key(config.private_key)
        self.id_gen = ClientMessageIdGenerator()

    @classmethod
    def from_pem(cls, pem: str | bytes, config: OopzConfig) -> "Signer":
        if isinstance(pem, str):
            pem = pem.encode("utf-8")
        key = serialization.load_pem_private_key(pem, password=None, backend=default_backend())
        config_copy = replace(config, private_key=key)
        return cls(config_copy)

    @staticmethod
    def _resolve_key(key_input: Any):
        if key_input is None:
            # OopzConfig 会提前拦住这个情况；这里兜底防止被绕开导致拿到一把服务端根本不认的随机密钥。
            raise OopzAuthError("private_key is required")
        if isinstance(key_input, (str, bytes)):
            raw = key_input.encode("utf-8") if isinstance(key_input, str) else key_input
            try:
                return serialization.load_pem_private_key(raw, password=None, backend=default_backend())
            except Exception as exc:
                raise OopzAuthError(f"无法加载 PEM 私钥: {exc}") from exc
        if hasattr(key_input, "sign"):
            return key_input
        raise OopzAuthError(f"不支持的 private_key 类型: {type(key_input)}")

    def sign(self, data: str) -> str:
        sig = self.private_key.sign(
            data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(sig).decode("utf-8")

    def client_message_id(self) -> str:
        return self.id_gen.generate()

    @staticmethod
    def request_id() -> str:
        return request_id()

    @staticmethod
    def timestamp_ms() -> str:
        return timestamp_ms()

    @staticmethod
    def timestamp_us() -> str:
        return timestamp_us()

    def body_md5(self, url_path: str, body_str: str) -> str:
        return hashlib.md5((url_path + body_str).encode("utf-8")).hexdigest()
