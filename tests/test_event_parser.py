"""针对 EventParser 的事件名契约测试。

重点是保证 parser 发出的事件名和 `OopzBot` 暴露的装饰器（`on_message` /
`on_private_message` / `on_recall` 等）注册的事件名对得上。
"""

from __future__ import annotations

import json

from oopz_sdk.config.constants import (
    EVENT_CHAT_MESSAGE,
    EVENT_HEARTBEAT,
    EVENT_MESSAGE_DELETE,
    EVENT_MESSAGE_EDIT,
    EVENT_PRIVATE_MESSAGE,
    EVENT_PRIVATE_MESSAGE_DELETE,
    EVENT_PRIVATE_MESSAGE_EDIT,
)
from oopz_sdk.events.parser import EventParser
from oopz_sdk.models.event import MessageEvent


def _envelope(event_type: int, body: dict) -> str:
    return json.dumps({"event": event_type, "body": json.dumps(body)})


def _message_data() -> dict:
    return {
        "type": "text",
        "messageId": "m-1",
        "clientMessageId": "c-1",
        "timestamp": "1700000000000",
        "person": "u-1",
        "area": "a-1",
        "channel": "ch-1",
        "content": "hello",
        "text": "hello",
        "attachments": [],
    }


def test_chat_message_event_name_is_message() -> None:
    raw = _envelope(EVENT_CHAT_MESSAGE, {"data": _message_data()})
    event = EventParser().parse(raw)

    assert isinstance(event, MessageEvent)
    assert event.name == "message"
    assert event.is_private is False


def test_private_message_event_name_is_message_private() -> None:
    raw = _envelope(EVENT_PRIVATE_MESSAGE, {"data": _message_data()})
    event = EventParser().parse(raw)

    assert isinstance(event, MessageEvent)
    assert event.name == "message.private"
    assert event.is_private is True


def test_message_delete_event_name_is_recall() -> None:
    """EVENT_MESSAGE_DELETE 必须映射到 'recall'，这样 `@bot.on_recall` 才能收到。"""
    raw = _envelope(EVENT_MESSAGE_DELETE, {"messageId": "m-1"})
    event = EventParser().parse(raw)

    assert event.name == "recall"
    assert event.event_type == EVENT_MESSAGE_DELETE


def test_heartbeat_event_name_is_heartbeat() -> None:
    raw = _envelope(EVENT_HEARTBEAT, {})
    event = EventParser().parse(raw)
    assert event.name == "heartbeat"


def test_message_edit_event_name_is_message_edit() -> None:
    """EVENT_MESSAGE_EDIT 必须映射到 'message.edit'，不然 `@bot.on_message_edit` 收不到。"""
    raw = _envelope(EVENT_MESSAGE_EDIT, {"data": _message_data()})
    event = EventParser().parse(raw)

    assert isinstance(event, MessageEvent)
    assert event.name == "message.edit"
    assert event.is_private is False


def test_private_message_edit_event_name_is_private_edit() -> None:
    raw = _envelope(EVENT_PRIVATE_MESSAGE_EDIT, {"data": _message_data()})
    event = EventParser().parse(raw)

    assert isinstance(event, MessageEvent)
    assert event.name == "message.private.edit"
    assert event.is_private is True


def test_private_message_delete_event_name_is_recall_private() -> None:
    """私聊消息撤回走 'recall.private'，对应 `@bot.on_private_recall`。"""
    raw = _envelope(EVENT_PRIVATE_MESSAGE_DELETE, {"messageId": "m-1"})
    event = EventParser().parse(raw)

    assert event.name == "recall.private"
    assert event.event_type == EVENT_PRIVATE_MESSAGE_DELETE
