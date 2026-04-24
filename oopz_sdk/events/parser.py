from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from oopz_sdk.config.constants import (
    EVENT_AREA_UPDATE,
    EVENT_AUTH,
    EVENT_CHANNEL_DELETE,
    EVENT_CHANNEL_MESSAGE_BAN,
    EVENT_CHANNEL_UPDATE,
    EVENT_CHANNEL_VOICE_BAN,
    EVENT_CHAT_MESSAGE,
    EVENT_HEARTBEAT,
    EVENT_MESSAGE_DELETE,
    EVENT_MESSAGE_EDIT,
    EVENT_PRIVATE_MESSAGE,
    EVENT_PRIVATE_MESSAGE_DELETE,
    EVENT_PRIVATE_MESSAGE_EDIT,
    EVENT_PUBLIC_CHANNEL_CREATE,
    EVENT_ROLE_CHANGED,
    EVENT_SERVER_ID,
    EVENT_USER_ENTER_VOICE_CHANNEL,
    EVENT_USER_LEAVE_VOICE_CHANNEL,
    EVENT_USER_LOGIN_STATE_CHANGED,
    EVENT_USER_UPDATE,
)
from oopz_sdk.exceptions.parse import OopzParseError
from oopz_sdk.models.event import (
    AreaDisableEvent,
    AreaUpdateEvent,
    AuthEvent,
    ChannelCreateEvent,
    ChannelDeleteEvent,
    ChannelUpdateEvent,
    Event,
    HeartbeatEvent,
    MessageDeleteEvent,
    MessageEvent,
    RoleChangedEvent,
    ServerIdEvent,
    UnknownEvent,
    UserLoginStateEvent,
    UserUpdateEvent,
    VoiceChannelPresenceEvent,
)
from oopz_sdk.models.message import Message

logger = logging.getLogger("oopz_sdk.events.parser")
_MISSING = object()


@dataclass(frozen=True, slots=True)
class EventSpec:
    name: str
    model: type[Event]
    is_message: bool = False
    is_private: bool = False


class EventParser:
    """
    事件解析器
    解析并规范化来自原始消息或字典的事件数据，将其转换为结构化的事件对象。

    - 消息事件 -> MessageEvent
    - 非消息事件 -> 具体 Event 子类
    - 未识别事件 -> UnknownEvent
    """

    EVENT_SPECS: dict[int, EventSpec] = {
        # 系统
        EVENT_SERVER_ID: EventSpec("server_id", ServerIdEvent),
        EVENT_AUTH: EventSpec("auth", AuthEvent),
        EVENT_HEARTBEAT: EventSpec("heartbeat", HeartbeatEvent),

        # 消息
        EVENT_CHAT_MESSAGE: EventSpec("message", MessageEvent, is_message=True),
        EVENT_PRIVATE_MESSAGE: EventSpec("message.private", MessageEvent, is_message=True, is_private=True, ),
        EVENT_MESSAGE_EDIT: EventSpec("message.edit", MessageEvent, is_message=True),
        EVENT_PRIVATE_MESSAGE_EDIT: EventSpec("message.private.edit", MessageEvent, is_message=True, is_private=True),
        EVENT_MESSAGE_DELETE: EventSpec("recall", MessageDeleteEvent),
        EVENT_PRIVATE_MESSAGE_DELETE: EventSpec("recall.private", MessageDeleteEvent),

        # 管理
        EVENT_CHANNEL_VOICE_BAN: EventSpec("moderation.voice_ban", AreaDisableEvent),
        EVENT_CHANNEL_MESSAGE_BAN: EventSpec("moderation.text_ban", AreaDisableEvent),

        # 频道 / 语音
        EVENT_CHANNEL_UPDATE: EventSpec("channel.update", ChannelUpdateEvent),
        EVENT_PUBLIC_CHANNEL_CREATE: EventSpec("channel.create", ChannelCreateEvent),
        EVENT_CHANNEL_DELETE: EventSpec("channel.delete", ChannelDeleteEvent),
        EVENT_USER_ENTER_VOICE_CHANNEL: EventSpec("voice.enter", VoiceChannelPresenceEvent),
        EVENT_USER_LEAVE_VOICE_CHANNEL: EventSpec("voice.leave", VoiceChannelPresenceEvent),

        # 用户 / 域 / 身份组
        EVENT_USER_UPDATE: EventSpec("user.update", UserUpdateEvent),
        EVENT_USER_LOGIN_STATE_CHANGED: EventSpec("user.login_state", UserLoginStateEvent),
        EVENT_AREA_UPDATE: EventSpec("area.update", AreaUpdateEvent),
        EVENT_ROLE_CHANGED: EventSpec("role.change", RoleChangedEvent),
    }

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
        spec = self.EVENT_SPECS.get(
            event_type,
            EventSpec(
                name=self._event_name_for_unknown(event_type),
                model=UnknownEvent,
            ),
        )

        body = self._parse_body(data, event_name=spec.name)

        if spec.is_message:
            return self._parse_message_event(
                event_type=event_type, event_name=spec.name,
                raw=data,
                body=body,
                is_private=spec.is_private,
            )

        return self._parse_typed_event(
            event_type=event_type,
            event_name=spec.name,
            raw=data,
            body=body,
            model_cls=spec.model,
        )

    def _parse_body(self, data: dict[str, Any], *, event_name: str) -> dict[str, Any]:
        body = self.safe_json_parse(data.get("body", {}), fallback=None)
        if not isinstance(body, dict):
            raise OopzParseError(f"Invalid {event_name} event body")
        return body

    def _parse_message_event(
            self,
            *,
            event_type: int,
            event_name: str,
            raw: dict[str, Any],
            body: dict[str, Any],
            is_private: bool,
    ) -> MessageEvent:
        msg_data = self.safe_json_parse(body.get("data", {}), fallback=None)
        if not isinstance(msg_data, dict):
            raise OopzParseError(f"Invalid {event_name} event data")

        message = Message.from_api(msg_data)
        return MessageEvent(
            event_name=event_name,
            event_type=event_type,
            raw=raw,
            message=message,
            is_private=is_private,
        )

    def _parse_typed_event(
            self,
            *,
            event_type: int,
            event_name: str,
            raw: dict[str, Any],
            body: dict[str, Any],
            model_cls: type[Event],
    ) -> Event:
        payload = {
            "event_name": event_name,
            "event_type": event_type,
            "raw": raw,
        }

        if model_cls is UnknownEvent:
            payload["payload"] = body
            return UnknownEvent.model_validate(payload)

        payload.update(body)
        return model_cls.model_validate(payload)

    @staticmethod
    def _parse_event_type(data: dict[str, Any]) -> int:
        raw_event = data.get("event", -1)
        try:
            return int(raw_event)
        except (TypeError, ValueError):
            return -1

    @staticmethod
    def _event_name_for_unknown(event_type: int) -> str:
        return f"event_{event_type}"
