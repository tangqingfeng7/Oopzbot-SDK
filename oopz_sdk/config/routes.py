"""官方 HTTP 网关与 WebSocket 线路的配对关系。"""

DEFAULT_BASE_URL = "https://gateway.oopz.cn"
DEFAULT_WS_URL = "wss://ws.oopz.cn"

OFFICIAL_WS_ROUTES = {
    DEFAULT_BASE_URL: DEFAULT_WS_URL,
    "https://gateway1.oopz.cn": "wss://ws1.oopz.cn",
    "https://gateway2.oopz.cn": "wss://ws2.oopz.cn",
    "https://gateway-web1.oopz.cn": "wss://ws-web1.oopz.cn",
}


def resolve_ws_url(base_url: str, ws_url: str = "") -> str:
    """显式地址优先；仅对已知官方网关推导配套的事件线路。"""
    explicit = str(ws_url or "").strip()
    if explicit:
        return explicit
    base = str(base_url or "").strip().rstrip("/")
    return OFFICIAL_WS_ROUTES.get(base, DEFAULT_WS_URL)
