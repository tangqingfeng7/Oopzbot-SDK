from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from oopz_sdk.config.settings import HeartbeatConfig, OopzConfig
from oopz_sdk.transport.ws import WebSocketTransport

logger = logging.getLogger("oopz_sdk.client.ws")


class OopzWSClient:
    """
    低层 WebSocket 客户端。

    职责：
    - 连接 / 重连 / 停止
    - 将底层 on_open / on_message / on_error / on_close 透传给上层
    - 不负责 parse / registry / dispatcher
    """

    def __init__(
        self,
        config: OopzConfig,
        *,
        on_message: Optional[Callable[[str], None]] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[object], None]] = None,
        on_close: Optional[Callable[[object, object], None]] = None,
        on_reconnect: Optional[Callable[[], None]] = None,
    ):
        self.config = config

        self.on_message = on_message
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close
        self.on_reconnect = on_reconnect

        self.transport = WebSocketTransport(
            config,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        self._running = False
        self._consecutive_failures = 0
        self._has_connected_once = False

    def start(self) -> None:
        self._running = True

        while self._running:
            try:
                # 第二次及以后进入连接循环，视为重连
                if self._has_connected_once and self.on_reconnect:
                    try:
                        self.on_reconnect()
                    except Exception:
                        logger.exception("on_reconnect 回调执行失败")

                self.transport.connect_forever()

            except Exception as exc:
                logger.error("WebSocket 运行异常: %s", exc)
                if self.on_error:
                    try:
                        self.on_error(exc)
                    except Exception:
                        logger.exception("on_error 回调执行失败")

            if not self._running:
                break

            heartbeat = getattr(self.config, "heartbeat", HeartbeatConfig())
            delay = min(
                heartbeat.reconnect_interval * (2 ** self._consecutive_failures),
                heartbeat.max_reconnect_interval,
            )
            self._consecutive_failures += 1

            logger.warning("WebSocket 将在 %.2f 秒后尝试重连", delay)
            time.sleep(delay)

    def start_async(self):
        self._running = True
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._running = False
        self.transport.close()

    # -------------------------
    # transport 回调
    # -------------------------
    def _on_open(self) -> None:
        self._consecutive_failures = 0
        self._has_connected_once = True

        if self.on_open:
            try:
                self.on_open()
            except Exception:
                logger.exception("on_open 回调执行失败")

    def _on_message(self, message: str) -> None:
        if self.on_message:
            try:
                self.on_message(message)
            except Exception:
                logger.exception("on_message 回调执行失败")

    def _on_error(self, error) -> None:
        logger.error("WebSocket error: %s", error)
        if self.on_error:
            try:
                self.on_error(error)
            except Exception:
                logger.exception("on_error 回调执行失败")

    def _on_close(self, code, reason) -> None:
        logger.warning("WebSocket closed: code=%s reason=%s", code, reason)
        if self.on_close:
            try:
                self.on_close(code, reason)
            except Exception:
                logger.exception("on_close 回调执行失败")