from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Optional

import websocket

from oopz_sdk.config import EVENT_AUTH, EVENT_CHAT_MESSAGE, EVENT_HEARTBEAT, EVENT_SERVER_ID, OopzConfig
from oopz_sdk.models import ChatMessageEvent, LifecycleEvent
from oopz_sdk.utils.payload import safe_json_loads

logger = logging.getLogger("oopz_sdk.client.compat")


def _error_message_from_payload(payload: dict | None, default_message: str) -> str:
    if not payload:
        return default_message
    for key in ("message", "error", "msg", "reason"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default_message


def _is_success_payload(payload: dict) -> bool:
    status = payload.get("status")
    code = payload.get("code")
    if status is True:
        return True
    if status is False:
        return code in (0, "0", 200, "200", "success")
    if payload.get("success") is True:
        return True
    if payload.get("success") is False:
        return False
    return code in (0, "0", 200, "200", "success")


class OopzClient:
    """Legacy-compatible WebSocket client exposed from oopz_sdk."""

    def __init__(
        self,
        config: OopzConfig,
        on_chat_message: Optional[Callable[[ChatMessageEvent], None]] = None,
        on_other_event: Optional[Callable[[int, dict[str, object]], None]] = None,
        on_lifecycle_event: Optional[Callable[[LifecycleEvent], None]] = None,
        reconnect_interval: float = 2.0,
        max_reconnect_interval: float = 120.0,
        heartbeat_interval: float = 10.0,
    ):
        self._config = config
        self.on_chat_message = on_chat_message
        self.on_other_event = on_other_event
        self.on_lifecycle_event = on_lifecycle_event
        self._base_reconnect = reconnect_interval
        self._max_reconnect = max_reconnect_interval
        self.heartbeat_interval = heartbeat_interval

        self._ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._consecutive_failures = 0
        self._fail_lock = threading.Lock()
        self._hb_body = json.dumps({"person": config.person_uid})
        self._auth_confirmed = False

    def _emit_lifecycle(
        self,
        state: str,
        *,
        attempt: int = 0,
        code: int | None = None,
        reason: str = "",
        error: str = "",
        payload: dict[str, object] | None = None,
    ) -> None:
        if not self.on_lifecycle_event:
            return
        try:
            self.on_lifecycle_event(
                LifecycleEvent(
                    state=state,
                    attempt=attempt,
                    code=code,
                    reason=reason,
                    error=error,
                    payload=payload or {},
                )
            )
        except Exception as exc:
            logger.debug("on_lifecycle_event failed: %s", exc)

    def _next_reconnect_delay(self) -> float:
        with self._fail_lock:
            delay = min(
                self._base_reconnect * (2 ** self._consecutive_failures),
                self._max_reconnect,
            )
            self._consecutive_failures += 1
        return delay

    def start(self):
        self._running = True
        while self._running:
            try:
                self._emit_lifecycle("connecting", attempt=self._consecutive_failures)
                self._connect_and_run()
            except Exception as exc:
                logger.error("WebSocket exception: %s", exc)
                self._emit_lifecycle("error", attempt=self._consecutive_failures, error=str(exc))
            if self._running:
                delay = self._next_reconnect_delay()
                self._emit_lifecycle("reconnecting", attempt=self._consecutive_failures)
                time.sleep(delay)

    def start_async(self):
        self._thread = threading.Thread(target=self.start, daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._running = False
        if self._ws:
            self._ws.close()

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
        self._ws.run_forever(ping_interval=0, ping_timeout=None)

    def _on_open(self, ws):
        with self._fail_lock:
            self._consecutive_failures = 0
        self._auth_confirmed = False
        self._emit_lifecycle("connected")
        self._send_auth(ws)
        threading.Thread(target=self._heartbeat_loop, args=(ws,), daemon=True).start()

    def _on_message(self, ws, message: str):
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, ValueError):
            logger.warning("failed to parse websocket message: %s", message[:200])
            return

        event = data.get("event")

        if event == EVENT_HEARTBEAT:
            body = self._safe_json_parse(data.get("body", {}))
            if body.get("r") == 1:
                self._confirm_auth({"event": EVENT_HEARTBEAT, **body})
                self._send_heartbeat(ws)
            return

        if event == EVENT_SERVER_ID:
            self._confirm_auth({"event": EVENT_SERVER_ID, **data})
            self._send_heartbeat(ws)
            return

        if event == EVENT_AUTH:
            self._handle_auth_event(ws, data)
            if self.on_other_event:
                try:
                    self.on_other_event(event, data)
                except Exception as exc:
                    logger.debug("on_other_event failed: %s", exc)
            return

        if event == EVENT_CHAT_MESSAGE:
            self._confirm_auth({"event": EVENT_CHAT_MESSAGE})
            self._handle_chat(data)
            return

        self._confirm_auth({"event": int(event) if isinstance(event, int) else -1})
        if self.on_other_event:
            try:
                self.on_other_event(event, data)
            except Exception as exc:
                logger.debug("on_other_event failed: %s", exc)

    def _on_error(self, ws, error):
        logger.error("WebSocket error: %s", error)
        self._emit_lifecycle("error", error=str(error))

    def _on_close(self, ws, code, reason):
        self._emit_lifecycle("closed", code=code, reason=str(reason or ""))

    def _send_auth(self, ws):
        auth_body = {
            "person": self._config.person_uid,
            "deviceId": self._config.device_id,
            "signature": self._config.jwt_token,
            "deviceName": self._config.device_id,
            "platformName": "web",
            "reconnect": 0,
        }
        ws.send(
            json.dumps(
                {
                    "time": str(int(time.time() * 1000)),
                    "body": json.dumps(auth_body),
                    "event": EVENT_AUTH,
                }
            )
        )
        self._emit_lifecycle("auth_sent")

    def _confirm_auth(self, payload: dict[str, object] | None = None) -> None:
        if self._auth_confirmed:
            return
        self._auth_confirmed = True
        self._emit_lifecycle("auth_ok", payload=payload or {})

    def _handle_auth_event(self, ws, data: dict[str, object]) -> None:
        body = self._safe_json_parse(data.get("body", {}))
        candidates: list[dict[str, object]] = []
        if isinstance(body, dict):
            candidates.append(body)
            for key in ("data", "result"):
                nested = body.get(key)
                if isinstance(nested, dict):
                    candidates.append(nested)

        for candidate in candidates:
            if "status" not in candidate and "success" not in candidate and "code" not in candidate:
                continue
            if _is_success_payload(candidate):
                self._confirm_auth(candidate)
                return

            reason = _error_message_from_payload(candidate, "WebSocket auth failed")
            code = candidate.get("code")
            try:
                code_value = int(code) if code is not None else None
            except (TypeError, ValueError):
                code_value = None
            self._emit_lifecycle("auth_failed", code=code_value, reason=reason, payload=candidate)
            try:
                ws.close()
            except Exception:
                logger.debug("failed to close websocket after auth failure")
            return

    def _send_heartbeat(self, ws):
        try:
            ws.send(
                json.dumps(
                    {
                        "time": str(int(time.time() * 1000)),
                        "body": self._hb_body,
                        "event": EVENT_HEARTBEAT,
                    }
                )
            )
        except Exception as exc:
            logger.debug("failed to send heartbeat: %s", exc)

    def _heartbeat_loop(self, ws):
        while self._running:
            time.sleep(self.heartbeat_interval)
            if ws.sock and ws.sock.connected:
                self._send_heartbeat(ws)
            else:
                break

    @staticmethod
    def _safe_json_parse(raw, fallback=None):
        return safe_json_loads(raw, fallback=fallback)

    def _handle_chat(self, data: dict[str, object]) -> None:
        try:
            body = self._safe_json_parse(data.get("body", {}))
            msg_data = self._safe_json_parse(body.get("data", {}))
            if not msg_data:
                return
            if msg_data.get("person") == self._config.person_uid:
                return
            if self.on_chat_message:
                event = ChatMessageEvent(
                    message_id=str(msg_data.get("messageId") or msg_data.get("id") or ""),
                    area=str(msg_data.get("area") or ""),
                    channel=str(msg_data.get("channel") or ""),
                    person=str(msg_data.get("person") or ""),
                    content=str(msg_data.get("content") or ""),
                    timestamp=str(msg_data.get("timestamp") or ""),
                    attachments=[
                        item for item in msg_data.get("attachments", [])
                        if isinstance(item, dict)
                    ] if isinstance(msg_data.get("attachments"), list) else [],
                    raw=msg_data,
                )
                self.on_chat_message(event)
        except Exception as exc:
            logger.error("failed to parse chat payload: %s", exc)
