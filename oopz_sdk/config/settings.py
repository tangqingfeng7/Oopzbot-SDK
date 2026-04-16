"""Runtime configuration objects for the Oopz SDK."""

from __future__ import annotations

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
class AutoRecallConfig:
    enabled: bool = False
    delay: int = 30


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

    default_area: str = ""
    default_channel: str = ""
    use_announcement_style: bool = False

    agora_app_id: str = "358eebceadb94c2a9fd91ecd7b341602"
    agora_init_timeout: int = 1800

    area_members_cache_ttl: float = 15.0
    area_members_stale_ttl: float = 300.0
    cache_max_entries: int = 200

    headers: dict[str, str] = field(default_factory=dict)
    retry: RetryConfig = field(default_factory=RetryConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    auto_recall: AutoRecallConfig = field(default_factory=AutoRecallConfig)

    ignore_self_messages: bool = True   # 如果设置为False, 会导致bot接收到自己处理的消息, 可能导致死循环

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

    @property
    def auto_recall_enabled(self) -> bool:
        return self.auto_recall.enabled

    @auto_recall_enabled.setter
    def auto_recall_enabled(self, value: bool) -> None:
        self.auto_recall.enabled = value

    @property
    def auto_recall_delay(self) -> int:
        return self.auto_recall.delay

    @auto_recall_delay.setter
    def auto_recall_delay(self, value: int) -> None:
        self.auto_recall.delay = value

    def get_headers(self) -> dict[str, str]:
        return self.headers if self.headers else dict(DEFAULT_HEADERS)
