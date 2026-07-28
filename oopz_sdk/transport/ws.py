from __future__ import annotations

import json
import logging
import aiohttp

from oopz_sdk.config.settings import OopzConfig, ProxyConfig
from oopz_sdk.exceptions import (
    AUTH_FAILURE_STATUS_CODES,
    OopzAuthError,
    OopzConnectionError,
    OopzTransportError,
)
from .proxy import build_aiohttp_proxy

logger = logging.getLogger(__name__)


class WebSocketClosedError(OopzTransportError):
    """WebSocket 连接被关闭。

    归入 ``OopzTransportError`` 谱系（与 HTTP 层的 ``OopzConnectionError`` 一致），
    使调用方可用单一 SDK 传输异常基类捕获所有传输层错误，而非混用内置
    ``ConnectionError``。
    """

    def __init__(self, *, code: int | None, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


class WebSocketTransport:
    def __init__(self, config: OopzConfig):
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None

    async def connect(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.config.get_headers())

        proxy = build_aiohttp_proxy(self.config.ws_url, getattr(self.config, "proxy", ProxyConfig()))

        try:
            self._ws = await self._session.ws_connect(
                self.config.ws_url,
                proxy=proxy,
                heartbeat=None,
                autoping=True,
            )
        except aiohttp.WSServerHandshakeError as exc:
            # 服务端在握手阶段直接以 401/428 拒绝失效 token：升级为 OopzAuthError，
            # 让上层（OopzWSClient）尝试续期恢复或上报停机，避免持死 token 无限重连。
            if exc.status in AUTH_FAILURE_STATUS_CODES:
                raise OopzAuthError(
                    f"WebSocket 握手鉴权失败 (HTTP {exc.status}): {exc.message}",
                    status_code=exc.status,
                ) from exc
            # 其余握手失败统一包装为 OopzConnectionError，与 HTTP 传输层一致，
            # 对外暴露稳定的 SDK 异常类型而非泄漏 aiohttp 内部异常。
            raise OopzConnectionError(
                f"WebSocket 握手失败 (HTTP {exc.status}): {exc.message}"
            ) from exc
        except aiohttp.ClientError as exc:
            raise OopzConnectionError(f"WebSocket 连接失败: {exc}") from exc

    async def recv(self) -> str:
        if self._ws is None:
            raise RuntimeError("WebSocket is not connected")

        msg = await self._ws.receive()

        if msg.type == aiohttp.WSMsgType.TEXT:
            return msg.data

        if msg.type == aiohttp.WSMsgType.BINARY:
            return msg.data.decode("utf-8")

        if msg.type == aiohttp.WSMsgType.ERROR:
            raise RuntimeError(f"WebSocket error: {self._ws.exception()}")

        if msg.type == aiohttp.WSMsgType.CLOSE:
            raise WebSocketClosedError(
                code=msg.data if isinstance(msg.data, int) else self._ws.close_code,
                reason=msg.extra or "connection closed",
            )

        if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
            raise WebSocketClosedError(
                code=self._ws.close_code,
                reason="connection closed",
            )

        raise RuntimeError(f"Unknown webSocket message type: {msg.type}")

    async def send_json(self, data: dict) -> None:
        if self._ws is None:
            raise RuntimeError("WebSocket is not connected")
        await self._ws.send_str(json.dumps(data, ensure_ascii=False))

    async def close(self) -> None:
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None

        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    @property
    def closed(self) -> bool:
        return self._ws is None or self._ws.closed
