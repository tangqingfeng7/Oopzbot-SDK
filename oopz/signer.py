"""Oopz API 请求签名器。"""

from __future__ import annotations

import base64
import hashlib
import random
import time
import uuid
from typing import Any, Dict

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .config import OopzConfig
from .exceptions import OopzAuthError


class ClientMessageIdGenerator:
    """生成 15 位客户端消息 ID（模拟真实格式）。"""

    def generate(self) -> str:
        timestamp_us = int(time.time() * 1_000_000)
        base_id = timestamp_us % 10_000_000_000_000
        suffix = random.randint(10, 99)
        return str(base_id * 100 + suffix)


class Signer:
    """Oopz API 请求签名器。

    Args:
        config: SDK 配置，包含 private_key / person_uid / device_id 等。
    """

    def __init__(self, config: OopzConfig):
        self._config = config
        self.private_key = self._resolve_key(config.private_key)
        self.id_gen = ClientMessageIdGenerator()

    @classmethod
    def from_pem(cls, pem: str | bytes, config: OopzConfig) -> Signer:
        """从 PEM 字符串或字节创建 Signer。"""
        config_copy = config
        if isinstance(pem, str):
            pem = pem.encode("utf-8")
        key = serialization.load_pem_private_key(pem, password=None, backend=default_backend())
        # 直接赋值到 config 的 private_key 字段
        object.__setattr__(config_copy, "private_key", key)
        return cls(config_copy)

    @staticmethod
    def _resolve_key(key_input: Any):
        """将 PEM 字符串、字节或已加载的 key 对象统一为 RSA 私钥。"""
        if key_input is None:
            raise OopzAuthError("private_key 未配置")

        if isinstance(key_input, (str, bytes)):
            raw = key_input.encode("utf-8") if isinstance(key_input, str) else key_input
            try:
                return serialization.load_pem_private_key(raw, password=None, backend=default_backend())
            except Exception as exc:
                raise OopzAuthError(f"无法加载 PEM 私钥: {exc}") from exc

        # 假设已经是 cryptography 的私钥对象
        if hasattr(key_input, "sign"):
            return key_input

        raise OopzAuthError(f"不支持的 private_key 类型: {type(key_input)}")

    # -- ID / 时间戳 --

    @staticmethod
    def request_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def timestamp_ms() -> str:
        return str(int(time.time() * 1000))

    @staticmethod
    def timestamp_us() -> str:
        return str(int(time.time() * 1_000_000))

    def client_message_id(self) -> str:
        return self.id_gen.generate()

    # -- 签名 --

    def sign(self, data: str) -> str:
        """RSA PKCS1v15 + SHA256 签名，返回 Base64。"""
        sig = self.private_key.sign(
            data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(sig).decode("utf-8")

    def oopz_headers(self, url_path: str, body_str: str) -> Dict[str, str]:
        """构造 Oopz 专用签名请求头。"""
        ts = self.timestamp_ms()
        md5 = hashlib.md5((url_path + body_str).encode("utf-8")).hexdigest()
        signature = self.sign(md5 + ts)

        cfg = self._config
        return {
            "Oopz-Sign": signature,
            "Oopz-Request-Id": self.request_id(),
            "Oopz-Time": ts,
            "Oopz-App-Version-Number": cfg.app_version,
            "Oopz-Channel": cfg.channel,
            "Oopz-Device-Id": cfg.device_id,
            "Oopz-Platform": cfg.platform,
            "Oopz-Web": str(cfg.web).lower(),
            "Oopz-Person": cfg.person_uid,
            "Oopz-Signature": cfg.jwt_token,
        }
