"""Oopz WebSocket 客户端，支持自动重连。"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Optional

import websocket

from .config import OopzConfig

logger = logging.getLogger("oopz.client")

_json_loads = json.loads

EVENT_SERVER_ID = 1
EVENT_CHAT_MESSAGE = 9
EVENT_AUTH = 253
EVENT_HEARTBEAT = 254


class OopzClient:
    """Oopz WebSocket 客户端，支持自动重连。

    用法::

        config = OopzConfig(...)
        client = OopzClient(config, on_chat_message=my_handler)
        client.start()          # 阻塞运行
        # 或
        client.start_async()    # 后台线程运行

    Args:
        config: SDK 配置对象。
        on_chat_message: 收到聊天消息时的回调，参数为解析后的 msg_data 字典。
        on_other_event: 收到非聊天事件时的回调，参数为 (event_type, data)。
        reconnect_interval: 初始重连间隔（秒）。
        max_reconnect_interval: 最大重连间隔（秒）。
        heartbeat_interval: 心跳间隔（秒）。
    """

    def __init__(
        self,
        config: OopzConfig,
        on_chat_message: Optional[Callable[[dict], None]] = None,
        on_other_event: Optional[Callable[[int, dict], None]] = None,
        reconnect_interval: float = 2.0,
        max_reconnect_interval: float = 120.0,
        heartbeat_interval: float = 10.0,
    ):
        self._config = config
        self.on_chat_message = on_chat_message
        self.on_other_event = on_other_event
        self._base_reconnect = reconnect_interval
        self._max_reconnect = max_reconnect_interval
        self.heartbeat_interval = heartbeat_interval

        self._ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._consecutive_failures = 0
        self._fail_lock = threading.Lock()
        self._hb_body = json.dumps({"person": config.person_uid})

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def _next_reconnect_delay(self) -> float:
        with self._fail_lock:
            delay = min(
                self._base_reconnect * (2 ** self._consecutive_failures),
                self._max_reconnect,
            )
            self._consecutive_failures += 1
        return delay

    def start(self):
        """阻塞运行（带指数退避自动重连）。"""
        self._running = True
        while self._running:
            try:
                self._connect_and_run()
            except Exception as e:
                logger.error("WebSocket 异常: %s", e)

            if self._running:
                delay = self._next_reconnect_delay()
                logger.info("%.1fs 后重连 (第 %d 次)", delay, self._consecutive_failures)
                time.sleep(delay)

    def start_async(self):
        """在后台线程中运行。"""
        self._thread = threading.Thread(target=self.start, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        """停止客户端。"""
        self._running = False
        if self._ws:
            self._ws.close()

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _connect_and_run(self):
        headers = self._config.get_headers()
        ws_headers = {
            "User-Agent": headers.get("User-Agent", ""),
            "Origin": headers.get("Origin", ""),
            "Cache-Control": headers.get("Cache-Control", ""),
            "Accept-Language": headers.get("Accept-Language", ""),
            "Accept-Encoding": headers.get("Accept-Encoding", ""),
        }

        self._ws = websocket.WebSocketApp(
            self._config.ws_url,
            header=ws_headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        logger.info("正在连接 %s ...", self._config.ws_url)
        self._ws.run_forever(
            ping_interval=0,
            ping_timeout=None,
        )

    # -- WebSocket 回调 --

    def _on_open(self, ws):
        logger.info("WebSocket 连接已建立")
        with self._fail_lock:
            self._consecutive_failures = 0
        self._send_auth(ws)
        threading.Thread(target=self._heartbeat_loop, args=(ws,), daemon=True).start()

    def _on_message(self, ws, message: str):
        try:
            data = _json_loads(message)
        except (json.JSONDecodeError, ValueError):
            logger.warning("无法解析消息: %s", message[:200])
            return

        event = data.get("event")

        if event == EVENT_HEARTBEAT:
            body_raw = data.get("body", {})
            if isinstance(body_raw, str):
                try:
                    body = _json_loads(body_raw)
                except (json.JSONDecodeError, ValueError):
                    body = {}
            elif isinstance(body_raw, dict):
                body = body_raw
            else:
                body = {}
            if body.get("r") == 1:
                self._send_heartbeat(ws)
            return

        if event == EVENT_SERVER_ID:
            self._send_heartbeat(ws)
            logger.info("收到 serverId，已发送首次心跳")
            return

        if event == EVENT_CHAT_MESSAGE:
            self._handle_chat(data)
            return

        if self.on_other_event:
            try:
                self.on_other_event(event, data)
            except Exception as e:
                logger.debug("on_other_event 处理异常: %s", e)

    def _on_error(self, ws, error):
        logger.error("WebSocket 错误: %s", error)

    def _on_close(self, ws, code, reason):
        logger.warning("连接关闭 (code=%s, reason=%s)", code, reason)

    # -- 认证 --

    def _send_auth(self, ws):
        cfg = self._config
        auth_body = {
            "person": cfg.person_uid,
            "deviceId": cfg.device_id,
            "signature": cfg.jwt_token,
            "deviceName": cfg.device_id,
            "platformName": "web",
            "reconnect": 0,
        }
        payload = {
            "time": str(int(time.time() * 1000)),
            "body": json.dumps(auth_body),
            "event": EVENT_AUTH,
        }
        ws.send(json.dumps(payload))
        logger.info("已发送认证信息")

    # -- 心跳 --

    def _send_heartbeat(self, ws):
        try:
            ws.send(json.dumps({
                "time": str(int(time.time() * 1000)),
                "body": self._hb_body,
                "event": EVENT_HEARTBEAT,
            }))
        except Exception as e:
            logger.debug("发送心跳失败（连接可能已关闭）: %s", e)

    def _heartbeat_loop(self, ws):
        while self._running:
            time.sleep(self.heartbeat_interval)
            if ws.sock and ws.sock.connected:
                self._send_heartbeat(ws)
            else:
                break

    # -- 聊天消息处理 --

    @staticmethod
    def _safe_json_parse(raw, fallback=None):
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                return _json_loads(raw)
            except (json.JSONDecodeError, ValueError):
                return fallback if fallback is not None else {}
        return fallback if fallback is not None else {}

    def _handle_chat(self, data: dict):
        try:
            body = self._safe_json_parse(data.get("body", {}))
            msg_data = self._safe_json_parse(body.get("data", {}))
            if not msg_data:
                return

            if msg_data.get("person") == self._config.person_uid:
                return

            person_id = msg_data.get("person", "")
            channel_id = msg_data.get("channel", "")
            area_id = msg_data.get("area", "")

            logger.info(
                "[聊天] 域=%s 频道=%s 用户=%s 内容=%s",
                area_id, channel_id, person_id,
                msg_data.get("content", "")[:100],
            )

            if self.on_chat_message:
                self.on_chat_message(msg_data)

        except Exception as e:
            logger.error("解析聊天消息失败: %s", e)
