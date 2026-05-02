from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from oopz_sdk.config.settings import HeartbeatConfig, OopzConfig
from oopz_sdk.config.constants import EVENT_AUTH, EVENT_HEARTBEAT, EVENT_SUBSCRIBE_AREA_EVENTS
from oopz_sdk.transport.ws import WebSocketClosedError, WebSocketTransport

logger = logging.getLogger(__name__)


class _WebSocketCallbackError(RuntimeError):
    def __init__(self, callback_name: str, original: Exception):
        super().__init__(f"{callback_name} failed: {original}")
        self.callback_name = callback_name
        self.original = original


@dataclass(slots=True)
class CloseInfo:
    code: int | None = None
    reason: str = ""
    error: Exception | None = None
    reconnecting: bool = False

class OopzWSClient:
    def __init__(
        self,
        config: OopzConfig,
        *,
        on_message: Optional[Callable[[str], Awaitable[None]]] = None,
        on_open: Optional[Callable[[], Awaitable[None]]] = None,
        on_error: Optional[Callable[[object], Awaitable[None]]] = None,
        on_close: Optional[Callable[[CloseInfo], Awaitable[None] | None]] = None,
        on_reconnect: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self.config = config
        self.on_message = on_message
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close
        self.on_reconnect = on_reconnect

        self.transport = WebSocketTransport(config)

        self._running = False
        self._stop_event = asyncio.Event()
        self._receive_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._consecutive_failures = 0
        self._has_connected_once = False

    async def start(self) -> None:
        self._running = True
        self._stop_event.clear()

        while self._running:
            fatal_error: Exception | None = None
            runtime_error: Exception | None = None
            connected_this_round = False

            try:
                if self._has_connected_once:
                    await self._run_callback("on_reconnect", self.on_reconnect)

                await self.transport.connect()
                connected_this_round = True
                self._consecutive_failures = 0
                self._has_connected_once = True

                await self.send_auth()

                await self._run_callback("on_open", self.on_open)

                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                await self._receive_loop()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                runtime_error = (
                    exc.original if isinstance(exc, _WebSocketCallbackError) else exc
                )
                normal_stop_error = self._is_normal_stop_error(runtime_error)
                if not normal_stop_error:
                    logger.exception("WebSocket 运行异常: %s", runtime_error)
                    already_dispatched = bool(
                        getattr(runtime_error, "_oopz_error_dispatched", False)
                    )
                    if self.on_error and not already_dispatched:
                        try:
                            await self._run_callback("on_error", self.on_error, runtime_error)
                        except _WebSocketCallbackError as callback_exc:
                            fatal_error = callback_exc.original
                if fatal_error is None and isinstance(exc, _WebSocketCallbackError):
                    fatal_error = runtime_error

            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    try:
                        await self._heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    self._heartbeat_task = None

                try:
                    await self.transport.close()
                except Exception:
                    logger.exception("关闭 WebSocketTransport 失败")

                if connected_this_round:
                    close_code = runtime_error.code if isinstance(runtime_error, WebSocketClosedError) else None
                    close_reason = self._get_close_reason(runtime_error)
                    close_info = CloseInfo(
                        code=close_code,
                        reason=close_reason,
                        error=runtime_error,
                        reconnecting=self._running and fatal_error is None,
                    )
                    try:
                        await self._run_callback("on_close", self.on_close, close_info)
                    except _WebSocketCallbackError as callback_exc:
                        if fatal_error is None:
                            fatal_error = callback_exc.original

            if fatal_error is not None:
                raise fatal_error

            if not self._running:
                break

            heartbeat = getattr(self.config, "heartbeat", HeartbeatConfig())
            delay = min(
                heartbeat.reconnect_interval * (2 ** self._consecutive_failures),
                heartbeat.max_reconnect_interval,
            )
            self._consecutive_failures += 1

            logger.warning("WebSocket 将在 %.2f 秒后尝试重连", delay)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        await self.transport.close()

    def _is_normal_stop_error(self, error: Exception) -> bool:
        return not self._running and isinstance(error, WebSocketClosedError)

    def _get_close_reason(self, error: Exception | None) -> str:
        if not self._running:
            return "stopped"
        if isinstance(error, WebSocketClosedError):
            return error.reason
        return "connection closed"

    async def _receive_loop(self) -> None:
        while self._running:
            raw = await self.transport.recv()
            await self._run_callback("on_message", self.on_message, raw)

    async def send_auth(self) -> None:
        auth_body = {
            "person": self.config.person_uid,
            "deviceId": self.config.device_id,
            "signature": self.config.jwt_token,
            "deviceName": self.config.device_id,
            "platformName": "web",
            "reconnect": 0,
        }

        await self.transport.send_json(
            {
                "time": str(int(time.time() * 1000)),
                "body": json.dumps(auth_body, ensure_ascii=False),
                "event": EVENT_AUTH,
            }
        )

    async def send_heartbeat(self) -> None:
        await self.transport.send_json(
            {
                "time": str(int(time.time() * 1000)),
                "body": json.dumps({"person": self.config.person_uid}, ensure_ascii=False),
                "event": EVENT_HEARTBEAT,
            }
        )

    async def _heartbeat_loop(self) -> None:
        while self._running and not self.transport.closed:
            heartbeat = getattr(self.config, "heartbeat", HeartbeatConfig())
            await asyncio.sleep(heartbeat.interval)
            if self._running and not self.transport.closed:
                await self.send_heartbeat()

    @staticmethod
    async def _run_callback(callback_name: str, callback, *args) -> None:
        if callback is None:
            return
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise _WebSocketCallbackError(callback_name, exc) from exc

    async def send_subscribe_area_events(
        self,
        areas: list[str],
        *,
        uid: str = "",
        event_type: int = 1,
    ) -> None:
        """订阅指定域的 WebSocket 事件。"""
        uid = uid if uid else self.config.person_uid
        clean_areas = [area for area in areas if str(area).strip()]
        if not clean_areas:
            return

        await self.transport.send_json(
            {
                "time": str(int(time.time() * 1000)),
                "body": json.dumps(
                    {
                        "areas": clean_areas,
                        "type": event_type,
                        "uid": uid,
                    },
                    ensure_ascii=False,
                ),
                "event": EVENT_SUBSCRIBE_AREA_EVENTS,
            }
        )