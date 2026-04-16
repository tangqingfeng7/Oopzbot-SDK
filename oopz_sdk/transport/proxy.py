from __future__ import annotations

from oopz_sdk.config.settings import ProxyConfig


def build_requests_proxies(config: ProxyConfig) -> dict[str, str]:
    proxies: dict[str, str] = {}
    if config.http:
        proxies["http"] = config.http
    if config.https:
        proxies["https"] = config.https
    return proxies


def build_websocket_proxy(config: ProxyConfig) -> str | None:
    return config.websocket or config.https or config.http
