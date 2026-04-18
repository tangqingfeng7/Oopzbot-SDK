from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable, Optional

from oopz_sdk.config.settings import HeartbeatConfig, OopzConfig
from oopz_sdk.config.constants import EVENT_AUTH, EVENT_HEARTBEAT
from oopz_sdk.transport.ws import WebSocketTransport

logger = logging.getLogger("oopz_sdk.client.ws")


class _WebSocketCallbackError(RuntimeError):
    def __init__(self, callback_name: str, original: Exception):
        super().__init__(f"{callback_name} failed: {original}")
        self.callback_name = callback_name
        self.original = original


class OopzWSClient:
    def __init__(
        self,
        config: OopzConfig,
        *,
        on_message: Optional[Callable[[str], Awaitable[None]]] = None,
        on_open: Optional[Callable[[], Awaitable[None]]] = None,
        on_error: Optional[Callable[[object], Awaitable[None]]] = None,
        on_close: Optional[Callable[[object, object], Awaitable[None]]] = None,
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
        self._receive_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._consecutive_failures = 0
        self._has_connected_once = False

    async def start(self) -> None:
        self._running = True

        while self._running:
            fatal_error: Exception | None = None
            try:
                if self._has_connected_once:
                    await self._run_callback("on_reconnect", self.on_reconnect)

                await self.transport.connect()
                self._consecutive_failures = 0
                self._has_connected_once = True

                await self.send_auth()

                await self._run_callback("on_open", self.on_open)

                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                await self._receive_loop()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                reported_error = (
                    exc.original if isinstance(exc, _WebSocketCallbackError) else exc
                )
                logger.exception("WebSocket 运行异常: %s", reported_error)
                if self.on_error:
                    try:
                        await self._run_callback("on_error", self.on_error, reported_error)
                    except _WebSocketCallbackError as callback_exc:
                        fatal_error = callback_exc.original
                if fatal_error is None and isinstance(exc, _WebSocketCallbackError):
                    fatal_error = reported_error

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
            await asyncio.sleep(delay)

    async def stop(self) -> None:
        self._running = False
        await self.transport.close()

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
