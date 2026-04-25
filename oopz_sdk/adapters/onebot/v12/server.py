from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import parse_qs

from aiohttp import ClientSession, WSMsgType, web

from .adapter import OneBotV12Adapter
from .types import JsonDict, failed

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OneBotV12ServerConfig:
    """
    OneBot v12 通信层配置。

    支持：
    - HTTP Action
    - 正向 WebSocket
    - 反向 WebSocket
    - HTTP Webhook

    路径默认同时兼容：
    - /onebot/v12
    - /onebot/v12/{action}
    - /{platform}/{self_id}/onebot/v12
    - /{platform}/{self_id}/onebot/v12/{action}
    """

    host: str = "127.0.0.1"
    port: int = 6727

    access_token: str = ""

    enable_http: bool = True
    enable_ws: bool = True

    # HTTP Webhook：事件发生后 POST 到这些 URL
    webhook_urls: list[str] = field(default_factory=list)

    # 反向 WebSocket：启动后主动连接这些 URL
    ws_reverse_urls: list[str] = field(default_factory=list)
    ws_reverse_reconnect_interval: float = 3.0

    # 是否在 WebSocket 连接建立后发送 connect meta event
    send_connect_event: bool = True


class OneBotV12Server:
    """
    OneBot v12 协议 Server。

    这个类只负责通信层，不负责 Oopz 事件解析，也不负责 OneBot action 的实际业务。
    实际业务都交给 OneBotV12Adapter：

    - action 请求 -> adapter.call_action_payload()
    - Oopz 事件 -> adapter.handle_oopz_event()
    - 事件广播 -> adapter.add_event_sink(self.broadcast_event)
    """

    def __init__(
        self,
        adapter: OneBotV12Adapter,
        config: OneBotV12ServerConfig | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config or OneBotV12ServerConfig()

        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

        self._ws_clients: set[web.WebSocketResponse] = set()
        self._session: ClientSession | None = None
        self._reverse_tasks: list[asyncio.Task[None]] = []
        self._started = False

        self._setup_routes()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._started:
            return

        self._started = True
        self.adapter.add_event_sink(self.broadcast_event)

        self._session = ClientSession()

        if self.config.enable_http or self.config.enable_ws:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(
                self.runner,
                host=self.config.host,
                port=self.config.port,
            )
            await self.site.start()

            logger.info(
                "OneBot v12 server started at http://%s:%s",
                self.config.host,
                self.config.port,
            )

        for url in self.config.ws_reverse_urls:
            task = asyncio.create_task(self._reverse_ws_loop(url))
            self._reverse_tasks.append(task)

    async def stop(self) -> None:
        if not self._started:
            return

        self._started = False
        self.adapter.remove_event_sink(self.broadcast_event)

        for task in self._reverse_tasks:
            task.cancel()

        if self._reverse_tasks:
            await asyncio.gather(*self._reverse_tasks, return_exceptions=True)

        self._reverse_tasks.clear()

        for ws in list(self._ws_clients):
            await ws.close()

        self._ws_clients.clear()

        if self._session is not None:
            await self._session.close()
            self._session = None

        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
            self.site = None

        logger.info("OneBot v12 server stopped")

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def _setup_routes(self) -> None:
        # HTTP Action
        self.app.router.add_post("/onebot/v12/{action}", self._handle_http_action)
        self.app.router.add_post(
            "/{platform}/{self_id}/onebot/v12/{action}",
            self._handle_http_action,
        )

        # 允许 action 放在 body 里
        self.app.router.add_post("/onebot/v12", self._handle_http_action_payload)
        self.app.router.add_post(
            "/{platform}/{self_id}/onebot/v12",
            self._handle_http_action_payload_or_ws,
        )

        # 正向 WebSocket
        self.app.router.add_get("/onebot/v12", self._handle_ws)
        self.app.router.add_get("/{platform}/{self_id}/onebot/v12", self._handle_ws)

        # 健康检查
        self.app.router.add_get("/onebot/v12/status", self._handle_status)

    # ------------------------------------------------------------------
    # HTTP Action
    # ------------------------------------------------------------------

    async def _handle_http_action(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return self._json_response(failed(1401, "unauthorized"), status=401)

        action = request.match_info.get("action", "")
        body = await self._read_json(request)

        if not isinstance(body, Mapping):
            return self._json_response(failed(1400, "request body must be object"))

        response = await self.adapter.call_action(action, body)
        return self._json_response(response)

    async def _handle_http_action_payload(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return self._json_response(failed(1401, "unauthorized"), status=401)

        body = await self._read_json(request)

        if not isinstance(body, Mapping):
            return self._json_response(failed(1400, "request body must be object"))

        response = await self.adapter.call_action_payload(body)
        return self._json_response(response)

    async def _handle_http_action_payload_or_ws(self, request: web.Request) -> web.StreamResponse:
        if self._is_websocket_request(request):
            return await self._handle_ws(request)

        return await self._handle_http_action_payload(request)

    async def _handle_status(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return self._json_response(failed(1401, "unauthorized"), status=401)

        response = await self.adapter.call_action("get_status")
        return self._json_response(response)

    # ------------------------------------------------------------------
    # Forward WebSocket
    # ------------------------------------------------------------------

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        if not self._check_auth(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json(failed(1401, "unauthorized"))
            await ws.close()
            return ws

        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)

        self._ws_clients.add(ws)
        logger.info("OneBot v12 forward WebSocket connected")

        try:
            if self.config.send_connect_event:
                await ws.send_json(self._connect_event())

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    response = await self._handle_ws_text(msg.data)
                    await ws.send_json(response)

                elif msg.type == WSMsgType.BINARY:
                    try:
                        text = msg.data.decode("utf-8")
                    except UnicodeDecodeError:
                        await ws.send_json(failed(1400, "binary payload must be utf-8 json"))
                        continue

                    response = await self._handle_ws_text(text)
                    await ws.send_json(response)

                elif msg.type == WSMsgType.ERROR:
                    logger.warning("OneBot v12 WebSocket error: %s", ws.exception())
                    break

        finally:
            self._ws_clients.discard(ws)
            logger.info("OneBot v12 forward WebSocket disconnected")

        return ws

    async def _handle_ws_text(self, text: str) -> JsonDict:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return failed(1400, "invalid json")

        if not isinstance(payload, Mapping):
            return failed(1400, "payload must be object")

        return await self.adapter.call_action_payload(payload)

    # ------------------------------------------------------------------
    # Reverse WebSocket
    # ------------------------------------------------------------------

    async def _reverse_ws_loop(self, url: str) -> None:
        while self._started:
            try:
                await self._connect_reverse_ws(url)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("OneBot v12 reverse WebSocket failed: %s", url)

            if self._started:
                await asyncio.sleep(self.config.ws_reverse_reconnect_interval)

    async def _connect_reverse_ws(self, url: str) -> None:
        if self._session is None:
            raise RuntimeError("ClientSession is not initialized")

        headers = self._auth_headers()
        logger.info("connecting OneBot v12 reverse WebSocket: %s", url)

        async with self._session.ws_connect(url, headers=headers, heartbeat=30) as ws:
            logger.info("OneBot v12 reverse WebSocket connected: %s", url)

            async def reverse_sink(event: JsonDict) -> None:
                await ws.send_json(event)

            self.adapter.add_event_sink(reverse_sink)

            try:
                if self.config.send_connect_event:
                    await ws.send_json(self._connect_event())

                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        response = await self._handle_ws_text(msg.data)
                        await ws.send_json(response)

                    elif msg.type == WSMsgType.BINARY:
                        try:
                            text = msg.data.decode("utf-8")
                        except UnicodeDecodeError:
                            await ws.send_json(failed(1400, "binary payload must be utf-8 json"))
                            continue

                        response = await self._handle_ws_text(text)
                        await ws.send_json(response)

                    elif msg.type == WSMsgType.ERROR:
                        logger.warning(
                            "OneBot v12 reverse WebSocket error: %s",
                            ws.exception(),
                        )
                        break
            finally:
                self.adapter.remove_event_sink(reverse_sink)
                logger.info("OneBot v12 reverse WebSocket disconnected: %s", url)

    # ------------------------------------------------------------------
    # Event broadcast
    # ------------------------------------------------------------------

    async def broadcast_event(self, event: JsonDict) -> None:
        """
        被 adapter.handle_oopz_event(event) 间接调用。

        事件会同时推给：
        - 正向 WebSocket 客户端
        - HTTP Webhook URL
        - 反向 WebSocket sink 在 _connect_reverse_ws() 里单独注册
        """
        await self._broadcast_ws(event)
        await self._broadcast_webhook(event)

    async def _broadcast_ws(self, event: JsonDict) -> None:
        if not self._ws_clients:
            return

        closed: list[web.WebSocketResponse] = []

        for ws in list(self._ws_clients):
            if ws.closed:
                closed.append(ws)
                continue

            try:
                await ws.send_json(event)
            except Exception:
                logger.exception("failed to send OneBot event to WebSocket")
                closed.append(ws)

        for ws in closed:
            self._ws_clients.discard(ws)

    async def _broadcast_webhook(self, event: JsonDict) -> None:
        if not self.config.webhook_urls:
            return

        if self._session is None:
            return

        headers = {
            "Content-Type": "application/json",
            **self._auth_headers(),
        }

        for url in self.config.webhook_urls:
            try:
                async with self._session.post(url, json=event, headers=headers) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        logger.warning(
                            "OneBot webhook failed: url=%s status=%s body=%s",
                            url,
                            resp.status,
                            text[:500],
                        )
            except Exception:
                logger.exception("OneBot webhook request failed: %s", url)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _connect_event(self) -> JsonDict:
        return {
            "id": f"oopz.meta.connect.{time.time_ns()}",
            "self": {
                "platform": self.adapter.platform,
                "user_id": self.adapter.self_id,
            },
            "time": time.time(),
            "type": "meta",
            "detail_type": "connect",
            "sub_type": "",
            "version": {
                "impl": "oopz_sdk",
                "version": "0.1.0",
                "onebot_version": "12",
            },
        }

    async def _read_json(self, request: web.Request) -> Any:
        if not request.can_read_body:
            return {}

        try:
            return await request.json()
        except Exception:
            text = await request.text()
            if not text.strip():
                return {}

            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return None

    def _check_auth(self, request: web.Request) -> bool:
        token = self.config.access_token
        if not token:
            return True

        auth = request.headers.get("Authorization", "")
        if auth == f"Bearer {token}":
            return True

        if auth == f"Token {token}":
            return True

        query_token = request.query.get("access_token", "")
        if query_token == token:
            return True

        # WebSocket 有些客户端会把 token 放在 Sec-WebSocket-Protocol，
        # 这里只做宽松兼容，不强依赖。
        protocols = request.headers.get("Sec-WebSocket-Protocol", "")
        if token and token in protocols:
            return True

        return False

    def _auth_headers(self) -> dict[str, str]:
        if not self.config.access_token:
            return {}

        return {
            "Authorization": f"Bearer {self.config.access_token}",
        }

    @staticmethod
    def _is_websocket_request(request: web.Request) -> bool:
        upgrade = request.headers.get("Upgrade", "").lower()
        connection = request.headers.get("Connection", "").lower()
        return upgrade == "websocket" or "upgrade" in connection

    @staticmethod
    def _json_response(data: Any, *, status: int = 200) -> web.Response:
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            status=status,
            content_type="application/json",
        )

#
# async def run_onebot_v12_server(
#     adapter: OneBotV12Adapter,
#     config: OneBotV12ServerConfig | None = None,
# ) -> OneBotV12Server:
#     """
#     方便外部快速启动：
#
#     server = await run_onebot_v12_server(bot.onebot_v12)
#     """
#     server = OneBotV12Server(adapter, config)
#     await server.start()
#     return server