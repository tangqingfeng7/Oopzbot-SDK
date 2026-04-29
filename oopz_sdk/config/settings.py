"""Runtime configuration objects for the Oopz SDK."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

from .constants import DEFAULT_HEADERS


@dataclass
class RetryConfig:
    interval: float = 0.35
    timeout: float | tuple[float, float] = (10, 30)
    max_attempts: int = 3


@dataclass
class HeartbeatConfig:
    interval: float = 10.0
    reconnect_interval: float = 2.0
    max_reconnect_interval: float = 120.0


@dataclass
class ProxyConfig:
    http: str | None = None
    https: str | None = None
    websocket: str | None = None


@dataclass
class OopzConfig:
    device_id: str
    person_uid: str
    jwt_token: str
    private_key: Any = None

    base_url: str = "https://gateway.oopz.cn"
    ws_url: str = "wss://ws.oopz.cn"
    app_version: str = "69514"
    channel: str = "Web"
    platform: str = "windows"
    web: bool = True

    use_announcement_style: bool = False

    agora_app_id: str = "358eebceadb94c2a9fd91ecd7b341602"
    agora_init_timeout: int = 1800

    voice_backend: str = "browser"
    voice_browser_headless: bool = True
    voice_browser_executable_path: str = ""
    voice_agora_sdk_url: str = "https://download.agora.io/sdk/release/AgoraRTC_N.js"

    area_members_cache_ttl: float = 15.0
    area_members_stale_ttl: float = 300.0
    cache_max_entries: int = 200

    headers: dict[str, str] = field(default_factory=dict)
    retry: RetryConfig = field(default_factory=RetryConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)

    ignore_self_messages: bool = True   # 如果设置为False, 会导致bot接收到自己处理的消息, 可能导致死循环

    def __post_init__(self) -> None:
        self.device_id = self._require_non_empty(self.device_id, "device_id")
        self.person_uid = self._require_non_empty(self.person_uid, "person_uid")
        self.jwt_token = self._require_non_empty(self.jwt_token, "jwt_token")

        if self.private_key is None:
            raise ValueError("private_key is required")
        if isinstance(self.private_key, str) and not self.private_key.strip():
            raise ValueError("private_key is required")
        if isinstance(self.private_key, (bytes, bytearray)) and not self.private_key:
            raise ValueError("private_key is required")

    @staticmethod
    def _require_non_empty(value: str, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return text

    @classmethod
    def from_env(cls, prefix: str = "OOPZ_", **overrides: Any) -> "OopzConfig":
        """从环境变量创建配置。

        默认读取 `OOPZ_DEVICE_ID`、`OOPZ_PERSON_UID`、`OOPZ_JWT_TOKEN`
        和 `OOPZ_PRIVATE_KEY`。可通过关键字参数覆盖其他配置项。
        """
        values: dict[str, Any] = {
            "device_id": cls._require_env(f"{prefix}DEVICE_ID"),
            "person_uid": cls._require_env(f"{prefix}PERSON_UID"),
            "jwt_token": cls._require_env(f"{prefix}JWT_TOKEN"),
            "private_key": cls._require_env(f"{prefix}PRIVATE_KEY"),
        }
        app_version = os.environ.get(f"{prefix}APP_VERSION", "").strip()
        if app_version:
            values["app_version"] = app_version
        values.update(overrides)
        return cls(**values)

    @classmethod
    async def from_password_env(
        cls,
        *,
        phone_env: str = "OOPZ_LOGIN_PHONE",
        password_env: str = "OOPZ_LOGIN_PASSWORD",
        headless: bool = True,
        **kwargs: Any,
    ) -> "OopzConfig":
        """用环境变量中的 OOPZ 账号密码登录并创建配置。

        `kwargs` 会先传给 `login_with_password()`；其中 `config_overrides`
        可用于覆盖最终 `OopzConfig` 的字段。
        """
        from oopz_sdk.auth.password_login import login_with_password

        config_overrides = dict(kwargs.pop("config_overrides", {}) or {})
        credentials = await login_with_password(
            cls._require_env(phone_env),
            cls._require_env(password_env),
            headless=headless,
            **kwargs,
        )
        values: dict[str, Any] = {
            "device_id": credentials.device_id,
            "person_uid": credentials.person_uid,
            "jwt_token": credentials.jwt_token,
            "private_key": credentials.private_key_pem,
        }
        if credentials.app_version:
            values["app_version"] = credentials.app_version
        values.update(config_overrides)
        return cls(**values)

    @classmethod
    def from_password_env_sync(cls, **kwargs: Any) -> "OopzConfig":
        """`from_password_env()` 的同步包装，适合一次性脚本。"""
        return asyncio.run(cls.from_password_env(**kwargs))

    @staticmethod
    def _require_env(name: str) -> str:
        value = os.environ.get(name, "").strip()
        if not value:
            raise ValueError(f"{name} environment variable is required")
        return value

    @property
    def rate_limit_interval(self) -> float:
        return self.retry.interval

    @rate_limit_interval.setter
    def rate_limit_interval(self, value: float) -> None:
        self.retry.interval = value

    @property
    def request_timeout(self) -> float | tuple[float, float]:
        return self.retry.timeout

    @request_timeout.setter
    def request_timeout(self, value: float | tuple[float, float]) -> None:
        self.retry.timeout = value

    def get_headers(self) -> dict[str, str]:
        return {**DEFAULT_HEADERS, **self.headers}
