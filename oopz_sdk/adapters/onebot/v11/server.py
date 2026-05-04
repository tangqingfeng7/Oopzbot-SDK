from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Mapping, Protocol

from aiohttp import ClientConnectorError, ClientSession, WSMsgType, WSServerHandshakeError, web

JsonDict = dict[str, Any]
EventSink = Callable[[JsonDict], Awaitable[None] | None]
WsRole = Literal["api", "event", "universal"]

logger = logging.getLogger(__name__)


class OneBotV11AdapterProtocol(Protocol):
    self_id: int | str

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
class OneBotV11ServerConfig:
    """OneBot v11 通信层配置。


    - HTTP action: /:action 和 /:action/
    - 正向 WebSocket: /api, /event, /
    - HTTP POST: 事件上报 URL
    - 反向 WebSocket: API / Event / Universal 三类客户端
    """

    host: str = "127.0.0.1"
    port: int = 6700

    access_token: str = ""
    secret: str = ""

    enable_http: bool = True
    enable_ws: bool = True
    enable_http_post: bool = True
    enable_ws_reverse: bool = True

    # HTTP POST，上报地址
    http_post_urls: list[str] = field(default_factory=list)
    http_post_timeout: float = 0.0

    # 反向 WS。ws_reverse_url 是共用 URL；api/event 为空时回退到共用 URL。
    ws_reverse_url: str = ""
    ws_reverse_api_url: str = ""
    ws_reverse_event_url: str = ""
    ws_reverse_use_universal_client: bool = False
    ws_reverse_reconnect_interval: float = 3.0

    send_connect_event: bool = True


class OneBotV11Server:
    """OneBot v11 独立 server。

    不复用 v12 server 的路径和角色模型，避免把 v11 做成 /onebot/v11 单入口。
    """

    def __init__(
        self,
        adapter: OneBotV11AdapterProtocol,
        config: OneBotV11ServerConfig | None = None,
    ) -> None:
        self.adapter = adapter
        self.config = config or OneBotV11ServerConfig()

        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

        self._session: ClientSession | None = None
        self._started = False
        self._reverse_tasks: list[asyncio.Task[None]] = []
        self._ws_clients: dict[web.WebSocketResponse, WsRole] = {}

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
                "OneBot v11 server started at http://%s:%s",
                self.config.host,
                self.config.port,
            )

        if self.config.enable_ws_reverse:
            for url, role in self._reverse_targets():
                task = asyncio.create_task(self._reverse_ws_loop(url, role))
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

        logger.info("OneBot v11 server stopped")

    # ------------------------------------------------------------------
    # routes
    # ------------------------------------------------------------------

    def _setup_routes(self) -> None:
        if self.config.enable_ws:
            self.app.router.add_get("/", self._handle_ws_universal)
            self.app.router.add_get("/api", self._handle_ws_api)
            self.app.router.add_get("/api/", self._handle_ws_api)
            self.app.router.add_get("/event", self._handle_ws_event)
            self.app.router.add_get("/event/", self._handle_ws_event)

        if self.config.enable_http:
            self.app.router.add_get("/{action}", self._handle_http_action)
            self.app.router.add_post("/{action}", self._handle_http_action)
            self.app.router.add_get("/{action}/", self._handle_http_action)
            self.app.router.add_post("/{action}/", self._handle_http_action)

    # ------------------------------------------------------------------
    # HTTP API: /:action
    # ------------------------------------------------------------------

    async def _handle_http_action(self, request: web.Request) -> web.Response:
        auth_status = self._auth_status(request)
        if auth_status != 200:
            return web.Response(status=auth_status)

        action = request.match_info.get("action", "")
        params, error_status = await self._read_http_params(request)
        if error_status is not None:
            return web.Response(status=error_status)

        response = await self.adapter.call_action(action, params)
        status = 404 if int(response.get("retcode", 0) or 0) == 1404 else 200
        return self._json_response(response, status=status)

    @staticmethod
    async def _read_http_params(request: web.Request) -> tuple[JsonDict, int | None]:
        if request.method == "GET":
            return {k: v for k, v in request.query.items() if k != "access_token"}, None

        if not request.can_read_body:
            return {}, None

        content_type = request.content_type.lower()
        if content_type == "application/json":
            try:
                data = await request.json()
            except Exception:
                return {}, 400
            if data is None:
                return {}, None
            if not isinstance(data, Mapping):
                return {}, 400
            return dict(data), None

        if content_type == "application/x-www-form-urlencoded":
            try:
                data = await request.post()
            except Exception:
                return {}, 400
            return dict(data), None

        # 空 body 允许不写 Content-Type；非空 body 但类型不支持则 406。
        body = await request.read()
        if not body.strip():
            return {}, None
        return {}, 406

    # ------------------------------------------------------------------
    # Forward WebSocket: /api, /event, /
    # ------------------------------------------------------------------

    async def _handle_ws_api(self, request: web.Request) -> web.StreamResponse:
        return await self._handle_ws(request, "api")

    async def _handle_ws_event(self, request: web.Request) -> web.StreamResponse:
        return await self._handle_ws(request, "event")

    async def _handle_ws_universal(self, request: web.Request) -> web.StreamResponse:
        return await self._handle_ws(request, "universal")

    async def _handle_ws(self, request: web.Request, role: WsRole) -> web.StreamResponse:
        auth_status = self._auth_status(request)
        if auth_status != 200:
            return web.Response(status=auth_status)

        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._ws_clients[ws] = role
        logger.info("OneBot v11 forward WebSocket connected: role=%s", role)

        try:
            if self.config.send_connect_event and role in {"event", "universal"}:
                await ws.send_json(self._connect_event())

            async for msg in ws:
                if role == "event":
                    # /event 只推送事件，不处理 API 调用。
                    continue

                if msg.type == WSMsgType.TEXT:
                    await ws.send_json(await self._handle_ws_payload_text(msg.data))
                elif msg.type == WSMsgType.BINARY:
                    try:
                        text = msg.data.decode("utf-8")
                    except UnicodeDecodeError:
                        await ws.send_json(self._failed(1400, "binary payload must be utf-8 json"))
                        continue
                    await ws.send_json(await self._handle_ws_payload_text(text))
                elif msg.type == WSMsgType.ERROR:
                    logger.warning("OneBot v11 WebSocket error: %s", ws.exception())
                    break
        finally:
            self._ws_clients.pop(ws, None)
            logger.info("OneBot v11 forward WebSocket disconnected: role=%s", role)

        return ws

    async def _handle_ws_payload_text(self, text: str) -> JsonDict:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return self._failed(1400, "invalid json")
        if not isinstance(payload, Mapping):
            return self._failed(1400, "payload must be object")
        return dict(await self.adapter.call_action_payload(payload))

    # ------------------------------------------------------------------
    # Event broadcast: forward WS + HTTP POST
    # ------------------------------------------------------------------

    async def broadcast_event(self, event: JsonDict) -> None:
        await self._broadcast_forward_ws(event)
        await self._broadcast_http_post(event)

    async def _broadcast_forward_ws(self, event: JsonDict) -> None:
        closed: list[web.WebSocketResponse] = []
        for ws, role in list(self._ws_clients.items()):
            if role == "api":
                continue
            if ws.closed:
                closed.append(ws)
                continue
            try:
                await ws.send_json(event)
            except Exception:
                logger.exception("failed to send OneBot v11 event to WebSocket")
                closed.append(ws)
        for ws in closed:
            self._ws_clients.pop(ws, None)

    async def _broadcast_http_post(self, event: JsonDict) -> None:
        if not self.config.enable_http_post or self._session is None:
            return

        urls = self.config.http_post_urls
        if not urls:
            return

        raw = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = self._http_post_headers(raw)
        timeout = self.config.http_post_timeout or None

        for url in urls:
            try:
                async with self._session.post(url, data=raw, headers=headers, timeout=timeout) as resp:
                    if resp.status == 204:
                        continue
                    text = await resp.text()
                    if resp.status >= 400:
                        logger.warning(
                            "OneBot v11 HTTP POST failed: url=%s status=%s body=%s",
                            url,
                            resp.status,
                            text[:500],
                        )
                        continue
                    await self._handle_quick_operation(event, text)
            except Exception:
                logger.exception("OneBot v11 HTTP POST request failed: %s", url)

    async def _handle_quick_operation(self, event: JsonDict, text: str) -> None:
        if not text.strip():
            return
        try:
            op = json.loads(text)
        except json.JSONDecodeError:
            return
        if not isinstance(op, Mapping):
            return

        if "reply" in op:
            message_type = event.get("message_type")
            if message_type == "private" and event.get("user_id") is not None:
                await self.adapter.call_action(
                    "send_private_msg",
                    {
                        "user_id": event["user_id"],
                        "message": op.get("reply"),
                        "auto_escape": op.get("auto_escape", False),
                    },
                )
            elif message_type == "group" and event.get("group_id") is not None:
                await self.adapter.call_action(
                    "send_group_msg",
                    {
                        "group_id": event["group_id"],
                        "message": op.get("reply"),
                        "auto_escape": op.get("auto_escape", False),
                    },
                )

        if op.get("delete") is True and event.get("message_id") is not None:
            await self.adapter.call_action("delete_msg", {"message_id": event["message_id"]})

        if op.get("ban") is True and event.get("message_type") == "group":
            if event.get("group_id") is not None and event.get("user_id") is not None:
                await self.adapter.call_action(
                    "set_group_ban",
                    {
                        "group_id": event["group_id"],
                        "user_id": event["user_id"],
                        "duration": int(op.get("ban_duration") or 30 * 60),
                    },
                )

        if op.get("kick") is True and event.get("message_type") == "group":
            if event.get("group_id") is not None and event.get("user_id") is not None:
                await self.adapter.call_action(
                    "set_group_kick",
                    {
                        "group_id": event["group_id"],
                        "user_id": event["user_id"],
                        "reject_add_request": bool(op.get("reject_add_request", False)),
                    },
                )

    # ------------------------------------------------------------------
    # Reverse WebSocket
    # ------------------------------------------------------------------

    def _reverse_targets(self) -> list[tuple[str, WsRole]]:
        targets: list[tuple[str, WsRole]] = []

        common_url = self.config.ws_reverse_url
        if self.config.ws_reverse_use_universal_client:
            if common_url:
                targets.append((common_url, "universal"))
            return self._dedupe_targets(targets)

        api_url = self.config.ws_reverse_api_url or common_url
        event_url = self.config.ws_reverse_event_url or common_url
        if api_url:
            targets.append((api_url, "api"))
        if event_url:
            targets.append((event_url, "event"))
        return self._dedupe_targets(targets)

    @staticmethod
    def _dedupe_targets(targets: list[tuple[str, WsRole]]) -> list[tuple[str, WsRole]]:
        seen: set[tuple[str, WsRole]] = set()
        out: list[tuple[str, WsRole]] = []
        for item in targets:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out

    async def _reverse_ws_loop(self, url: str, role: WsRole) -> None:
        failures = 0
        while self._started:
            try:
                await self._connect_reverse_ws(url, role)
                failures = 0
            except asyncio.CancelledError:
                raise
            except ClientConnectorError as exc:
                failures += 1
                if failures == 1:
                    logger.warning(
                        "OneBot v11 reverse WebSocket unreachable: url=%s role=%s error=%s. retry in %ss",
                        url,
                        role,
                        exc.os_error or exc,
                        self.config.ws_reverse_reconnect_interval,
                    )
                else:
                    logger.debug(
                        "OneBot v11 reverse WebSocket still unreachable: url=%s role=%s retry=%s",
                        url,
                        role,
                        failures,
                    )
            except WSServerHandshakeError as exc:
                failures += 1
                logger.warning(
                    "OneBot v11 reverse WebSocket handshake failed: url=%s role=%s status=%s message=%s. retry in %ss",
                    url,
                    role,
                    exc.status,
                    exc.message,
                    self.config.ws_reverse_reconnect_interval,
                )
            except Exception:
                failures += 1
                logger.exception("OneBot v11 reverse WebSocket unexpected error: url=%s role=%s", url, role)

            if self._started:
                await asyncio.sleep(self.config.ws_reverse_reconnect_interval)

    async def _connect_reverse_ws(self, url: str, role: WsRole) -> None:
        if self._session is None:
            raise RuntimeError("ClientSession is not initialized")

        logger.info("connecting OneBot v11 reverse WebSocket: url=%s role=%s", url, role)
        async with self._session.ws_connect(
            url,
            headers=self._reverse_ws_headers(role),
            heartbeat=30,
        ) as ws:
            logger.info("OneBot v11 reverse WebSocket connected: url=%s role=%s", url, role)

            async def reverse_sink(event: JsonDict) -> None:
                if role in {"event", "universal"}:
                    await ws.send_json(event)

            self.adapter.add_event_sink(reverse_sink)
            try:
                if self.config.send_connect_event and role in {"event", "universal"}:
                    await ws.send_json(self._connect_event())

                async for msg in ws:
                    if role == "event":
                        continue
                    if msg.type == WSMsgType.TEXT:
                        await ws.send_json(await self._handle_ws_payload_text(msg.data))
                    elif msg.type == WSMsgType.BINARY:
                        try:
                            text = msg.data.decode("utf-8")
                        except UnicodeDecodeError:
                            await ws.send_json(self._failed(1400, "binary payload must be utf-8 json"))
                            continue
                        await ws.send_json(await self._handle_ws_payload_text(text))
                    elif msg.type == WSMsgType.ERROR:
                        logger.warning("OneBot v11 reverse WebSocket error: %s", ws.exception())
                        break
            finally:
                self.adapter.remove_event_sink(reverse_sink)
                logger.info("OneBot v11 reverse WebSocket disconnected: url=%s role=%s", url, role)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _auth_status(self, request: web.Request) -> int:
        token = self.config.access_token
        if not token:
            return 200

        auth = request.headers.get("Authorization", "")
        query_token = request.query.get("access_token", "")
        provided = bool(auth or query_token)

        if auth == f"Bearer {token}" or query_token == token:
            return 200
        return 403 if provided else 401

    def _http_post_headers(self, raw_body: bytes) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Self-ID": str(getattr(self.adapter, "self_id", "")),
        }
        if self.config.secret:
            digest = hmac.new(self.config.secret.encode("utf-8"), raw_body, hashlib.sha1).hexdigest()
            headers["X-Signature"] = f"sha1={digest}"
        return headers

    def _reverse_ws_headers(self, role: WsRole) -> dict[str, str]:
        role_header = {"api": "API", "event": "Event", "universal": "Universal"}[role]
        headers = {
            "X-Self-ID": str(getattr(self.adapter, "self_id", "")),
            "X-Client-Role": role_header,
            "User-Agent": "CQHttp/4.15.0",
        }
        if self.config.access_token:
            headers["Authorization"] = f"Bearer {self.config.access_token}"
        return headers

    @staticmethod
    def _failed(retcode: int, message: str, *, echo: Any = None) -> JsonDict:
        resp: JsonDict = {"status": "failed", "retcode": retcode, "data": None, "message": message}
        if echo is not None:
            resp["echo"] = echo
        return resp

    def _connect_event(self) -> JsonDict:
        return {
            "time": int(time.time()),
            "self_id": int(getattr(self.adapter, "self_id", 0) or 0),
            "post_type": "meta_event",
            "meta_event_type": "lifecycle",
            "sub_type": "connect",
        }

    @staticmethod
    def _json_response(data: Any, *, status: int = 200) -> web.Response:
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            status=status,
            content_type="application/json",
        )
