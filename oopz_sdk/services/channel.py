from __future__ import annotations

import asyncio
import copy
import logging
import re
import time
from typing import Optional, Any, List

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.channel")


class Channel(BaseService):
    """Channel-related platform capabilities."""

    def __init__(
        self,
        bot,
        config: OopzConfig | None = None,
        transport: HttpTransport | None = None,
        signer: Signer | None = None,
    ):
        super().__init__(config, transport, signer, bot=bot)


    def _get_voice_ids_cache_store(self) -> dict[str, dict]:
        store = getattr(self, "_voice_ids_cache", None)
        if not isinstance(store, dict):
            store = {}
            self._voice_ids_cache = store
        return store

    async def get_channel_setting_info(self, channel: str) -> models.ChannelSetting:
        """获取频道设置详情（名称、访问权限等）。"""

        if channel.strip() == "":
            raise ValueError("channel cannot be empty")

        url_path = "/area/v3/channel/setting/info"
        params = {"channel": channel}
        data = await self._request_data("GET", url_path, params=params)
        return models.ChannelSetting.from_api(data)


    async def _rollback_created_channel(
        self,
        channel_id: str,
        area: str,
        message: str,
        context: dict | None = None,
    ) -> dict[str, str]:
        def _error_with_context(error_message: str, cleanup_error: str = "") -> dict[str, str]:
            payload = {"error": error_message}
            if cleanup_error:
                payload["cleanup_error"] = cleanup_error
            if isinstance(context, dict):
                payload.update(context)
            return payload

        cleanup_error = ""
        try:
            rollback_result = await self.delete_channel(channel_id, area=area)
        except Exception as exc:
            cleanup_error = str(exc)
        else:
            if isinstance(rollback_result, models.OperationResult):
                if rollback_result.ok:
                    return _error_with_context(message)
                cleanup_error = str(rollback_result.message or "删除新建频道失败")
            elif isinstance(rollback_result, dict):
                cleanup_error = str(
                    rollback_result.get("error")
                    or rollback_result.get("message")
                    or "删除新建频道失败"
                )
            elif rollback_result:
                return _error_with_context(message)
            else:
                cleanup_error = "删除新建频道失败"

        logger.error("回滚新建频道失败: channel=%s reason=%s", channel_id[:24], cleanup_error)
        return _error_with_context(f"{message}；删除新建频道失败: {cleanup_error}", cleanup_error)

    async def create_channel(
        self,
        area: str,
        name: str,
        group_id: str = "",
        channel_type: models.ChannelType | str = models.ChannelType.TEXT,
    ) -> models.CreateChannelResult:
        """创建频道。"""
        if area.strip() == "":
            raise ValueError("area cannot be empty")
        if name.strip() == "":
            raise ValueError("name cannot be empty")
        if isinstance(channel_type, str):
            try:
                channel_type = models.ChannelType(channel_type.upper())
                channel_type = channel_type.value
            except ValueError as exc:
                allowed = ", ".join(member.value for member in models.ChannelType)
                raise ValueError(f"invalid channel_type: {channel_type!r}, allowed: {allowed}") from exc

        # if group_id is not provided, call area get_area_channels
        # and choose first group as default group to request
        if not group_id:
            groups: list[models.ChannelGroupInfo] = await self._bot.areas.get_area_channels(area)
            if len(groups) >= 1:
                group_id = groups[0].group_id
            else:
                raise ValueError("no channel group found in area, group_id is required")

        body: dict = {
            "area": area,
            "group": group_id,
            "name": name,
            "type": channel_type,
            "secret": False,
            "maxMember": 100,
        }
        # if channel_type == "VOICE":
        #     body["isTemp"] = False

        data = await self._request_data("POST", "/client/v1/area/v1/channel/v1/create", body=body)
        return models.CreateChannelResult.from_api(data)

    async def update_channel(
            self,
            area: str,
            channel_id: str,
            *,
            name: str | None = None,
            text_gap_second: int | None = None,
            voice_quality: str | None = None,
            voice_delay: str | None = None,
            max_member: int | None = None,
            voice_control_enabled: bool | None = None,
            text_control_enabled: bool | None = None,
            access_control_enabled: bool | None = None,
            secret: bool | None = None,
            has_password: bool | None = None,
            password: str | None = None,
            text_roles: list[int] | None = None,
            voice_roles: list[int] | None = None,
            accessible_roles: list[int] | None = None,
            accessible_members: list[str] | None = None,
    ) -> models.OperationResult:
        """修改频道设置。"""

        area = area.strip()
        channel_id = channel_id.strip()

        if area == "":
            raise ValueError("area cannot be empty")
        if channel_id == "":
            raise ValueError("channel_id cannot be empty")

        setting = await self.get_channel_setting_info(channel_id)
        editable_setting = models.ChannelEdit.from_setting(setting, area=area, channel=channel_id)

        def _normalize_int_list(value: list[int], field_name: str) -> list[int]:
            if not isinstance(value, list):
                raise ValueError(f"{field_name} must be a list")
            result: list[int] = []
            for item in value:
                if item is None or isinstance(item, (dict, list, tuple, set)):
                    raise ValueError(f"{field_name} contains invalid item")
                result.append(int(item))
            return result

        def _normalize_member_list(value: list[str], field_name: str) -> list[str]:
            if not isinstance(value, list):
                raise ValueError(f"{field_name} must be a list")
            result: list[str] = []
            for item in value:
                if item is None or isinstance(item, (dict, list, tuple, set)):
                    raise ValueError(f"{field_name} contains invalid item")
                text = str(item).strip()
                if text:
                    result.append(text)
            return result

        # 普通字段覆盖到 model
        if name is not None:
            editable_setting.name = str(name)

        if text_gap_second is not None:
            editable_setting.text_gap_second = int(text_gap_second)

        if voice_quality is not None:
            editable_setting.voice_quality = str(voice_quality)

        if voice_delay is not None:
            editable_setting.voice_delay = str(voice_delay)

        if max_member is not None:
            editable_setting.max_member = int(max_member)

        if voice_control_enabled is not None:
            editable_setting.voice_control_enabled = bool(voice_control_enabled)

        if text_control_enabled is not None:
            editable_setting.text_control_enabled = bool(text_control_enabled)

        if access_control_enabled is not None:
            editable_setting.access_control_enabled = bool(access_control_enabled)

        # 判断密码的更新逻辑
        if has_password: # when has_password is true
            if password is None or str(password).strip() == "":
                raise ValueError("password cannot be empty when has_password is True")
            editable_setting.has_password = True
            editable_setting.password = str(password)

        elif has_password is False: # when has_password is false
            editable_setting.has_password = False
            editable_setting.password = ""

        elif password is not None: # when has_password not none
            raise ValueError("password requires has_password=True")
        # keep original when has_password is none

        # 可以发送消息的group
        if text_roles is not None:
            editable_setting.text_roles = _normalize_int_list(text_roles, "text_roles")

        # 可以加入语音的group
        if voice_roles is not None:
            editable_setting.voice_roles = _normalize_int_list(voice_roles, "voice_roles")

        final_secret = bool(secret) if secret is not None else bool(editable_setting.secret)

        if accessible_roles is not None:
            roles = _normalize_int_list(accessible_roles, "accessible_roles")
            if not final_secret and roles:
                raise ValueError("accessible_roles can only be set when secret is enabled")
            editable_setting.accessible_roles = roles

        if accessible_members is not None:
            members = _normalize_member_list(accessible_members, "accessible_members")
            if not final_secret and members:
                raise ValueError("accessible_members can only be set when secret is enabled")
            editable_setting.accessible_members = members

        # secret 联动
        if secret is not None:
            editable_setting.secret = final_secret
            editable_setting.access_control_enabled = final_secret

            if final_secret:
                members = set(editable_setting.accessible_members or [])
                bot_uid = str(self._config.person_uid or "").strip()
                if bot_uid:
                    members.add(bot_uid)
                editable_setting.accessible_members = list(members)
            else:
                editable_setting.accessible_roles = []
                editable_setting.accessible_members = []

        edit_body = editable_setting.to_request_body()

        resp = await self._request_data("POST", "/area/v3/channel/setting/edit", body=edit_body)

        return models.OperationResult.from_api(resp)


    # async def create_restricted_text_channel(
    #     self,
    #     target_uid: str,
    #     area: Optional[str] = None,
    #     preferred_channel: Optional[str] = None,
    #     name: Optional[str] = None,
    # ) -> dict:
    #     """创建仅指定成员可见的文字频道。"""
    #     target_uid = str(target_uid or "").strip()
    #     request_payload = {"area": area, "target": target_uid}
    #     if not target_uid:
    #         return self._error_payload(
    #             "缺少 target_uid",
    #             payload={**request_payload, "error": "缺少 target_uid"},
    #         )
    #
    #     picked_group = await self._pick_channel_group(area, preferred_channel=preferred_channel)
    #     if isinstance(picked_group, dict) and picked_group.get("error"):
    #         return self._error_payload(
    #             f"获取频道分组失败: {picked_group['error']}",
    #             payload={**request_payload, "error": f"获取频道分组失败: {picked_group['error']}"},
    #         )
    #     group_id = str(picked_group or "")
    #     if not group_id:
    #         return self._error_payload(
    #             "未找到可用频道分组",
    #             payload={**request_payload, "error": "未找到可用频道分组"},
    #         )
    #
    #     default_name = f"登录-{target_uid[-4:]}-{time.strftime('%H%M%S')}"
    #     channel_name = (name or default_name).strip() or "登录"
    #     url_path = "/client/v1/area/v1/channel/v1/create"
    #     body = {
    #         "area": area,
    #         "group": group_id,
    #         "name": channel_name,
    #         "type": "TEXT",
    #         "secret": True,
    #     }
    #     request_payload = {**request_payload, **body}
    #
    #     try:
    #         resp = await self._post(url_path, body)
    #     except Exception as e:
    #         logger.error("创建受限频道异常: %s", e)
    #         return self._error_payload(str(e), payload={**request_payload, "error": str(e)})
    #
    #     raw = resp.text or ""
    #     logger.info("创建受限频道 POST %s -> HTTP %d, body: %s", url_path, resp.status_code, raw[:300])
    #     if resp.status_code != 200:
    #         message = f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")
    #         return self._error_payload(message, payload={**request_payload, "error": message})
    #
    #     try:
    #         result = resp.json()
    #     except Exception:
    #         return self._error_payload(
    #             f"响应非 JSON: {raw[:200]}",
    #             payload={**request_payload, "error": f"响应非 JSON: {raw[:200]}"},
    #         )
    #     if not isinstance(result, dict):
    #         return self._error_payload(
    #             "创建频道响应格式异常",
    #             payload={**request_payload, "error": "创建频道响应格式异常"},
    #         )
    #
    #     if not result.get("status"):
    #         msg = result.get("message") or result.get("error") or "创建频道失败"
    #         return self._error_payload(
    #             str(msg),
    #             payload={**request_payload, **result, "error": str(msg)},
    #         )
    #
    #     data = result.get("data", {})
    #     channel_id = self._extract_channel_id(data) or self._extract_channel_id(result)
    #     if not channel_id:
    #         return self._error_payload(
    #             "创建频道成功，但未能提取频道 ID",
    #             payload={**request_payload, **result, "error": "创建频道成功，但未能提取频道 ID"},
    #         )
    #
    #     setting = await self.get_channel_setting_info(channel_id, as_model=True)
    #     if isinstance(setting, dict):
    #         if setting.get("error"):
    #             logger.warning("获取新频道设置失败，回滚新建频道: %s", setting["error"])
    #             return await self._rollback_created_channel(
    #                 channel_id,
    #                 area,
    #                 f"获取频道设置失败: {setting['error']}",
    #                 context={"area": area, "target": target_uid},
    #             )
    #         logger.warning("获取新频道设置失败，回滚新建频道: 频道设置响应格式异常")
    #         return await self._rollback_created_channel(
    #             channel_id,
    #             area,
    #             "获取频道设置失败: 频道设置响应格式异常",
    #             context={"area": area, "target": target_uid},
    #         )
    #     if setting.payload.get("error"):
    #         logger.warning("获取新频道设置失败，回滚新建频道: %s", setting.payload["error"])
    #         return await self._rollback_created_channel(
    #             channel_id,
    #             area,
    #             f"获取频道设置失败: {setting.payload['error']}",
    #             context={"area": area, "target": target_uid},
    #         )
    #
    #     edit_body = setting.to_edit_body(area=area)
    #     edit_body["channel"] = channel_id
    #     edit_body["name"] = str(setting.name or channel_name)
    #     edit_body["accessControlEnabled"] = True
    #     edit_body["accessible"] = []
    #     edit_body["accessibleMembers"] = [
    #         uid for uid in dict.fromkeys([
    #             str(target_uid),
    #             str(self._config.person_uid or ""),
    #         ]) if uid
    #     ]
    #     edit_body["secret"] = True
    #     edit_body["hasPassword"] = bool(setting.has_password)
    #     edit_body["password"] = str(setting.password or "")
    #
    #     edit_path = "/area/v3/channel/setting/edit"
    #     try:
    #         edit_resp = await self._post(edit_path, edit_body)
    #     except Exception as e:
    #         logger.error("设置受限频道权限异常: %s", e)
    #         return await self._rollback_created_channel(
    #             channel_id,
    #             area,
    #             str(e),
    #             context={"area": area, "target": target_uid},
    #         )
    #
    #     edit_raw = edit_resp.text or ""
    #     logger.info("设置受限频道权限 POST %s -> HTTP %d, body: %s", edit_path, edit_resp.status_code, edit_raw[:300])
    #     if edit_resp.status_code != 200:
    #         return await self._rollback_created_channel(
    #             channel_id,
    #             area,
    #             f"HTTP {edit_resp.status_code}" + (f" | {edit_raw[:200]}" if edit_raw else ""),
    #             context={"area": area, "target": target_uid},
    #         )
    #
    #     try:
    #         edit_result = edit_resp.json()
    #     except Exception:
    #         return await self._rollback_created_channel(
    #             channel_id,
    #             area,
    #             f"权限设置响应非 JSON: {edit_raw[:200]}",
    #             context={"area": area, "target": target_uid},
    #         )
    #     if not isinstance(edit_result, dict):
    #         return await self._rollback_created_channel(
    #             channel_id,
    #             area,
    #             "权限设置响应格式异常",
    #             context={"area": area, "target": target_uid},
    #         )
    #
    #     if not edit_result.get("status"):
    #         msg = edit_result.get("message") or edit_result.get("error") or "权限设置失败"
    #         return await self._rollback_created_channel(
    #             channel_id,
    #             area,
    #             str(msg),
    #             context={"area": area, "target": target_uid},
    #         )
    #
    #     logger.info("创建受限频道成功: channel=%s target=%s", channel_id[:24], target_uid[:12])
    #     return {
    #         "status": True,
    #         "channel": channel_id,
    #         "group": group_id,
    #         "name": edit_body["name"],
    #     }

    async def delete_channel(self, area: str, channel: str) -> models.OperationResult:
        """删除频道。"""
        if channel.strip() == "":
            raise ValueError("channel cannot be empty")
        if area.strip() == "":
            raise ValueError("area cannot be empty")

        params = {"channel": channel, "area": area}

        url_path = f"/client/v1/area/v1/channel/v1/delete"

        resp = await self._request_data("DELETE",url_path, params=params)

        return models.OperationResult.from_api(resp)

    async def enter_channel(self, channel, area,
                      channel_type: str = "TEXT", from_channel: str = "",
                      from_area: str = "", pid: str = "") -> models.ChannelSign:
        """进入指定频道。"""
        url_path = "/area/v2/channel/enter"

        body: dict = {"type": channel_type, "area": area, "channel": channel}
        if channel_type == "VOICE":
            body.update({
                "fromChannel": from_channel,
                "fromArea": from_area,
                "password": "",
                "sign": 1,
                "pid": pid,
            })

        resp = await self._request_data("POST", url_path, body=body)
        return models.ChannelSign.from_api(resp)


    async def leave_voice_channel(self, channel: str, area: Optional[str] = None,
                            target: Optional[str] = None) -> models.OperationResult:
        """退出语音频道。"""
        target = target or self._config.person_uid
        url_path = "/client/v1/area/v1/member/v1/removeFromChannel"
        params = {"area": area, "channel": channel, "target": target}
        resp = await self._request_data("DELETE", url_path, params=params)
        return models.OperationResult.from_api(resp)

    async def _get_voice_channel_ids(self, area: str) -> list[str] | dict[str, str]:
        cache_store = self._get_voice_ids_cache_store()
        cached = cache_store.get(area)
        if cached and time.time() - cached["ts"] < 300:
            return cached["ids"]
        groups: list[models.ChannelGroupInfo] = await self._bot.areas.get_area_channels(area)
        ids = []
        for g in groups:
            for ch in g.channels:
                if ch.channel_type in ("VOICE", "AUDIO"):
                    ids.append(ch.channel_id)
        cache_store[area] = {"ids": ids, "ts": time.time()}
        return ids

    async def get_voice_channel_members(
        self,
        area
    ) -> models.VoiceChannelMembersResult:
        """获取域内各语音频道的在线成员列表。"""
        voice_ids = await self._get_voice_channel_ids(area)

        url_path = "/area/v3/channel/membersByChannels"
        body = {"area": area, "channels": voice_ids}
        resp = await self._request_data("POST", url_path, body=body)
        return models.VoiceChannelMembersResult.from_api(resp)

    async def get_voice_channel_for_user(self, user_uid: str, area: Optional[str] = None) -> Optional[str]:
        """获取用户当前所在的语音频道 ID，不在任何语音频道则返回 None。"""
        members = await self.get_voice_channel_members(area=area)

        for ch_id, ch_members in members.channel_members.items():
            if not ch_members:
                continue
            for m in ch_members:
                if m.uid == user_uid:
                    return ch_id
        return None
