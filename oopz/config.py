"""Oopz SDK 配置模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class SupportsSign(Protocol):
    """最小私钥协议。"""

    def sign(self, data: bytes, padding: object, algorithm: object) -> bytes:
        """执行签名。"""


@dataclass
class OopzConfig:
    """Oopz 平台连接所需的完整配置。

    必填字段：
        device_id, person_uid, jwt_token, private_key
    """

    device_id: str
    person_uid: str
    jwt_token: str

    # RSA 私钥：接受 PEM 字符串或已加载的 cryptography 私钥对象
    private_key: str | bytes | SupportsSign | None = None

    base_url: str = "https://gateway.oopz.cn"
    ws_url: str = "wss://ws.oopz.cn"
    app_version: str = "69514"
    channel: str = "Web"
    platform: str = "windows"
    web: bool = True

    default_area: str = ""
    default_channel: str = ""
    use_announcement_style: bool = True

    agora_app_id: str = "358eebceadb94c2a9fd91ecd7b341602"
    agora_init_timeout: int = 1800

    # 自动撤回
    auto_recall_enabled: bool = False
    auto_recall_delay: int = 30

    # 速率控制
    rate_limit_interval: float = 0.35
    request_timeout: float | tuple[float, float] = (10, 30)

    # 成员缓存
    area_members_cache_ttl: float = 15.0
    area_members_stale_ttl: float = 300.0
    query_cache_ttl: float = 15.0
    query_cache_stale_ttl: float = 300.0
    cache_max_entries: int = 200

    # 自定义请求头（留空则使用 DEFAULT_HEADERS）
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.device_id = self._require_non_empty(self.device_id, "device_id")
        self.person_uid = self._require_non_empty(self.person_uid, "person_uid")
        self.jwt_token = self._require_non_empty(self.jwt_token, "jwt_token")
        if self.private_key is None:
            raise ValueError("private_key 不能为空")

        self.default_area = str(self.default_area or "").strip()
        self.default_channel = str(self.default_channel or "").strip()
        self.headers = {
            str(key): str(value)
            for key, value in self.headers.items()
            if str(key).strip()
        }
        self._validate_timeouts()
        self._validate_cache_settings()

    @staticmethod
    def _require_non_empty(value: str, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} 不能为空")
        return text

    def _validate_timeouts(self) -> None:
        timeout = self.request_timeout
        if isinstance(timeout, tuple):
            if len(timeout) != 2 or any(float(item) <= 0 for item in timeout):
                raise ValueError("request_timeout 必须是正数或长度为 2 的正数元组")
            return
        if float(timeout) <= 0:
            raise ValueError("request_timeout 必须大于 0")

    def _validate_cache_settings(self) -> None:
        for field_name in (
            "area_members_cache_ttl",
            "area_members_stale_ttl",
            "query_cache_ttl",
            "query_cache_stale_ttl",
        ):
            value = float(getattr(self, field_name))
            if value <= 0:
                raise ValueError(f"{field_name} 必须大于 0")

    def require_default_area(self) -> str:
        """返回默认域，未配置则抛错。"""
        return self._require_non_empty(self.default_area, "default_area")

    def require_default_channel(self) -> str:
        """返回默认频道，未配置则抛错。"""
        return self._require_non_empty(self.default_channel, "default_channel")

    def get_headers(self) -> dict[str, str]:
        """返回实际使用的 HTTP 请求头。"""
        return self.headers if self.headers else dict(DEFAULT_HEADERS)


DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Content-Type": "application/json;charset=utf-8",
    "Origin": "https://web.oopz.cn",
    "Pragma": "no-cache",
    "Priority": "u=1, i",
    "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
}
