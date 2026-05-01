from __future__ import annotations

import logging
import time
from collections import deque
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from oopz_sdk.models.event import HeartbeatEvent, ServerIdEvent

from .event import to_onebot_event
from .message import from_onebot_message
from .types import (
    ActionResponse,
    JsonDict,
    MessageRecord,
    MessageStore,
    OneBotSelf,
    failed,
    make_ob_message_id,
    ok,
    parse_oopz_timestamp,
    require_str,
)

logger = logging.getLogger(__name__)

BAD_REQUEST = 10001
UNSUPPORTED_ACTION = 10002
BAD_PARAM = 10003
INTERNAL_HANDLER_ERROR = 20002

EventSink = Callable[[JsonDict], Awaitable[None] | None]
ActionHandler = Callable[[Mapping[str, Any]], Awaitable[Any]]

if TYPE_CHECKING:
    from oopz_sdk import OopzBot, models


class OneBotV12Adapter:
    """
    Oopz -> OneBot v12 适配器。
    """

    protocol = "onebot.v12"

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
        self.self_id = self_id
        self.self_info: OneBotSelf = {
            "platform": self.platform,
            "user_id": self.self_id,
        }

        self.store = MessageStore(db_path)
        self._event_sinks: list[EventSink] = []
        self._event_queue: deque[JsonDict] = deque(maxlen=1000)

        self._actions: dict[str, ActionHandler] = self._build_actions()

    # ------------------------------------------------------------------
    # Action 注册表
    # ------------------------------------------------------------------

    def _build_actions(self) -> dict[str, ActionHandler]:
        """
        OneBot v12 action -> handler 映射。

        """
        return {
            "get_supported_actions": self.get_supported_actions,
            "get_latest_events": self.get_latest_events,

            "get_status": self.get_status,
            "get_version": self.get_version,

            "send_message": self.send_message,

            "delete_message": self.delete_message,
            "recall_message": self.delete_message,
            "delete_msg": self.delete_message,

            "get_self_info": self.get_self_info,
            "get_user_info": self.get_user_info,
            "get_friend_list": self.get_friend_list,

            "get_guild_info": self.get_guild_info,
            "get_guild_list": self.get_guild_list,
            "set_guild_name": self.set_guild_name,
            "get_guild_member_info": self.get_guild_member_info,
            # "get_guild_member_list": self.not_implemented("get_guild_member_list"),
            "leave_guild": self.not_implemented("leave_guild"),

            "get_channel_info": self.get_channel_info,
            "get_channel_list": self.get_channel_list,
            "set_channel_name": self.set_channel_name,
            "get_channel_member_info": self.get_channel_member_info,
            "get_channel_member_list": self.get_channel_member_list,
            # "leave_channel": self.not_implemented("leave_channel"),

            "cleanup_message_mapping": self.cleanup_message_mapping,
        }

    def not_implemented(self, name: str) -> ActionHandler:
        async def handler(params: Mapping[str, Any]) -> Any:
            raise NotImplementedError(f"{name} is not implemented yet")

        return handler

    # ------------------------------------------------------------------
    # 事件：Oopz Event -> OneBot Event
    # ------------------------------------------------------------------

    async def emit_event(self, event: Any) -> JsonDict:
        """
        转换后推送给所有 sink。
        """
        # 心跳事件不推送给外部，避免干扰。
        if isinstance(event, HeartbeatEvent) or isinstance(event, ServerIdEvent):
            return {}

        payload = to_onebot_event(
            event,
            self_info=self.self_info,
            store=self.store,
        )

        self._event_queue.append(payload)
        logger.debug("emit onebot v12 event: %s", payload)

        for sink in list(self._event_sinks):
            try:
                result = sink(payload)
                if result is not None:
                    await result
            except Exception:
                logger.exception("failed to emit onebot v12 event")

        return payload

    def add_event_sink(self, sink: EventSink) -> None:
        self._event_sinks.append(sink)

    def remove_event_sink(self, sink: EventSink) -> None:
        try:
            self._event_sinks.remove(sink)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Action 入口
    # ------------------------------------------------------------------

    async def call_action_payload(self, payload: Mapping[str, Any]) -> ActionResponse:
        echo = payload.get("echo")

        action = payload.get("action")
        if not isinstance(action, str) or not action:
            return failed(BAD_REQUEST, "action must be a non-empty string", echo=echo)

        params = payload.get("params")
        if not isinstance(params, Mapping):
            return failed(BAD_REQUEST, "params must be an object", echo=echo)

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
            return failed(UNSUPPORTED_ACTION, f"unsupported action: {action}", echo=echo)

        try:
            data = await handler(params)
            return ok(data, echo=echo)
        except NotImplementedError as exc:
            return failed(UNSUPPORTED_ACTION, str(exc), echo=echo)
        except ValueError as exc:
            return failed(BAD_PARAM, str(exc), echo=echo)
        except Exception as exc:
            logger.exception("onebot v12 action failed: %s", action)
            return failed(INTERNAL_HANDLER_ERROR, str(exc), echo=echo)

    async def get_supported_actions(self, params: Mapping[str, Any]) -> list[str]:
        return list(self._actions)

    async def get_latest_events(self, params: Mapping[str, Any]) -> list[JsonDict]:
        limit = int(params.get("limit") or 0)
        events = list(self._event_queue)
        if limit > 0:
            return events[-limit:]
        return events

    async def cleanup_message_mapping(self, params: Mapping[str, Any]) -> JsonDict:
        seconds = int(params.get("older_than_seconds") or 7 * 24 * 3600)
        return {"deleted": self.store.cleanup(seconds)}

    def failed_response(self, retcode: int, message: str, *, echo: Any = None) -> ActionResponse:
        return failed(retcode, message, echo=echo)


    # ------------------------------------------------------------------
    # Action: send_message
    # ------------------------------------------------------------------

    async def send_message(self, params: Mapping[str, Any]) -> JsonDict:
        detail_type = str(params.get("detail_type") or "")
        message = params.get("message") or ""

        send_parts = from_onebot_message(message)

        # reply segment 传的是 OneBot 内部 message_id，需要转回 Oopz 原始 messageId
        reference_message_id = send_parts.reference_message_id
        if reference_message_id:
            ref = self.store.get(reference_message_id)
            if ref is not None:
                reference_message_id = ref.oopz_message_id

        if detail_type == "private":
            user_id = require_str(params, "user_id")

            result = await self.oopz_bot.messages.send_private_message(
                *send_parts.parts,
                target=user_id,
                mention_list=send_parts.mention_list,
                is_mention_all=send_parts.is_mention_all,
                reference_message_id=reference_message_id,
            )

            ob_message_id = self._save_sent_message(
                oopz_message_id=result.message_id,
                detail_type="private",
                target=user_id,
                user_id=user_id,
                timestamp=result.timestamp,
            )

            return {
                "message_id": ob_message_id,
                "time": parse_oopz_timestamp(result.timestamp),
                "original_message_id": result.message_id,
            }

        if detail_type == "channel":
            guild_id = require_str(params, "guild_id")
            channel_id = require_str(params, "channel_id")

            result = await self.oopz_bot.messages.send_message(
                *send_parts.parts,
                area=guild_id,
                channel=channel_id,
                mention_list=send_parts.mention_list,
                is_mention_all=send_parts.is_mention_all,
                reference_message_id=reference_message_id,
            )

            ob_message_id = self._save_sent_message(
                oopz_message_id=result.message_id,
                detail_type="channel",
                area=guild_id,
                channel=channel_id,
                timestamp=result.timestamp,
            )

            return {
                "message_id": ob_message_id,
                "time": parse_oopz_timestamp(result.timestamp),
                "original_message_id": result.message_id,
            }

        if detail_type == "group":
            raise NotImplementedError(
                "detail_type='group' is not supported by this adapter; "
                "use detail_type='channel' with guild_id=area and channel_id=channel"
            )

        raise ValueError(f"unsupported detail_type: {detail_type!r}")


    # ------------------------------------------------------------------
    # Action: delete_message
    # ------------------------------------------------------------------
    async def delete_message(self, params: Mapping[str, Any]) -> None:
        ob_message_id = require_str(params, "message_id")
        record = self.store.get(ob_message_id)

        if record is None:
            # fallback：允许外部直接传 Oopz 原始 message_id + guild/channel
            guild_id = str(params.get("guild_id") or "")
            channel_id = str(params.get("channel_id") or "")
            target = str(params.get("target") or "")

            if not guild_id or not channel_id:
                raise ValueError(
                    "message_id mapping not found. "
                    "Use OneBot internal message_id, or provide guild_id/channel_id."
                )

            result = await self.oopz_bot.messages.recall_message(
                message_id=ob_message_id,
                area=guild_id,
                channel=channel_id,
                target=target,
            )

            if not getattr(result, "ok", True):
                raise RuntimeError(getattr(result, "message", "recall failed"))

            return None

        if record.detail_type == "private":
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

    # ------------------------------------------------------------------
    # 基础信息
    # ------------------------------------------------------------------

    async def get_self_info(self, params: Mapping[str, Any]) -> JsonDict:
        profile: models.Profile = await self.oopz_bot.person.get_self_detail()

        return {
            "user_id": self.self_id,
            "user_name": getattr(profile, "name", ""),
            "user_displayname": "",
            "platform": self.platform,
            "extra": self.model_to_profile_extra(profile),
        }

    async def get_user_info(self, params: Mapping[str, Any]) -> JsonDict:
        user_id = require_str(params, "user_id")

        nicknames_resp = (
            await self.oopz_bot.person.get_person_remark_name(self.self_id)
        ).user_remark_names

        nickname = ""
        for name_model in nicknames_resp:
            if name_model.uid == user_id:
                nickname = name_model.remark_name
                break

        profile = await self.oopz_bot.person.get_person_detail_full(uid=user_id)

        return {
            "user_id": user_id,
            "user_name": getattr(profile, "name", ""),
            "user_displayname": "",
            "user_remark": nickname,
            "extra": self.model_to_profile_extra(profile),
        }

    async def get_friend_list(self, params: Mapping[str, Any]) -> list[JsonDict]:
        nicknames_resp = (
            await self.oopz_bot.person.get_person_remark_name(self.self_id)
        ).user_remark_names

        nickname_dict = {}
        for name_model in nicknames_resp:
            nickname_dict[name_model.uid] = name_model.remark_name

        friendships = await self.oopz_bot.person.get_friendship()

        return [
            {
                "user_id": friend.uid,
                "user_name": friend.name,
                "user_displayname": "",
                "user_remark": nickname_dict.get(friend.uid, ""),
            }
            for friend in friendships
        ]

    async def get_status(self, params: Mapping[str, Any]) -> JsonDict:
        return {
            "good": True,
            "bots": [
                {
                    "self": self.self_info,
                    "online": True,
                }
            ],
        }

    async def get_version(self, params: Mapping[str, Any]) -> JsonDict:
        return {
            "impl": "oopz_sdk",
            "version": "0.1.0",
            "onebot_version": "12",
        }

    # ------------------------------------------------------------------
    # Guild / Area
    # ------------------------------------------------------------------

    async def get_guild_info(self, params: Mapping[str, Any]) -> JsonDict:
        guild_id = require_str(params, "guild_id")
        model: models.AreaInfo = await self.oopz_bot.areas.get_area_info(area=guild_id)

        return {
            "guild_id": guild_id,
            "guild_name": model.name,
            "extra": {
                "avatar": model.avatar,
                "banner": model.banner,
                "code": model.code,
                "desc": model.desc,
                "disable_text_to": model.disable_text_to,
                "disable_voice_to": model.disable_voice_to,
                "edit_count": model.edit_count,
                "home_page_channel_id": model.home_page_channel_id,
                "area_id": model.area_id,
                "is_public": model.is_public,
                "name": model.name,
                "now": model.now,
                "private_channels": model.private_channels,
                "role_list": [rl.model_dump() for rl in model.role_list],
                "subscribed": model.subscribed,
                "area_role_infos": model.area_role_infos.model_dump(),
            },
        }

    async def get_guild_list(self, params: Mapping[str, Any]) -> list[JsonDict]:
        guild_list: list[models.JoinedAreaInfo] = await self.oopz_bot.areas.get_joined_areas()

        return [
            {
                "guild_id": area.area_id,
                "guild_name": area.name,
                "extra": {
                    "code": area.code,
                    "avatar": area.avatar,
                    "banner": area.banner,
                    "level": area.level,
                    "owner": area.owner,
                },
            }
            for area in guild_list
        ]

    async def set_guild_name(self, params: Mapping[str, Any]) -> None:
        guild_id = require_str(params, "guild_id")
        guild_name = require_str(params, "guild_name")

        await self.oopz_bot.areas.edit_area_name(area=guild_id, name=guild_name)
        return None

    async def get_guild_member_info(self, params: Mapping[str, Any]) -> JsonDict:
        guild_id = require_str(params, "guild_id")
        user_id = require_str(params, "user_id")

        nickname_dict = await self.oopz_bot.areas.get_user_area_nicknames(
            area=guild_id,
            uids=[user_id],
        )
        user_name = await self.oopz_bot.person.get_person_detail_full(uid=user_id)

        return {
            "user_id": user_id,
            "user_name": user_name.name,
            "user_displayname": nickname_dict.get(user_id),
            "extra": self.model_to_profile_extra(user_name),
        }

    # ------------------------------------------------------------------
    # Channel
    # ------------------------------------------------------------------

    async def get_channel_info(self, params: Mapping[str, Any]) -> JsonDict:
        _ = require_str(params, "guild_id")
        channel_id = require_str(params, "channel_id")

        model: models.ChannelSetting = await self.oopz_bot.channels.get_channel_setting_info(
            channel=channel_id
        )

        return {
            "channel_id": channel_id,
            "channel_name": model.name,
            "extra": {
                "channel_type": model.channel_type,
                "guild_id": model.area_id,
                "category_id": model.group_id,

                "text_gap_second": model.text_gap_second,
                "voice_quality": model.voice_quality,
                "voice_delay": model.voice_delay,
                "max_member": model.max_member,

                "voice_control_enabled": model.voice_control_enabled,
                "text_control_enabled": model.text_control_enabled,

                "text_roles": model.text_roles,
                "voice_roles": model.voice_roles,

                "access_control_enabled": model.access_control_enabled,
                "accessible_roles": model.accessible_roles,
                "accessible_members": model.accessible_members,

                "member_public": model.member_public,
                "secret": model.secret,
                "has_password": model.has_password,
            },
        }

    async def get_channel_list(self, params: Mapping[str, Any]) -> list[JsonDict]:
        guild_id = require_str(params, "guild_id")
        joined_only = bool(params.get("joined_only") or False)

        # todo joined_only 暂时没有使用。
        _ = joined_only

        model: list[models.ChannelGroupInfo] = await self.oopz_bot.areas.get_area_channels(
            area=guild_id
        )

        result: list[JsonDict] = []

        for group in model:
            for channel in group.channels:
                result.append(
                    {
                        "channel_id": channel.channel_id,
                        "channel_name": channel.name,
                        "guild_id": channel.area_id,
                        "extra": {
                            "channel_type": channel.channel_type,
                            "category_id": channel.group_id,
                            "text_gap_second": channel.settings.text_gap_second,
                            "voice_quality": channel.settings.voice_quality,
                            "voice_delay": channel.settings.voice_delay,
                            "max_member": channel.settings.max_member,

                            "voice_control_enabled": channel.settings.voice_control_enabled,
                            "text_control_enabled": channel.settings.text_control_enabled,

                            "text_roles": channel.settings.text_roles,
                            "voice_roles": channel.settings.voice_roles,

                            "member_public": channel.settings.member_public,
                            "secret": channel.secret,
                        },
                    }
                )

        return result

    async def set_channel_name(self, params: Mapping[str, Any]) -> None:
        guild_id = require_str(params, "guild_id")
        channel_id = require_str(params, "channel_id")
        channel_name = require_str(params, "channel_name")

        await self.oopz_bot.channels.update_channel(
            area=guild_id,
            channel_id=channel_id,
            name=channel_name,
        )
        return None

    async def get_channel_member_info(self, params: Mapping[str, Any]) -> JsonDict:
        guild_id = require_str(params, "guild_id")
        channel_id = require_str(params, "channel_id")
        user_id = require_str(params, "user_id")

        # channel_id 当前只用于符合 OneBot v12 参数语义。
        _ = channel_id

        model: models.UserInfo = await self.oopz_bot.person.get_person_info(user_id)
        nickname_dict = await self.oopz_bot.areas.get_user_area_nicknames(
            area=guild_id,
            uids=[user_id],
        )

        data = self._model_to_userinfo_dict(user_id, model, nickname_dict)
        data["guild_id"] = guild_id
        data["channel_id"] = channel_id
        return data

    async def get_channel_member_list(self, params: Mapping[str, Any]) -> list[JsonDict]:
        guild_id = require_str(params, "guild_id")
        channel_id = require_str(params, "channel_id")

        voice_channel_number_model: models.VoiceChannelMembersResult = (
            await self.oopz_bot.channels.get_voice_channel_members(area=guild_id)
        )

        for channel, member in voice_channel_number_model.channel_members.items():
            if channel == channel_id:
                uids = [user.uid for user in member]
                user_infos: list[models.UserInfo] = await self.oopz_bot.person.get_person_infos_batch(uids)
                nickname_dict = await self.oopz_bot.areas.get_user_area_nicknames(area=guild_id, uids=uids)
                return [
                    self._model_to_userinfo_dict(info.uid, info, nickname_dict) for info in user_infos
                ]
        return []

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _model_to_userinfo_dict(
        user_id: str,
        model: models.UserInfo,
        nickname_dict: Mapping[str, str],
    ) -> dict[str, Any]:
        return {
            "user_id": getattr(model, "uid", "") or user_id,
            "user_name": getattr(model, "name", ""),
            "user_displayname": nickname_dict.get(user_id, ""),
            "extra": {
                "avatar": getattr(model, "avatar", ""),
                "avatar_frame": getattr(model, "avatar_frame", ""),
                "avatar_frame_animation": getattr(model, "avatar_frame_animation", ""),
                "avatar_frame_expire_time": getattr(model, "avatar_frame_expire_time", 0),

                "badges": getattr(model, "badges", None),
                "introduction": getattr(model, "introduction", ""),
                "mark": getattr(model, "mark", ""),
                "mark_expire_time": getattr(model, "mark_expire_time", 0),
                "mark_name": getattr(model, "mark_name", ""),

                "online": getattr(model, "online", False),

                "pid": getattr(model, "pid", ""),
                "status": getattr(model, "status", ""),
                "user_common_id": getattr(model, "user_common_id", ""),

                "member_level": getattr(model, "memberLevel", 0),
                "person_role": getattr(model, "person_role", ""),
                "person_type": getattr(model, "person_type", ""),
            },
        }

    @staticmethod
    def model_to_profile_extra(profile: models.Profile) -> dict[str, Any]:
        return {
            "area_avatar": getattr(profile, "area_avatar", ""),
            "area_max_num": getattr(profile, "area_max_num", 0),
            "area_name": getattr(profile, "area_name", ""),

            "avatar": getattr(profile, "avatar", ""),
            "avatar_frame": getattr(profile, "avatar_frame", ""),
            "avatar_frame_animation": getattr(profile, "avatar_frame_animation", ""),
            "avatar_frame_expire_time": getattr(profile, "avatar_frame_expire_time", 0),

            "badges": getattr(profile, "badges", []),

            "banner": getattr(profile, "banner", ""),
            "card_decoration": getattr(profile, "card_decoration", ""),
            "card_decoration_expire_time": getattr(profile, "card_decoration_expire_time", 0),

            "community_personal_rec": getattr(profile, "community_personal_rec", False),
            "default_avatar": getattr(profile, "default_avatar", False),
            "default_name": getattr(profile, "default_name", False),

            "disabled_end_time": getattr(profile, "disabled_end_time", 0),
            "disabled_start_time": getattr(profile, "disabled_start_time", 0),

            "display_playing_state": getattr(profile, "display_playing_state", None),
            "display_type": getattr(profile, "display_type", ""),

            "fans_count": getattr(profile, "fans_count", 0),
            "fixed_private_message": getattr(profile, "fixed_private_message", False),
            "follow_count": getattr(profile, "follow_count", 0),
            "follow_private": getattr(profile, "follow_private", False),

            "greeting": getattr(profile, "greeting", ""),
            "introduction": getattr(profile, "introduction", ""),
            "ip_address": getattr(profile, "ip_address", ""),
            "is_abroad": getattr(profile, "is_abroad", False),

            "like_count": getattr(profile, "like_count", 0),

            "mark": getattr(profile, "mark", ""),
            "mark_expire_time": getattr(profile, "mark_expire_time", 0),
            "mark_name": getattr(profile, "mark_name", ""),

            "mobile_banner": getattr(profile, "mobile_banner", ""),
            "music_state": getattr(profile, "music_state", ""),
            "mute": getattr(profile, "mute", None),
            "mutual_follow_count": getattr(profile, "mutual_follow_count", 0),

            "name": getattr(profile, "name", ""),
            "online": getattr(profile, "online", False),

            "person_role": getattr(profile, "person_role", ""),
            "person_type": getattr(profile, "person_type", ""),
            "person_vip_end_time": getattr(profile, "person_vip_end_time", 0),
            "person_vip_start_time": getattr(profile, "person_vip_start_time", 0),

            "phone": getattr(profile, "phone", ""),
            "pid": getattr(profile, "pid", ""),
            "pid_level_name": getattr(profile, "pid_level_name", ""),
            "pid_tag_black": getattr(profile, "pid_tag_black", ""),
            "pid_tag_white": getattr(profile, "pid_tag_white", ""),

            "playing_game_image": getattr(profile, "playing_game_image", ""),
            "playing_state": getattr(profile, "playing_state", ""),
            "playing_time": getattr(profile, "playing_time", 0),

            "pwd_set_time": getattr(profile, "pwd_set_time", 0),
            "recommend_area": getattr(profile, "recommend_area", ""),
            "song_state": getattr(profile, "song_state", ""),

            "status": getattr(profile, "status", ""),
            "stealth": getattr(profile, "stealth", False),

            "uid": getattr(profile, "uid", ""),
            "use_booster": getattr(profile, "use_booster", False),
            "user_common_id": getattr(profile, "user_common_id", ""),
            "user_level": getattr(profile, "user_level", 0),

            "vip_id": getattr(profile, "vip_id", ""),
            "voice_disable": getattr(profile, "voice_disable", 0),

            "wx_nickname": getattr(profile, "wx_nickname", ""),
            "wx_union_id": getattr(profile, "wx_union_id", ""),
        }

    def _save_sent_message(
        self,
        *,
        oopz_message_id: str,
        detail_type: str,
        area: str = "",
        channel: str = "",
        target: str = "",
        user_id: str = "",
        timestamp: str = "",
    ) -> str:
        ob_message_id = make_ob_message_id(
            oopz_message_id=oopz_message_id,
            detail_type=detail_type,
            area=area,
            channel=channel,
            target=target,
            user_id=user_id,
        )

        self.store.save(
            MessageRecord(
                ob_message_id=ob_message_id,
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

        return ob_message_id