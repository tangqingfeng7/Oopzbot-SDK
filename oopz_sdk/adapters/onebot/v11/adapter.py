from __future__ import annotations

import logging
import math
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
    require_bool,
    parse_bool,
)
from ..utils import model_to_userinfo_extra, model_to_profile_extra

logger = logging.getLogger(__name__)

EventSink = Callable[[JsonDict], Awaitable[None] | None]

if TYPE_CHECKING:
    from oopz_sdk import OopzBot, models

ActionHandler = Callable[[Mapping[str, Any]], Awaitable[Any]]


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
            self_oopz_id: str,
            *,
            platform: str = "oopz",
            db_path: str | Path | None = None,
            enable_area_scoped_group_ban: bool = False,
            enable_set_group_leave_as_area_leave: bool = False,
            enable_set_group_kick_as_area_kick: bool = False,
    ) -> None:
        self.oopz_bot = oopz_bot
        self.platform = platform
        self.self_oopz_id = str(self_oopz_id)

        if db_path is None:
            base = Path.cwd() / ".oopz_sdk"
            base.mkdir(parents=True, exist_ok=True)
            db_path = base / "onebot_v11.sqlite3"

        self.ids = IdStore(db_path)
        self.store = MessageStore(db_path)
        self.self_id = self.ids.createId(make_self_source(self.self_oopz_id)).number

        self._event_sinks: list[EventSink] = []
        self._event_queue: deque[JsonDict] = deque(maxlen=1000)

        self.enable_area_scoped_group_ban = enable_area_scoped_group_ban
        self.enable_set_group_leave_as_area_leave = enable_set_group_leave_as_area_leave
        self.enable_set_group_kick_as_area_kick = enable_set_group_kick_as_area_kick
        self._actions: dict[str, ActionHandler] = self._build_actions()

    # ------------------------------------------------------------------
    # Action 注册表
    # ------------------------------------------------------------------

    def _build_actions(self) -> dict[str, ActionHandler]:
        actions: dict[str, ActionHandler] = {
            # meta / internal
            "get_supported_actions": self.get_supported_actions,
            ".get_supported_actions": self.get_supported_actions,
            "get_latest_events": self.get_latest_events,
            "get_status": self.get_status,
            "get_version_info": self.get_version_info,
            "get_version": self.get_version_info,
            "can_send_image": self.can_send_image,
            "can_send_record": self.can_send_record,

            # message
            "send_msg": self.send_msg,
            "send_private_msg": self.send_private_msg,
            "send_group_msg": self.send_group_msg,
            "delete_msg": self.delete_msg,
            "recall_message": self.delete_msg,
            "get_msg": self.get_msg,

            # user / friend
            "get_login_info": self.get_login_info,
            "get_stranger_info": self.get_stranger_info,
            "get_friend_list": self.get_friend_list,
            "set_friend_add_request": self.set_friend_add_request,

            # group compatibility
            "get_group_info": self.get_group_info,
            "get_group_list": self.get_group_list,
            "get_group_member_info": self.get_group_member_info,
            "set_group_name": self.set_group_name,

            # maintenance
            "cleanup_message_mapping": self.cleanup_message_mapping,
        }

        if self.enable_area_scoped_group_ban:
            actions["set_group_ban"] = self.set_group_ban

        if self.enable_set_group_leave_as_area_leave:
            actions["set_group_leave"] = self.set_group_leave

        if self.enable_set_group_kick_as_area_kick:
            actions["set_group_kick"] = self.set_group_kick
        return actions


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

        handler = self._actions.get(action)
        if handler is None:
            return failed(1404, f"unsupported action: {action}", echo=echo)

        try:
            data = await handler(params)
            return ok(data, echo=echo)
        except ValueError as exc:
            return failed(1400, str(exc), echo=echo)
        except KeyError as exc:
            return failed(1404, str(exc), echo=echo)
        except NotImplementedError as exc:
            return failed(1404, str(exc), echo=echo)
        except Exception as exc:
            logger.exception("onebot v11 action failed: %s", action)
            return failed(1500, str(exc), echo=echo)

    async def get_supported_actions(self, params: Mapping[str, Any]) -> list[str]:
        return list(self._actions)

    async def get_status(self, params: Mapping[str, Any]) -> JsonDict:
        return {"online": True, "good": True}

    async def get_version_info(self, params: Mapping[str, Any]) -> JsonDict:
        return {
            "app_name": "oopz_sdk",
            "app_version": "0.1.0",
            "protocol_version": "v11",
        }

    async def can_send_image(self, params: Mapping[str, Any]) -> JsonDict:
        return {"yes": True}

    async def can_send_record(self, params: Mapping[str, Any]) -> JsonDict:
        return {"yes": False}

    async def get_latest_events(self, params: Mapping[str, Any]) -> list[JsonDict]:
        limit = int(params.get("limit") or 0)
        events = list(self._event_queue)
        return events[-limit:] if limit > 0 else events

    async def cleanup_message_mapping(self, params: Mapping[str, Any]) -> JsonDict:
        seconds = int(params.get("older_than_seconds") or 7 * 24 * 3600)
        return {"deleted": self.store.cleanup(seconds)}


    async def get_login_info(self, params: Mapping[str, Any] | None = None) -> JsonDict:
        profile: models.Profile = await self.oopz_bot.person.get_self_detail()
        return {
            "user_id": self.self_id,
            "nickname": profile.name,
            "extra": model_to_profile_extra(profile)
        }

    async def send_msg(self, params: Mapping[str, Any]) -> JsonDict:
        message_type = str(params.get("message_type") or "")
        if message_type == "private":
            return await self.send_private_msg(params)
        if message_type == "group":
            return await self.send_group_msg(params)
        raise ValueError("message_type, user_id or group_id is required")

    async def send_private_msg(self, params: Mapping[str, Any]) -> JsonDict:
        user_id = require_int(params, "user_id")
        message = params.get("message") or ""

        if truthy(params.get("auto_escape")) and isinstance(message, str):
            send_parts = V11SendParts(
                parts=[message],
                mention_list=[],
                is_mention_all=False,
            )
        else:
            send_parts = from_v11_message(message)

        target = self._resolve_user_id(user_id)
        send_parts = self._resolve_send_parts(send_parts)

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
            raw={
                "message": message,
            }
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

        self.ids.createId(make_group_source(area=area, channel=channel))

        message = params.get("message") or ""

        if truthy(params.get("auto_escape")) and isinstance(message, str):
            send_parts = V11SendParts(
                parts=[message],
                mention_list=[],
                is_mention_all=False,
            )
        else:
            send_parts = from_v11_message(message)

        send_parts = self._resolve_send_parts(send_parts)

        result = await self.oopz_bot.messages.send_message(
            *send_parts.parts,
            area=area,
            channel=channel,
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
            raw={
                "message": message,
            }
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

    async def get_msg(self, params: Mapping[str, Any]) -> JsonDict:
        message_id = require_int(params, "message_id")
        record = self.store.get(str(message_id))

        if record is None:
            raise ValueError(f"message mapping not found: {message_id}")

        raw = record.raw or {}

        # 如果是从事件保存的完整 payload，优先按原 payload 还原
        if raw.get("post_type") == "message":
            message_type = str(raw.get("message_type") or record.detail_type or "")
            return {
                "time": int(raw.get("time") or record.created_at or int(time.time())),
                "message_type": message_type,
                "message_id": message_id,
                "real_id": message_id,
                "sender": raw.get("sender") or {
                    "user_id": int(raw["user_id"]) if str(raw.get("user_id") or "").isdigit() else 0,
                    "nickname": "",
                },
                "message": raw.get("message") or [],
            }

        # 自己发送的消息，raw 可能不完整，只能返回最小结构
        message_type = "private" if record.detail_type == "private" else "group"

        sender: JsonDict = {
            "user_id": self.self_id,
            "nickname": "",
        }

        data: JsonDict = {
            "time": int(record.created_at or int(time.time())),
            "message_type": message_type,
            "message_id": message_id,
            "real_id": message_id,
            "sender": sender,
            "message": raw.get("message") or [],
        }

        if message_type == "group" and record.area and record.channel:
            group_id = self.ids.createId(
                make_group_source(area=record.area, channel=record.channel)
            ).number
            data["group_id"] = group_id

        return data


    async def get_stranger_info(self, params: Mapping[str, Any]) -> JsonDict:
        user_id = require_int(params, "user_id")
        uid = self._resolve_user_id(user_id)
        info: models.UserInfo = await self.oopz_bot.person.get_person_info(uid)
        return {
            "user_id": user_id,
            "nickname": info.name,
            "sex": "unknown",
            "age": 0,
            "extra": model_to_userinfo_extra(info)
        }

    async def get_friend_list(self, params: Mapping[str, Any] | None = None) -> list[JsonDict]:
        friends = await self.oopz_bot.person.get_friendship()
        result: list[JsonDict] = []
        for friend in friends:
            user_id = self.ids.createId(make_user_source(friend.uid)).number
            result.append(
                {
                    "user_id": user_id,
                    "nickname": friend.name,
                    "remark": "",
                    "extra": {
                        "oopz_user_id": friend.uid,
                    }
                }
            )
        return result

    async def get_group_info(self, params: Mapping[str, Any]) -> JsonDict:
        group_id = require_int(params, "group_id")
        area, channel = self._resolve_group_id(group_id)
        name = channel
        try:
            setting = await self.oopz_bot.channels.get_channel_setting_info(channel=channel)
            name = getattr(setting, "name", "") or channel
        except Exception:
            pass
        return {
            "group_id": group_id,
            "group_name": name,
            "member_count": 0,
            "max_member_count": 0,
            "extra": {
                "oopz_area_id": area,
                "oopz_channel_id": channel,
            }
        }

    async def get_group_list(self, params: Mapping[str, Any] | None = None) -> list[JsonDict]:
        areas = await self.oopz_bot.areas.get_joined_areas()
        result: list[JsonDict] = []

        for area_obj in areas:
            area_id = getattr(area_obj, "area_id", "") or getattr(area_obj, "area", "") or getattr(area_obj, "id", "")
            if not area_id:
                continue

            groups = await self.oopz_bot.areas.get_area_channels(area_id)
            for group in groups:
                for channel_obj in group.channels:
                    channel_id = getattr(channel_obj, "channel_id", "")
                    if not channel_id:
                        continue

                    group_id = self.ids.createId(make_group_source(area=area_id, channel=channel_id)).number
                    result.append(
                        {
                            "group_id": group_id,
                            "group_name": getattr(channel_obj, "name", "") or channel_id,
                            "member_count": 0,
                            "max_member_count": 0,
                            "extra": {
                                "oopz_area_id": area_id,
                                "oopz_channel_id": channel_id,
                            }
                        }
                    )

        return result

    async def get_group_member_info(self, params: Mapping[str, Any]) -> JsonDict:
        """
        获取群成员信息。

        OneBot v11 的 group member 是 QQ 群成员模型；
        Oopz 没有完全等价的「频道成员名片 / 群头衔 / 入群时间」概念，
        所以这里返回 v11 标准字段，并把 Oopz 原始字段作为扩展字段保留。
        """
        group_id = require_int(params, "group_id")
        user_id = require_int(params, "user_id")

        area, channel = self._resolve_group_id(group_id)
        uid = self._resolve_user_id(user_id)

        info = await self.oopz_bot.person.get_person_info(uid)
        aud: models.AreaUserDetail = await self.oopz_bot.areas.get_area_user_detail(area, uid)
        # Oopz 当前没有直接等价于 OneBot v11 的 group card。
        # mark_name 更像用户备注/标记名，不一定是群名片，所以默认不给 card 硬塞 nickname。
        card = getattr(info, "mark_name", "") or ""

        response = {
            # OneBot v11 标准字段
            "group_id": group_id,
            "user_id": user_id,
            "nickname": info.name,
            "card": card,
            "sex": "unknown",
            "age": 0,
            "area": "",
            "join_time": 0,
            "last_sent_time": 0,
            "level": str(info.memberLevel),
            "role": "member",
            "unfriendly": False,
            "title": "",
            "title_expire_time": 0,
            "card_changeable": False,
            "shut_up_timestamp": aud.disable_text_to // 1000,

            # 扩展字段，方便调试和高级用户使用
            "extra": model_to_userinfo_extra(info),
        }
        return response

    async def set_group_kick(self, params: Mapping[str, Any]) -> JsonDict:
        group_id = require_int(params, "group_id")
        user_id = require_int(params, "user_id")
        reject_add_request = params.get("reject_add_request", False)

        area, channel = self._resolve_group_id(group_id)
        uid = self._resolve_user_id(user_id)

        if parse_bool(reject_add_request):
            await self.oopz_bot.moderation.block_user_in_area(area, uid)
            return {}
        await self.oopz_bot.moderation.remove_from_area(area, uid)
        return {}

    async def set_group_ban(self, params: Mapping[str, Any]) -> JsonDict:
        group_id = require_int(params, "group_id")
        user_id = require_int(params, "user_id")
        # OneBot v11 的 ban duration 单位是秒，Oopz 的 mute_user / mute_mic duration 单位是分钟，所以这里转换一下。
        duration_seconds = int(params.get("duration", 0) or 0)

        area, channel = self._resolve_group_id(group_id)
        uid = self._resolve_user_id(user_id)

        if duration_seconds > 0:
            duration_minutes = max(1, math.ceil(duration_seconds / 60))
            await self.oopz_bot.moderation.mute_user(area, uid, duration_minutes)
        else:
            await self.oopz_bot.moderation.unmute_user(area, uid)
        return {}

    async def set_group_name(self, params: Mapping[str, Any]) -> JsonDict:
        group_id = require_int(params, "group_id")
        group_name = str(params.get("group_name", "")).strip()

        if group_name == "":
            return {}

        area, channel = self._resolve_group_id(group_id)

        await self.oopz_bot.channels.update_channel(area, channel, name=group_name)
        return {}

    async def set_group_leave(self, params: Mapping[str, Any]) -> JsonDict:
        group_id = require_int(params, "group_id")
        # 暂时不接受is_dismiss参数

        area, channel = self._resolve_group_id(group_id)
        await self.oopz_bot.areas.leave_area(area)
        return {}

    async def get_group_member_list(self, params: Mapping[str, Any]) -> list[JsonDict]:
        raise NotImplementedError

    async def set_friend_add_request(self, params: Mapping[str, Any]) -> JsonDict:
        approve = require_bool(params, "approve")
        remark = str(params.get("remark") or "")
        flag = str(params.get("flag", "")).strip()

        prefix = "oopz_friend_request:"
        if not flag.startswith(prefix):
            raise ValueError("invalid friend request flag")

        rest = flag[len(prefix):]
        parts = rest.split(":", 1)

        if len(parts) != 2:
            raise ValueError("invalid friend request flag")

        request_id_text, uid = parts
        uid = uid.strip()

        if not uid:
            raise ValueError("invalid friend request flag: missing uid")

        try:
            friend_request_id = int(request_id_text)
        except ValueError as exc:
            raise ValueError("invalid friend request flag: invalid request id") from exc

        if approve:
            await self.oopz_bot.person.post_friendship_response(uid, friend_request_id, True)
            if remark:
                await self.oopz_bot.person.set_user_remark_name(uid, remark)
        else:
            await self.oopz_bot.person.post_friendship_response(uid, friend_request_id, False)
        return {}

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

    def _get_payload_extra(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        extra = payload.get("extra")
        if isinstance(extra, Mapping):
            return extra

        oopz_extra = payload.get("oopz_extra")
        if isinstance(oopz_extra, Mapping):
            return oopz_extra

        return {}

    def _save_message_event_mapping(self, payload: Mapping[str, Any]) -> None:
        if payload.get("post_type") not in {"message"}:
            return

        mid = payload.get("message_id")

        extra = self._get_payload_extra(payload)


        original = str(extra.get("oopz_message_id") or "")

        if not mid or not original:
            return

        area = str(payload.get("oopz_area_id") or extra.get("oopz_area_id") or "")
        channel = str(payload.get("oopz_channel_id") or extra.get("oopz_channel_id") or "")
        target = str(payload.get("oopz_target_id") or payload.get("oopz_user_id")
                     or extra.get("oopz_target_id") or extra.get("oopz_user_id") or "")
        user_id = str(payload.get("oopz_user_id") or extra.get("oopz_user_id") or "")

        self._save_sent_mapping(
            int(mid),
            original,
            detail_type=str(payload.get("message_type") or payload.get("notice_type") or "group"),
            area=area,
            channel=channel,
            target=target,
            user_id=user_id,
            raw=payload,
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
            raw: Mapping[str, Any] | None = None,
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
                raw=dict(raw or {}),
            )
        )


def truthy(value: Any) -> bool:
    return value is True or str(value).lower() in {"true", "1", "yes"}
