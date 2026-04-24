from __future__ import annotations

from oopz_sdk.config.settings import ProxyConfig
from urllib.parse import urlparse


# 历史遗留：返回 `{"http": ..., "https": ...}` 形状，原本给 `requests.Session.proxies`
# 使用。0.7.0 起 SDK 内部已全部改走 aiohttp，`build_aiohttp_proxy` 才是现役入口；
# 这里仅为保持公开 API 兼容性保留，新代码请直接用 `build_aiohttp_proxy`。
def build_requests_proxies(config: ProxyConfig) -> dict[str, str]:
    proxies: dict[str, str] = {}
    if config.http:
        proxies["http"] = config.http
    if config.https:
        proxies["https"] = config.https
    return proxies


def build_websocket_proxy(config: ProxyConfig) -> str | None:
    return config.websocket or config.https or config.http


def build_aiohttp_proxy(url: str, config: ProxyConfig) -> str | None:
    scheme = urlparse(url).scheme.lower()
    if scheme == "https":
        return config.https or config.http
    if scheme == "http":
        return config.http
    return None
