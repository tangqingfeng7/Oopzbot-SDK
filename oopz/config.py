"""Oopz SDK 配置模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    private_key: Any = None

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
    cache_max_entries: int = 200

    # 自定义请求头（留空则使用 DEFAULT_HEADERS）
    headers: dict[str, str] = field(default_factory=dict)

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
