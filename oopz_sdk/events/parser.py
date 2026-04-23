from __future__ import annotations

import json
import logging
from typing import Any

from oopz_sdk.config.constants import (
    EVENT_CHAT_MESSAGE,
    EVENT_HEARTBEAT,
    EVENT_MESSAGE_DELETE,
    EVENT_MESSAGE_EDIT,
    EVENT_PRIVATE_MESSAGE,
    EVENT_PRIVATE_MESSAGE_DELETE,
    EVENT_PRIVATE_MESSAGE_EDIT,
    EVENT_SERVER_ID,
)
from oopz_sdk.exceptions.parse import OopzParseError
from oopz_sdk.models.event import Event, MessageEvent
from oopz_sdk.models.message import Message

logger = logging.getLogger("oopz_sdk.events.parser")
_MISSING = object()


class EventParser:
    """
    时间解析器
    解析并规范化来自原始消息或字典的事件数据，将其转换为结构化的事件对象。
    """

    @staticmethod
    def safe_json_parse(raw: Any, fallback: Any = _MISSING):
        default = {} if fallback is _MISSING else fallback

        if isinstance(raw, dict):
            return raw

        if isinstance(raw, (bytes, bytearray, memoryview)):
            try:
                raw = bytes(raw).decode("utf-8")
            except (UnicodeDecodeError, ValueError):
                return default

        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError, TypeError):
                return default

        return default

    def parse(self, message: str | dict) -> Event:
        data = self.safe_json_parse(message, fallback=None)
        if not isinstance(data, dict):
            raise OopzParseError("Invalid event payload")

        event_type = self._parse_event_type(data)
        body = self.safe_json_parse(data.get("body", {}), fallback={})

        if event_type == EVENT_CHAT_MESSAGE:
            return self._parse_message_event(
                event_type, data, name="message", what="chat"
            )
        elif event_type == EVENT_PRIVATE_MESSAGE:
            return self._parse_message_event(
                event_type, data, name="message.private", what="private",
                is_private=True,
            )
        elif event_type == EVENT_MESSAGE_EDIT:
            return self._parse_message_event(
                event_type, data, name="message.edit", what="message edit"
            )
        elif event_type == EVENT_PRIVATE_MESSAGE_EDIT:
            return self._parse_message_event(
                event_type, data, name="message.private.edit",
                what="private message edit", is_private=True,
            )
        elif event_type == EVENT_PRIVATE_MESSAGE_DELETE:
            return Event(
                name="recall.private",
                event_type=event_type,
                body=body,
                raw=data,
            )
        elif event_type == EVENT_HEARTBEAT:
            return Event(
                name="heartbeat",
                event_type=event_type,
                body=body,
                raw=data,
            )
        elif event_type == EVENT_SERVER_ID:
            return Event(
                name="server_id",
                event_type=event_type,
                body=body,
                raw=data,
            )
        elif event_type == EVENT_MESSAGE_DELETE:
            return Event(
                name="recall",
                event_type=event_type,
                body=body,
                raw=data,
            )

        return Event(
            name=self._event_name_for_unknown(event_type),
            event_type=event_type,
            body=body,
            raw=data,
        )

    def _parse_message_event(
        self,
        event_type: int,
        data: dict,
        *,
        name: str,
        what: str,
        is_private: bool = False,
    ) -> "MessageEvent":
        body = self.safe_json_parse(data.get("body", {}), fallback=None)
        if not isinstance(body, dict):
            raise OopzParseError(f"Invalid {what} event body")

        msg_data = self.safe_json_parse(body.get("data", {}), fallback=None)
        if not isinstance(msg_data, dict):
            raise OopzParseError(f"Invalid {what} event data")

        message = Message.from_api(msg_data)
        return MessageEvent(
            name=name,
            event_type=event_type,
            body=body,
            raw=data,
            message=message,
            is_private=is_private,
        )

    @staticmethod
    def _parse_event_type(data: dict) -> int:
        raw_event = data.get("event", -1)
        try:
            return int(raw_event)
        except (TypeError, ValueError):
            return -1

    @staticmethod
    def _event_name_for_unknown(event_type: int) -> str:
        return f"event_{event_type}"
