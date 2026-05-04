from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Protocol

from aiohttp import ClientConnectorError, ClientSession, WSMsgType, WSServerHandshakeError, web

JsonDict = dict[str, Any]
EventSink = Callable[[JsonDict], Awaitable[None] | None]

logger = logging.getLogger(__name__)


class OneBotV12AdapterProtocol(Protocol):
    platform: str
    self_id: str | int

    def add_event_sink(self, sink: EventSink) -> None: ...

    def remove_event_sink(self, sink: EventSink) -> None: ...

    async def call_action(
        self,
        action: str,
        params: Mapping[str, Any] | None = None,
        *,
        echo: Any = None,
    ) -> Mapping[str, Any]: ...

    async def call_action_payload(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def failed_response(self, retcode: int, message: str, *, echo: Any = None) -> JsonDict: ...

    def connect_event(self) -> JsonDict: ...


@dataclass(slots=True)
class OneBotV12ServerConfig:
    """OneBot v12 通信层配置。

    v12 暂时继续使用项目原来的统一入口：
    - HTTP action: /onebot/v12/{action}
    - HTTP payload: /onebot/v12
    - WebSocket: /onebot/v12
    - HTTP webhook / reverse WebSocket: 统一事件与 action 连接
    """

    host: str = "127.0.0.1"
    port: int = 6727
    path_prefix: str = "/onebot"
    version: str = "v12"

    access_token: str = ""

    enable_http: bool = True
    enable_ws: bool = True

    webhook_urls: list[str] = field(default_factory=list)
    ws_reverse_urls: list[str] = field(default_factory=list)
    ws_reverse_reconnect_interval: float = 3.0

    send_connect_event: bool = True


class OneBotV12Server:
    """OneBot v12 server。
    """

    def __init__(
        self,
        adapter: OneBotV12AdapterProtocol,
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

    async def start(self) -> None:
        if self._started:
            return

        self._started = True
        self.adapter.add_event_sink(self.broadcast_event)
        self._session = ClientSession()

        if self.config.enable_http or self.config.enable_ws:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, host=self.config.host, port=self.config.port)
            await self.site.start()
            logger.info(
                "OneBot v12 server started at http://%s:%s%s",
                self.config.host,
                self.config.port,
                self._base_path(),
            )

        for url in self.config.ws_reverse_urls:
            self._reverse_tasks.append(asyncio.create_task(self._reverse_ws_loop(url)))

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

    def _setup_routes(self) -> None:
        base = self._base_path()

        if self.config.enable_http:
            self.app.router.add_post(base + "/{action}", self._handle_http_action)
            self.app.router.add_get(base + "/{action}", self._handle_http_action)
            self.app.router.add_get(base + "/{action}/", self._handle_http_action)
            self.app.router.add_post(base + "/{action}/", self._handle_http_action)
            self.app.router.add_post(base, self._handle_http_action_payload)
            self.app.router.add_get(base + "/status", self._handle_status)

        if self.config.enable_ws:
            self.app.router.add_get(base, self._handle_ws)

    async def _handle_http_action(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return self._json_response(self._failed(1401, "unauthorized"), status=401)

        action = request.match_info.get("action", "")
        body = await self._read_json(request)
        if not isinstance(body, Mapping):
            return self._json_response(self._failed(1400, "request body must be object"))

        return self._json_response(await self.adapter.call_action(action, body))

    async def _handle_http_action_payload(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return self._json_response(self._failed(1401, "unauthorized"), status=401)

        body = await self._read_json(request)
        if not isinstance(body, Mapping):
            return self._json_response(self._failed(1400, "request body must be object"))

        return self._json_response(await self.adapter.call_action_payload(body))

    async def _handle_status(self, request: web.Request) -> web.Response:
        if not self._check_auth(request):
            return self._json_response(self._failed(1401, "unauthorized"), status=401)
        return self._json_response(await self.adapter.call_action("get_status"))

    async def _handle_ws(self, request: web.Request) -> web.StreamResponse:
        if not self._check_auth(request):
            return self._json_response(self._failed(1401, "unauthorized"), status=401)

        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._ws_clients.add(ws)
        logger.info("OneBot v12 forward WebSocket connected")

        try:
            if self.config.send_connect_event:
                await ws.send_json(self._connect_event())

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await ws.send_json(await self._handle_ws_text(msg.data))
                elif msg.type == WSMsgType.BINARY:
                    try:
                        text = msg.data.decode("utf-8")
                    except UnicodeDecodeError:
                        await ws.send_json(self._failed(1400, "binary payload must be utf-8 json"))
                        continue
                    await ws.send_json(await self._handle_ws_text(text))
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
            return self._failed(1400, "invalid json")
        if not isinstance(payload, Mapping):
            return self._failed(1400, "payload must be object")
        return await self.adapter.call_action_payload(payload)

    async def _reverse_ws_loop(self, url: str) -> None:
        failures = 0

        while self._started:
            try:
                await self._connect_reverse_ws(url)
                failures = 0
            except asyncio.CancelledError:
                raise
            except ClientConnectorError as exc:
                failures += 1
                if failures == 1:
                    logger.warning(
                        "OneBot v12 reverse WebSocket is not reachable: %s (%s). Will retry in %ss.",
                        url,
                        exc.os_error or exc,
                        self.config.ws_reverse_reconnect_interval,
                    )
                else:
                    logger.debug(
                        "OneBot v12 reverse WebSocket still unreachable: %s (%s). retry=%s",
                        url,
                        exc.os_error or exc,
                        failures,
                    )
            except WSServerHandshakeError as exc:
                failures += 1
                logger.warning(
                    "OneBot v12 reverse WebSocket handshake failed: %s status=%s message=%s. Will retry in %ss.",
                    url,
                    exc.status,
                    exc.message,
                    self.config.ws_reverse_reconnect_interval,
                )
            except Exception:
                failures += 1
                logger.exception("OneBot v12 reverse WebSocket unexpected error: %s", url)

            if self._started:
                await asyncio.sleep(self.config.ws_reverse_reconnect_interval)

    async def _connect_reverse_ws(self, url: str) -> None:
        if self._session is None:
            raise RuntimeError("ClientSession is not initialized")

        logger.info("connecting OneBot v12 reverse WebSocket: %s", url)
        async with self._session.ws_connect(
            url,
            headers=self._reverse_ws_headers(),
            heartbeat=30,
        ) as ws:
            logger.info("OneBot v12 reverse WebSocket connected: %s", url)

            async def reverse_sink(event: JsonDict) -> None:
                await ws.send_json(event)

            self.adapter.add_event_sink(reverse_sink)
            try:
                if self.config.send_connect_event:
                    await ws.send_json(self._connect_event())

                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        await ws.send_json(await self._handle_ws_text(msg.data))
                    elif msg.type == WSMsgType.BINARY:
                        try:
                            text = msg.data.decode("utf-8")
                        except UnicodeDecodeError:
                            await ws.send_json(self._failed(1400, "binary payload must be utf-8 json"))
                            continue
                        await ws.send_json(await self._handle_ws_text(text))
                    elif msg.type == WSMsgType.ERROR:
                        logger.warning("OneBot v12 reverse WebSocket error: %s", ws.exception())
                        break
            finally:
                self.adapter.remove_event_sink(reverse_sink)
                logger.info("OneBot v12 reverse WebSocket disconnected: %s", url)

    async def broadcast_event(self, event: JsonDict) -> None:
        await self._broadcast_ws(event)
        await self._broadcast_webhook(event)

    async def _broadcast_ws(self, event: JsonDict) -> None:
        closed: list[web.WebSocketResponse] = []
        for ws in list(self._ws_clients):
            if ws.closed:
                closed.append(ws)
                continue
            try:
                await ws.send_json(event)
            except Exception:
                logger.exception("failed to send OneBot v12 event to WebSocket")
                closed.append(ws)
        for ws in closed:
            self._ws_clients.discard(ws)

    async def _broadcast_webhook(self, event: JsonDict) -> None:
        if not self.config.webhook_urls or self._session is None:
            return
        headers = {"Content-Type": "application/json", **self._auth_headers()}
        for url in self.config.webhook_urls:
            try:
                async with self._session.post(url, json=event, headers=headers) as resp:
                    if resp.status >= 400:
                        text = await resp.text()
                        logger.warning("OneBot v12 webhook failed: url=%s status=%s body=%s", url, resp.status, text[:500])
            except Exception:
                logger.exception("OneBot v12 webhook request failed: %s", url)

    def _base_path(self) -> str:
        prefix = "/" + str(self.config.path_prefix or "/onebot").strip("/")
        version = str(self.config.version or "").strip("/")
        return f"{prefix}/{version}" if version else prefix

    def _failed(self, retcode: int, message: str, *, echo: Any = None) -> JsonDict:
        maker = getattr(self.adapter, "failed_response", None)
        if callable(maker):
            return maker(retcode, message, echo=echo)
        resp: JsonDict = {"status": "failed", "retcode": retcode, "data": None, "message": message}
        if echo is not None:
            resp["echo"] = echo
        return resp

    def _connect_event(self) -> JsonDict:
        maker = getattr(self.adapter, "connect_event", None)
        if callable(maker):
            return maker()
        return {
            "id": f"oopz.meta.connect.{time.time_ns()}",
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

    def _reverse_ws_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "User-Agent": "OneBot/12 (oopz) oopz_sdk/0.1.0",
            "Sec-WebSocket-Protocol": "12.oopz_sdk",
        }
        if self.config.access_token:
            headers["Authorization"] = f"Bearer {self.config.access_token}"
        return headers

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
        if auth in {f"Bearer {token}", f"Token {token}"}:
            return True
        if request.query.get("access_token", "") == token:
            return True
        protocols = request.headers.get("Sec-WebSocket-Protocol", "")
        return bool(token and token in protocols)

    def _auth_headers(self) -> dict[str, str]:
        if not self.config.access_token:
            return {}
        return {"Authorization": f"Bearer {self.config.access_token}"}

    @staticmethod
    def _json_response(data: Any, *, status: int = 200) -> web.Response:
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            status=status,
            content_type="application/json",
        )
