from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Optional

import websocket

from oopz_sdk.config.constants import EVENT_AUTH, EVENT_HEARTBEAT
from oopz_sdk.config.settings import HeartbeatConfig, OopzConfig, ProxyConfig

from .proxy import build_websocket_proxy

logger = logging.getLogger("oopz_sdk.transport.websocket")


class WebSocketTransport:
    def __init__(
        self,
        config: OopzConfig,
        *,
        on_message: Optional[Callable[[str], None]] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[object, object], None]] = None,
        on_error: Optional[Callable[[object], None]] = None,
    ):
        self.config = config
        self.on_message = on_message
        self.on_open = on_open
        self.on_close = on_close
        self.on_error = on_error
        self._ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._hb_body = json.dumps({"person": config.person_uid})

    def connect_forever(self) -> None:
        self._running = True
        headers = self.config.get_headers()
        ws_headers = {
            "User-Agent": headers.get("User-Agent", ""),
            "Origin": headers.get("Origin", ""),
            "Cache-Control": headers.get("Cache-Control", ""),
            "Accept-Language": headers.get("Accept-Language", ""),
            "Accept-Encoding": headers.get("Accept-Encoding", ""),
        }
        self._ws = websocket.WebSocketApp(
            self.config.ws_url,
            header=ws_headers,
            on_open=self._handle_open,
            on_message=self._handle_message,
            on_error=self._handle_error,
            on_close=self._handle_close,
        )
        proxy = build_websocket_proxy(getattr(self.config, "proxy", ProxyConfig()))
        kwargs = {}
        if proxy and "://" in proxy:
            try:
                scheme, target = proxy.split("://", 1)
                host_port = target.rsplit("@", 1)[-1]
                host, port = host_port.split(":", 1)
                kwargs["http_proxy_host"] = host
                kwargs["http_proxy_port"] = int(port)
                kwargs["proxy_type"] = scheme
            except Exception:
                logger.debug("Ignore unsupported websocket proxy format: %s", proxy)
        self._ws.run_forever(ping_interval=0, ping_timeout=None, **kwargs)

    def start_async(self) -> threading.Thread:
        self._thread = threading.Thread(target=self.connect_forever, daemon=True)
        self._thread.start()
        return self._thread

    def close(self) -> None:
        self._running = False
        if self._ws:
            self._ws.close()

    def send_auth(self) -> None:
        if self._ws is None:
            return
        auth_body = {
            "person": self.config.person_uid,
            "deviceId": self.config.device_id,
            "signature": self.config.jwt_token,
            "deviceName": self.config.device_id,
            "platformName": "web",
            "reconnect": 0,
        }
        self._ws.send(
            json.dumps(
                {
                    "time": str(int(time.time() * 1000)),
                    "body": json.dumps(auth_body),
                    "event": EVENT_AUTH,
                }
            )
        )

    def send_heartbeat(self) -> None:
        if self._ws is None:
            return
        self._ws.send(
            json.dumps(
                {
                    "time": str(int(time.time() * 1000)),
                    "body": self._hb_body,
                    "event": EVENT_HEARTBEAT,
                }
            )
        )

    def _heartbeat_loop(self) -> None:
        while self._running:
            heartbeat = getattr(self.config, "heartbeat", HeartbeatConfig())
            time.sleep(heartbeat.interval)
            if self._ws and self._ws.sock and self._ws.sock.connected:
                self.send_heartbeat()
            else:
                break

    def _handle_open(self, ws) -> None:
        self.send_auth()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        if self.on_open:
            self.on_open()

    def _handle_message(self, ws, message: str) -> None:
        if self.on_message:
            self.on_message(message)

    def _handle_error(self, ws, error) -> None:
        if self.on_error:
            self.on_error(error)

    def _handle_close(self, ws, code, reason) -> None:
        if self.on_close:
            self.on_close(code, reason)
