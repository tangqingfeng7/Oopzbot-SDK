from __future__ import annotations

import json
import logging
import aiohttp

from oopz_sdk.config.settings import OopzConfig, ProxyConfig
from .proxy import build_aiohttp_proxy

logger = logging.getLogger("oopz_sdk.transport.websocket")


class WebSocketClosedError(ConnectionError):
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

        self._ws = await self._session.ws_connect(
            self.config.ws_url,
            proxy=proxy,
            heartbeat=None,
            autoping=True,
        )

    async def recv(self) -> str:
        if self._ws is None:
            raise RuntimeError("WebSocket 未连接")

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

        raise RuntimeError(f"未知 WebSocket 消息类型: {msg.type}")

    async def send_json(self, data: dict) -> None:
        if self._ws is None:
            raise RuntimeError("WebSocket 未连接")
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
