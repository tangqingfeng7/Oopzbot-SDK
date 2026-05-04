from __future__ import annotations

import time
from typing import Any

from oopz_sdk.config.constants import EVENT_PRIVATE_MESSAGE_DELETE
from oopz_sdk.models.event import Event, MessageDeleteEvent, MessageEvent, FriendRequestEvent

from .message import to_v11_message
from .types import (
    IdStore,
    JsonDict,
    make_group_source,
    make_message_source,
    make_self_source,
    make_user_source,
    parse_oopz_timestamp,
)


def to_v11_event(event: Any, *, self_id: str | int, ids: IdStore) -> JsonDict:
    if isinstance(event, MessageEvent):
        return _message_event(event, self_id=self_id, ids=ids)

    if isinstance(event, MessageDeleteEvent):
        return _delete_event(event, self_id=self_id, ids=ids)

    if isinstance(event, FriendRequestEvent):
        return _friend_request_event(event, self_id=self_id, ids=ids)

    self_ob_id = ids.createId(make_self_source(str(self_id))).number

    if isinstance(event, Event):
        return {
            "time": int(time.time()),
            "self_id": self_ob_id,
            "post_type": "meta_event",
            "notice_type": "oopz",
            "sub_type": event.event_name,
            "oopz_event_name": event.event_name,
            "oopz_event_type": event.event_type,
            "payload": event.model_dump(),
        }

    return {
        "time": int(time.time()),
        "self_id": self_ob_id,
        "post_type": "meta_event",
        "meta_event_type": "oopz",
        "payload": event,
    }


def _message_event(event: MessageEvent, *, self_id: str | int, ids: IdStore) -> JsonDict:
    msg = event.message
    if msg is None:
        raise ValueError("MessageEvent.message is required")

    self_ob_id = ids.createId(make_self_source(str(self_id))).number
    user_ob_id = ids.createId(make_user_source(msg.sender_id)).number
    message_ob_id = ids.createId(
        make_message_source(
            area=msg.area,
            channel=msg.channel,
            target=msg.target,
            message_id=msg.message_id,
        )
    ).number

    if event.is_private:
        return {
            "time": parse_oopz_timestamp(msg.timestamp),
            "self_id": self_ob_id,
            "post_type": "message",
            "message_type": "private",
            "sub_type": "friend",
            "message_id": message_ob_id,
            "user_id": user_ob_id,
            "message": to_v11_message(msg, ids=ids),
            "raw_message": msg.plain_text or msg.text or msg.content,
            "font": 0,
            "sender": {
                "user_id": user_ob_id,
                "nickname": getattr(msg, "display_name", ""),
            },
            "extra": {
                "oopz_user_id": msg.sender_id,
                "oopz_target_id": msg.target,
                "oopz_message_id": msg.message_id,
            },
        }

    group_ob_id = ids.createId(
        make_group_source(area=msg.area, channel=msg.channel or msg.area)
    ).number

    return {
        "time": parse_oopz_timestamp(msg.timestamp),
        "self_id": self_ob_id,
        "post_type": "message",
        "message_type": "group",
        "sub_type": "normal",
        "message_id": message_ob_id,
        "group_id": group_ob_id,
        "user_id": user_ob_id,
        "message": to_v11_message(msg, ids=ids),
        "raw_message": msg.plain_text or msg.text or msg.content,
        "font": 0,
        "sender": {
            "user_id": user_ob_id,
            "nickname": getattr(msg, "display_name", ""),
        },
        "extra": {
            "oopz_area_id": msg.area,
            "oopz_channel_id": msg.channel,
            "oopz_user_id": msg.sender_id,
            "oopz_message_id": msg.message_id,
        },
    }


def _delete_event(event: MessageDeleteEvent, *, self_id: str | int, ids: IdStore) -> JsonDict:
    self_ob_id = ids.createId(make_self_source(str(self_id))).number
    user_ob_id = ids.createId(make_user_source(event.person)).number

    event_type = int(getattr(event, "event_type", 0) or 0)
    event_name = str(getattr(event, "event_name", "") or "")

    is_private = (
        event_type == EVENT_PRIVATE_MESSAGE_DELETE
        or event_name in {"message.private.delete", "recall.private", "private_message_delete"}
        or (not getattr(event, "area", "") and bool(getattr(event, "channel", "")))
    )

    if is_private:
        message_ob_id = ids.createId(
            make_message_source(
                target=event.person,
                message_id=event.message_id,
            )
        ).number

        return {
            "time": int(time.time()),
            "self_id": self_ob_id,
            "post_type": "notice",
            "notice_type": "friend_recall",
            "user_id": user_ob_id,
            "message_id": message_ob_id,
            "extra": {
                "oopz_user_id": event.person,
                "oopz_target_id": event.person,
                "oopz_message_id": event.message_id,
                "oopz_channel_id": event.channel,
            },
        }

    group_ob_id = ids.createId(
        make_group_source(area=event.area, channel=event.channel or event.area)
    ).number

    message_ob_id = ids.createId(
        make_message_source(
            area=event.area,
            channel=event.channel,
            message_id=event.message_id,
        )
    ).number

    return {
        "time": int(time.time()),
        "self_id": self_ob_id,
        "post_type": "notice",
        "notice_type": "group_recall",
        "group_id": group_ob_id,
        "user_id": user_ob_id,
        "operator_id": user_ob_id,
        "message_id": message_ob_id,
        "extra": {
            "oopz_area_id": event.area,
            "oopz_channel_id": event.channel,
            "oopz_user_id": event.person,
            "oopz_message_id": event.message_id,
        },
    }

def _friend_request_event(event: FriendRequestEvent, *, self_id: str | int, ids: IdStore) -> JsonDict:
    self_ob_id = ids.createId(make_self_source(str(self_id))).number
    user_ob_id = ids.createId(make_user_source(event.person)).number
    return {
    "time": int(time.time()),
    "self_id": self_ob_id,
    "post_type": "request",
    "request_type": "friend",
    "user_id": user_ob_id,
    "comment": event.name or "",
    "flag": f"oopz_friend_request:{event.friend_request_id}:{event.person}",
    "extra": {
        "oopz_friend_request_id": event.friend_request_id,
        "oopz_user_id": event.person,
        "oopz_name": event.name,
        "oopz_type": event.type,
        "oopz_avatar": event.avatar,
    },
}