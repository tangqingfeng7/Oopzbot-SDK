from __future__ import annotations

from oopz_sdk.config.settings import ProxyConfig
from urllib.parse import urlparse


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
