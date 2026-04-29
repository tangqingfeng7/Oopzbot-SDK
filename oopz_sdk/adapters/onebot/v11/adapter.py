from __future__ import annotations

import logging
import time
from collections import deque
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping, TYPE_CHECKING

from oopz_sdk.adapters.onebot.v12.types import MessageRecord, MessageStore
from oopz_sdk.models.event import HeartbeatEvent, ServerIdEvent
from oopz_sdk.models.segment import Mention

from .event import to_v11_event
from .message import V11SendParts, from_v11_message
from .types import (
    ActionResponse,
    IdStore,
    JsonDict,
    failed,
    make_group_source,
    make_message_source,
    make_self_source,
    make_user_source,
    ok,
    parse_group_source,
    parse_message_source,
    parse_oopz_timestamp,
    parse_user_source,
    require_int,
)

logger = logging.getLogger(__name__)

EventSink = Callable[[JsonDict], Awaitable[None] | None]

if TYPE_CHECKING:
    from oopz_sdk import OopzBot

SUPPORTED_ACTIONS = [
    "get_supported_actions",
    ".get_supported_actions",
    "get_latest_events",
    "get_status",
    "get_version_info",
    "get_login_info",
    "send_msg",
    "send_private_msg",
    "send_group_msg",
    "delete_msg",
    "get_stranger_info",
    "get_friend_list",
    "get_group_info",
    "get_group_list",
    "get_group_member_info",
]


class OneBotV11Adapter:
    """
    Oopz -> OneBot v11 适配器。

    ID 策略与 onebots 的 createId / resolveId 类似：
    - Oopz 原始字符串 ID 不直接暴露给 v11；
    - v11 user_id / group_id / message_id / self_id 均为数字；
    - 内部通过 IdStore.resolveId 还原到 Oopz 原始 ID。
    """

    protocol = "onebot.v11"

    def __init__(
        self,
        oopz_bot: OopzBot,
        self_id: str,
        *,
        platform: str = "oopz",
        db_path: str | Path | None = None,
    ) -> None:
        self.oopz_bot = oopz_bot
        self.platform = platform
        self.self_oopz_id = str(self_id)

        if db_path is None:
            base = Path.cwd() / ".oopz_sdk"
            base.mkdir(parents=True, exist_ok=True)
            db_path = base / "onebot_v11.sqlite3"

        self.ids = IdStore(db_path)
        self.store = MessageStore(db_path)
        self.self_id = self.ids.createId(make_self_source(self.self_oopz_id)).number

        self._event_sinks: list[EventSink] = []
        self._event_queue: deque[JsonDict] = deque(maxlen=1000)

    async def emit_event(self, event: Any) -> JsonDict:
        if isinstance(event, HeartbeatEvent) or isinstance(event, ServerIdEvent):
            return {}

        payload = to_v11_event(event, self_id=self.self_oopz_id, ids=self.ids)
        self._save_message_event_mapping(payload)
        self._event_queue.append(payload)
        logger.debug("emit onebot v11 event: %s", payload)

        for sink in list(self._event_sinks):
            try:
                result = sink(payload)
                if result is not None:
                    await result
            except Exception:
                logger.exception("failed to emit onebot v11 event")

        return payload

    def add_event_sink(self, sink: EventSink) -> None:
        self._event_sinks.append(sink)

    def remove_event_sink(self, sink: EventSink) -> None:
        try:
            self._event_sinks.remove(sink)
        except ValueError:
            pass

    async def call_action_payload(self, payload: Mapping[str, Any]) -> ActionResponse:
        action = payload.get("action")
        echo = payload.get("echo")
        if not isinstance(action, str) or not action:
            return failed(1400, "action must be a non-empty string", echo=echo)

        params = payload.get("params") or {}
        if not isinstance(params, Mapping):
            return failed(1400, "params must be an object", echo=echo)

        return await self.call_action(action, params, echo=echo)

    async def call_action(
        self,
        action: str,
        params: Mapping[str, Any] | None = None,
        *,
        echo: Any = None,
    ) -> ActionResponse:
        params = params or {}
        try:
            if action in {"get_supported_actions", ".get_supported_actions"}:
                return ok(list(SUPPORTED_ACTIONS), echo=echo)
            if action == "get_status":
                return ok({"online": True, "good": True}, echo=echo)
            if action in {"get_version_info", "get_version"}:
                return ok(
                    {
                        "app_name": "oopz_sdk",
                        "app_version": "0.1.0",
                        "protocol_version": "v11",
                    },
                    echo=echo,
                )
            if action == "get_latest_events":
                return ok(self.get_latest_events(params), echo=echo)
            if action == "get_login_info":
                return ok(await self.get_login_info(), echo=echo)
            if action == "send_private_msg":
                return ok(await self.send_private_msg(params), echo=echo)
            if action == "send_group_msg":
                return ok(await self.send_group_msg(params), echo=echo)
            if action == "send_msg":
                return ok(await self.send_msg(params), echo=echo)
            if action in {"delete_msg", "recall_message"}:
                return ok(await self.delete_msg(params), echo=echo)
            if action == "get_stranger_info":
                return ok(await self.get_stranger_info(params), echo=echo)
            if action == "get_friend_list":
                return ok(await self.get_friend_list(), echo=echo)
            if action in {"get_group_info", "get_guild_info"}:
                return ok(await self.get_group_info(params), echo=echo)
            if action in {"get_group_list", "get_guild_list"}:
                return ok(await self.get_group_list(), echo=echo)
            if action == "get_group_member_info":
                return ok(await self.get_group_member_info(params), echo=echo)
            return failed(1404, f"unsupported action: {action}", echo=echo)
        except ValueError as exc:
            return failed(1400, str(exc), echo=echo)
        except KeyError as exc:
            return failed(1404, str(exc), echo=echo)
        except NotImplementedError as exc:
            return failed(1404, str(exc), echo=echo)
        except Exception as exc:
            logger.exception("onebot v11 action failed: %s", action)
            return failed(1500, str(exc), echo=echo)

    def get_latest_events(self, params: Mapping[str, Any]) -> list[JsonDict]:
        limit = int(params.get("limit") or 0)
        events = list(self._event_queue)
        return events[-limit:] if limit > 0 else events

    def failed_response(self, retcode: int, message: str, *, echo: Any = None) -> ActionResponse:
        return failed(retcode, message, echo=echo)

    def connect_event(self) -> JsonDict:
        return {
            "time": int(time.time()),
            "self_id": self.self_id,
            "post_type": "meta_event",
            "meta_event_type": "lifecycle",
            "sub_type": "connect",
        }

    async def get_login_info(self) -> JsonDict:
        profile = await self.oopz_bot.person.get_self_detail()
        return {"user_id": self.self_id, "nickname": getattr(profile, "name", "")}

    async def send_msg(self, params: Mapping[str, Any]) -> JsonDict:
        message_type = str(params.get("message_type") or "")
        if message_type == "private" or params.get("user_id"):
            return await self.send_private_msg(params)
        if message_type == "group" or params.get("group_id"):
            return await self.send_group_msg(params)
        raise ValueError("message_type, user_id or group_id is required")

    async def send_private_msg(self, params: Mapping[str, Any]) -> JsonDict:
        user_id = require_int(params, "user_id")
        target = self._resolve_user_id(user_id)
        send_parts = self._resolve_send_parts(from_v11_message(params.get("message") or ""))

        result = await self.oopz_bot.messages.send_private_message(
            *send_parts.parts,
            target=target,
            mention_list=send_parts.mention_list,
            is_mention_all=send_parts.is_mention_all,
        )

        message_id = self.ids.createId(
            make_message_source(target=target, message_id=result.message_id)
        ).number
        self._save_sent_mapping(
            message_id,
            result.message_id,
            detail_type="private",
            target=target,
            user_id=target,
            timestamp=result.timestamp,
        )
        return {"message_id": message_id}

    async def send_group_msg(self, params: Mapping[str, Any]) -> JsonDict:
        group_id = require_int(params, "group_id")

        try:
            area, channel = self._resolve_group_id(group_id)
        except ValueError:
            area = str(params.get("oopz_area_id") or params.get("area") or params.get("guild_id") or "")
            channel = str(params.get("oopz_channel_id") or params.get("channel_id") or "")

        if not area or not channel:
            raise ValueError("unknown group_id; provide oopz_area_id and oopz_channel_id")

        # 如果调用方通过扩展字段提供了真实 channel，也把它注册成这个 group_id 的 source。
        self.ids.createId(make_group_source(area=area, channel=channel))

        send_parts = self._resolve_send_parts(from_v11_message(params.get("message") or ""))
        result = await self.oopz_bot.messages.send_message(
            *send_parts.parts,
            area=area,
            channel=channel,
            mention_list=send_parts.mention_list,
            is_mention_all=send_parts.is_mention_all,
        )

        message_id = self.ids.createId(
            make_message_source(area=area, channel=channel, message_id=result.message_id)
        ).number
        self._save_sent_mapping(
            message_id,
            result.message_id,
            detail_type="group",
            area=area,
            channel=channel,
            timestamp=result.timestamp,
        )
        return {"message_id": message_id}

    async def delete_msg(self, params: Mapping[str, Any]) -> None:
        message_id = require_int(params, "message_id")
        record = self.store.get(str(message_id))

        if record is None:
            id_record = self.ids.try_resolve_id(message_id)
            if id_record is not None:
                try:
                    area, channel, target, oopz_message_id = parse_message_source(id_record.source)
                except ValueError:
                    area = channel = target = ""
                    oopz_message_id = str(message_id)
            else:
                area = channel = target = ""
                oopz_message_id = str(message_id)

            area = str(params.get("oopz_area_id") or params.get("area") or params.get("guild_id") or area or "")
            channel = str(params.get("oopz_channel_id") or params.get("channel_id") or channel or "")
            target = str(params.get("target") or params.get("user_id") or target or "")

            if target and not channel:
                result = await self.oopz_bot.messages.recall_private_message(
                    message_id=oopz_message_id,
                    target=self._resolve_user_id(target) if str(target).isdigit() else target,
                    area=area or None,
                )
            else:
                if not area or not channel:
                    raise ValueError("message mapping not found; provide oopz_area_id and oopz_channel_id")
                result = await self.oopz_bot.messages.recall_message(
                    message_id=oopz_message_id,
                    area=area,
                    channel=channel,
                )
        elif record.detail_type == "private":
            result = await self.oopz_bot.messages.recall_private_message(
                message_id=record.oopz_message_id,
                channel=record.channel,
                target=record.target or record.user_id,
                area=record.area or None,
            )
        else:
            result = await self.oopz_bot.messages.recall_message(
                message_id=record.oopz_message_id,
                area=record.area,
                channel=record.channel,
                target=record.target,
            )

        if not getattr(result, "ok", True):
            raise RuntimeError(getattr(result, "message", "recall failed"))
        return None

    async def get_stranger_info(self, params: Mapping[str, Any]) -> JsonDict:
        user_id = require_int(params, "user_id")
        uid = self._resolve_user_id(user_id)
        info = await self.oopz_bot.person.get_person_info(uid)
        return {
            "user_id": user_id,
            "nickname": getattr(info, "name", ""),
            "sex": "unknown",
            "age": 0,
            "oopz_user_id": uid,
        }

    async def get_friend_list(self) -> list[JsonDict]:
        friends = await self.oopz_bot.person.get_friendship()
        result: list[JsonDict] = []
        for friend in friends:
            user_id = self.ids.createId(make_user_source(friend.uid)).number
            result.append(
                {
                    "user_id": user_id,
                    "nickname": friend.name,
                    "remark": "",
                    "oopz_user_id": friend.uid,
                }
            )
        return result

    async def get_group_info(self, params: Mapping[str, Any]) -> JsonDict:
        group_id = require_int(params, "group_id")
        area, channel = self._resolve_group_id(group_id)
        return {
            "group_id": group_id,
            "group_name": channel,
            "member_count": 0,
            "max_member_count": 0,
            "oopz_area_id": area,
            "oopz_channel_id": channel,
        }

    async def get_group_list(self) -> list[JsonDict]:
        areas = await self.oopz_bot.areas.get_joined_areas()
        result: list[JsonDict] = []

        for area_obj in areas:
            area_id = getattr(area_obj, "area_id", "") or getattr(area_obj, "area", "") or getattr(area_obj, "id", "")
            if not area_id:
                continue

            channels = await self._get_area_channels(area_id)
            for channel_obj in channels:
                channel_id = getattr(channel_obj, "channel_id", "") or getattr(channel_obj, "channel", "") or getattr(channel_obj, "id", "")
                if not channel_id:
                    continue

                group_id = self.ids.createId(make_group_source(area=area_id, channel=channel_id)).number
                result.append(
                    {
                        "group_id": group_id,
                        "group_name": getattr(channel_obj, "name", "") or getattr(channel_obj, "channel_name", "") or channel_id,
                        "member_count": 0,
                        "max_member_count": 0,
                        "oopz_area_id": area_id,
                        "oopz_channel_id": channel_id,
                    }
                )

        return result

    async def get_group_member_info(self, params: Mapping[str, Any]) -> JsonDict:
        group_id = require_int(params, "group_id")
        user_id = require_int(params, "user_id")
        area, channel = self._resolve_group_id(group_id)
        uid = self._resolve_user_id(user_id)

        info = await self.oopz_bot.person.get_person_info(uid)
        return {
            "group_id": group_id,
            "user_id": user_id,
            "nickname": getattr(info, "name", ""),
            "card": "",
            "oopz_area_id": area,
            "oopz_channel_id": channel,
            "oopz_user_id": uid,
        }

    def _resolve_user_id(self, user_id: int | str) -> str:
        record = self.ids.try_resolve_id(user_id)
        if record is None:
            raise ValueError(f"unknown user_id: {user_id}")
        return parse_user_source(record.source)

    def _resolve_group_id(self, group_id: int | str) -> tuple[str, str]:
        record = self.ids.try_resolve_id(group_id)
        if record is None:
            raise ValueError(f"unknown group_id: {group_id}")
        return parse_group_source(record.source)

    def _resolve_send_parts(self, send_parts: V11SendParts) -> V11SendParts:
        resolved_mentions: list[str] = []
        resolved_parts: list[Any] = []

        for part in send_parts.parts:
            if isinstance(part, Mention):
                uid = self._resolve_user_id(part.person)
                resolved_mentions.append(uid)
                resolved_parts.append(Mention(uid))
            else:
                resolved_parts.append(part)

        for mention in send_parts.mention_list:
            uid = self._resolve_user_id(mention)
            if uid not in resolved_mentions:
                resolved_mentions.append(uid)

        return V11SendParts(
            parts=resolved_parts,
            mention_list=resolved_mentions,
            is_mention_all=send_parts.is_mention_all,
        )

    async def _get_area_channels(self, area_id: str) -> list[Any]:
        channels_service = getattr(self.oopz_bot, "channels", None)
        if channels_service is None:
            return []

        for method_name in ("get_area_channels", "get_channels", "list_channels"):
            method = getattr(channels_service, method_name, None)
            if method is None:
                continue
            try:
                channels = await method(area=area_id)
            except TypeError:
                channels = await method(area_id)
            if channels is None:
                return []
            if isinstance(channels, Mapping):
                for key in ("channels", "data", "items", "list"):
                    value = channels.get(key)
                    if isinstance(value, list):
                        return value
                return []
            return list(channels)

        return []

    def _save_message_event_mapping(self, payload: Mapping[str, Any]) -> None:
        if payload.get("post_type") != "message" and payload.get("post_type") != "notice":
            return

        mid = payload.get("message_id")
        original = str(payload.get("original_message_id") or "")
        if not mid or not original:
            return

        self._save_sent_mapping(
            int(mid),
            original,
            detail_type=str(payload.get("message_type") or payload.get("notice_type") or "group"),
            area=str(payload.get("oopz_area_id") or ""),
            channel=str(payload.get("oopz_channel_id") or ""),
            target=str(payload.get("oopz_user_id") or ""),
            user_id=str(payload.get("oopz_user_id") or ""),
        )

    def _save_sent_mapping(
        self,
        message_id: int | str,
        oopz_message_id: str,
        *,
        detail_type: str,
        area: str = "",
        channel: str = "",
        target: str = "",
        user_id: str = "",
        timestamp: str = "",
    ) -> None:
        self.store.save(
            MessageRecord(
                ob_message_id=str(message_id),
                oopz_message_id=oopz_message_id,
                detail_type=detail_type,
                area=area,
                channel=channel,
                target=target,
                user_id=user_id,
                created_at=parse_oopz_timestamp(timestamp),
                raw={},
            )
        )
