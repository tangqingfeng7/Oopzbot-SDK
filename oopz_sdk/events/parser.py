from __future__ import annotations

import json
import logging
from typing import Any

from oopz_sdk.config.constants import (
    EVENT_CHAT_MESSAGE,
    EVENT_HEARTBEAT,
    EVENT_SERVER_ID,
)
from oopz_sdk.exceptions.parse import OopzParseError
from oopz_sdk.models.event import Event, MessageEvent

logger = logging.getLogger("oopz_sdk.events.parser")


class EventParser:
    """
    时间解析器
    解析并规范化来自原始消息或字典的事件数据，将其转换为结构化的事件对象。
    """

    @staticmethod
    def safe_json_parse(raw: Any, fallback=None):
        default = fallback if fallback is not None else {}

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
            msg_data = self.safe_json_parse(body.get("data", {}), fallback={})
            msg_data = self._normalize_message_payload(msg_data)

            return MessageEvent(
                name="message",
                event_type=event_type,
                body=body,
                raw=data,
                message=msg_data['content'],
            )

        if event_type == EVENT_HEARTBEAT:
            return Event(
                name="heartbeat",
                event_type=event_type,
                body=body,
                raw=data,
            )

        if event_type == EVENT_SERVER_ID:
            return Event(
                name="server_id",
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

    @staticmethod
    def _normalize_message_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """
        对 message 做兼容性归一化。

        目标：
        - 保留原始字段
        - 补一些常用别名，方便上层直接取
        - 不破坏现有接口
        """
        if not isinstance(payload, dict):
            return {}

        msg = dict(payload)

        # 常见 ID 字段归一化
        message_id = msg.get("message_id") or msg.get("messageId") or msg.get("id") or ""
        if message_id:
            msg["message_id"] = str(message_id)
            msg["messageId"] = str(message_id)

        # 文本字段归一化
        if "text" not in msg and "content" in msg:
            msg["text"] = msg.get("content") or ""
        else:
            msg["text"] = msg.get("text") or ""

        # 基础上下文字段
        msg["area"] = str(msg.get("area") or "")
        msg["channel"] = str(msg.get("channel") or "")
        msg["target"] = str(msg.get("target") or "")
        msg["timestamp"] = str(msg.get("timestamp") or "")

        # mention/style/attachments 统一成列表
        mention_list = msg.get("mention_list")
        if mention_list is None:
            mention_list = msg.get("mentionList")
        if not isinstance(mention_list, list):
            mention_list = []
        msg["mention_list"] = mention_list
        msg["mentionList"] = mention_list

        style_tags = msg.get("style_tags")
        if style_tags is None:
            style_tags = msg.get("styleTags")
        if not isinstance(style_tags, list):
            style_tags = []
        msg["style_tags"] = style_tags
        msg["styleTags"] = style_tags

        attachments = msg.get("attachments")
        if not isinstance(attachments, list):
            attachments = []
        msg["attachments"] = attachments

        # client message id 兼容
        client_message_id = (
            msg.get("client_message_id")
            or msg.get("clientMessageId")
            or ""
        )
        if client_message_id:
            msg["client_message_id"] = str(client_message_id)
            msg["clientMessageId"] = str(client_message_id)

        # sender 兼容提取
        sender = msg.get("sender")
        if not isinstance(sender, dict):
            sender = {}

        sender_id = (
            sender.get("id")
            or sender.get("userId")
            or sender.get("uid")
            or msg.get("sender_id")
            or ""
        )
        sender_name = (
            sender.get("nickname")
            or sender.get("name")
            or sender.get("username")
            or msg.get("sender_name")
            or ""
        )
        if sender_id:
            msg["sender_id"] = str(sender_id)
        if sender_name:
            msg["sender_name"] = str(sender_name)

        # 保存原始 sender
        msg["sender"] = sender

        return msg