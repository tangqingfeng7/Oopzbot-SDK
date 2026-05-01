from __future__ import annotations

import time
from typing import Any

from oopz_sdk.config.constants import EVENT_PRIVATE_MESSAGE_DELETE
from oopz_sdk.models.event import Event, MessageDeleteEvent, MessageEvent, ChannelCreateEvent, ChannelDeleteEvent, \
    HeartbeatEvent

from .message import to_onebot_message
from .types import JsonDict, MessageRecord, MessageStore, OneBotSelf, make_ob_message_id, parse_oopz_timestamp


def to_onebot_event(
    event: Any,
    *,
    self_info: OneBotSelf,
    store: MessageStore,
) -> JsonDict:
    """
    Oopz Event -> OneBot v12 Event。
    """
    # 消息事件
    if isinstance(event, MessageEvent):
        return _message_event(event, self_info=self_info, store=store)

    if isinstance(event, MessageDeleteEvent):
        return _message_delete_event(event, self_info=self_info, store=store)

    if isinstance(event, ChannelCreateEvent):
        return _create_channel_event(event, self_info=self_info)

    if isinstance(event, ChannelDeleteEvent):
        return _delete_channel_event(event, self_info=self_info)

    if isinstance(event, Event):
        return _generic_event(event, self_info=self_info)

    return _unknown_event(event, self_info=self_info)


def _message_event(
    event: MessageEvent,
    *,
    self_info: OneBotSelf,
    store: MessageStore,
) -> JsonDict:
    msg = event.message
    if msg is None:
        raise ValueError("MessageEvent.message is required")

    detail_type = "private" if event.is_private else "channel"

    ob_message_id = make_ob_message_id(
        oopz_message_id=msg.message_id,
        detail_type=detail_type,
        area=msg.area,
        channel=msg.channel,
        target=msg.target,
        user_id=msg.sender_id,
    )

    store.save(
        MessageRecord(
            ob_message_id=ob_message_id,
            oopz_message_id=msg.message_id,
            detail_type=detail_type,
            area=msg.area,
            channel=msg.channel,
            target=msg.target,
            user_id=msg.sender_id,
            created_at=parse_oopz_timestamp(msg.timestamp),
            raw=event.raw,
        )
    )

    payload: JsonDict = {
        "id": _event_id(event),
        "self": self_info,
        "time": parse_oopz_timestamp(msg.timestamp),
        "type": "message",
        "detail_type": detail_type,
        "sub_type": "",
        "message_id": ob_message_id,
        "message": to_onebot_message(msg),
        "alt_message": msg.plain_text or msg.text or msg.content,
        "user_id": msg.sender_id,
        "original_message_id": msg.message_id,
        "original_event_name": event.event_name,
        "original_event_type": event.event_type,
    }

    if detail_type == "channel":
        payload["guild_id"] = msg.area
        payload["channel_id"] = msg.channel

    return payload


def _message_delete_event(
    event: MessageDeleteEvent,
    *,
    self_info: OneBotSelf,
    store: MessageStore,
) -> JsonDict:

    if event.event_type == EVENT_PRIVATE_MESSAGE_DELETE:
        ob_message_id = make_ob_message_id(
            oopz_message_id=event.message_id,
            detail_type="private",
            channel=event.channel,
            target=event.person,
            user_id=event.person,
        )

        return {
            "id": _event_id(event),
            "self": self_info,
            "time": time.time(),
            "type": "notice",
            "detail_type": "message_delete",
            "sub_type": "private",
            "message_id": ob_message_id,
            "original_message_id": event.message_id,
            "user_id": event.person,
            "original_event_name": event.event_name,
            "original_event_type": event.event_type,
            "extra": {
                "oopz_user_id": event.person,
                "oopz_target_id": event.person,
                "oopz_message_id": event.message_id,
                "oopz_channel_id": event.channel,
            },
        }

    ob_message_id = make_ob_message_id(
        oopz_message_id=event.message_id,
        detail_type="channel",
        area=event.area,
        channel=event.channel,
        user_id=event.person,
    )

    return {
        "id": _event_id(event),
        "self": self_info,
        "time": time.time(),
        "type": "notice",
        "detail_type": "message_delete",
        "sub_type": "",
        "message_id": ob_message_id,
        "original_message_id": event.message_id,
        "user_id": event.person,
        "guild_id": event.area,
        "channel_id": event.channel,
        "original_event_name": event.event_name,
        "original_event_type": event.event_type,
        "extra": {
            "oopz_area_id": event.area,
            "oopz_channel_id": event.channel,
            "oopz_user_id": event.person,
            "oopz_message_id": event.message_id,
        },
    }

def _create_channel_event(
    event: ChannelCreateEvent,
    *,
    self_info: OneBotSelf
) -> JsonDict:
    """
    Oopz ChannelCreateEvent -> OneBot v12 notice event。

    Oopz:
        area    -> guild_id
        channel -> channel_id

    OneBot:
        type        = notice
        detail_type = channel_create

    额外字段保留 Oopz 频道配置，方便上层框架使用。
    """
    return {
        "id": _event_id(event),
        "self": self_info,
        "time": time.time(),
        "type": "notice",
        "detail_type": "channel_create",
        "sub_type": "",
        "guild_id": event.area,
        "channel_id": event.channel,
        "channel_name": event.name,
        "channel_type": event.channel_type or event.type,
        # event.group_id 在 Oopz 侧是一个频道分组的概念，OneBot 侧没有对应概念，所以重命名为category
        "channel_category_id": event.group_id,
        "is_temp": event.is_temp,
        "secret": event.secret,
        "member_public": event.member_public,
        "voice_control_enabled": event.voice_control_enabled,
        "text_control_enabled": event.text_control_enabled,
        "voice_roles": event.voice_roles,
        "text_roles": event.text_roles,
        "accessible_roles": event.accessible_roles,
        "accessible_members": event.accessible_members,
        "access_control_enabled": event.access_control_enabled,
        "has_password": event.has_password,
        "max_member": event.max_member,
        "text_gap_second": event.text_gap_second,
        "voice_quality": event.voice_quality,
        "voice_delay": event.voice_delay,
        "original_event_name": event.event_name,
        "original_event_type": event.event_type
    }


def _delete_channel_event(
    event: ChannelDeleteEvent,
    *,
    self_info: OneBotSelf
) -> JsonDict:
    """
    Oopz ChannelDeleteEvent -> OneBot v12 notice event。

    Oopz:
        area    -> guild_id
        channel -> channel_id
        ack_id  -> 原始删除确认/事件 ID
    """
    return {
        "id": _event_id(event),
        "self": self_info,
        "time": time.time(),
        "type": "notice",
        "detail_type": "channel_delete",
        "sub_type": "",
        "guild_id": event.area,
        "channel_id": event.channel,
        "ack_id": event.ack_id,
        "original_event_name": event.event_name,
        "original_event_type": event.event_type
    }

def _generic_event(event: Event, *, self_info: OneBotSelf) -> JsonDict:
    return {
        "id": _event_id(event),
        "self": self_info,
        "time": time.time(),
        "type": "meta",
        "detail_type": f"oopz.{event.event_name}",
        "sub_type": "",
        "original_event_name": event.event_name,
        "original_event_type": event.event_type,
        "payload": event.model_dump(),
    }


def _unknown_event(payload: Any, *, self_info: OneBotSelf) -> JsonDict:
    return {
        "id": f"oopz.event.{time.time_ns()}",
        "self": self_info,
        "time": time.time(),
        "type": "meta",
        "detail_type": "oopz.unknown",
        "sub_type": "",
        "payload": payload,
    }


def _event_id(event: Any) -> str:
    raw = getattr(event, "raw", None)
    if isinstance(raw, dict):
        for key in ("eventId", "event_id", "ackId", "id"):
            value = raw.get(key)
            if value:
                return f"oopz.event.{value}"

    msg = getattr(event, "message", None)
    if msg is not None and getattr(msg, "message_id", ""):
        return f"oopz.event.message.{msg.message_id}"

    return f"oopz.event.{time.time_ns()}"