from __future__ import annotations

import asyncio
import copy
import logging
import re
import time
from typing import Optional

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.transport.http import HttpTransport

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.channel")


class Channel(BaseService):
    """Channel-related platform capabilities."""

    def __init__(
        self,
        config_or_bot,
        config: OopzConfig | None = None,
        transport: HttpTransport | None = None,
        signer: Signer | None = None,
    ):
        if config is None:
            bot = None
            config = config_or_bot
        else:
            bot = config_or_bot
        resolved_signer = signer or Signer(config)
        resolved_transport = transport or HttpTransport(config, resolved_signer)
        super().__init__(config, resolved_transport, resolved_signer, bot=bot)

    @staticmethod
    def _extract_channel_id(payload: object) -> Optional[str]:
        if isinstance(payload, dict):
            for key in ("channel", "channelId", "id", "chatChannel", "sessionChannel"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for value in payload.values():
                found = Channel._extract_channel_id(value)
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = Channel._extract_channel_id(item)
                if found:
                    return found
        elif isinstance(payload, str) and payload.strip():
            text = payload.strip()
            if re.fullmatch(r"[0-9A-Za-z]{16,64}", text):
                return text
        return None

    def _get_voice_ids_cache_store(self) -> dict[str, dict]:
        store = getattr(self, "_voice_ids_cache", None)
        if not isinstance(store, dict):
            store = {}
            self._voice_ids_cache = store
        return store

    def _invalidate_voice_ids_cache(self, area: str | None = None) -> None:
        store = self._get_voice_ids_cache_store()
        if area is None:
            store.clear()
            return
        store.pop(str(area), None)

    @staticmethod
    def _to_channel_model(payload: dict, area: str = "") -> models.Channel:
        return models.Channel(
            id=str(payload.get("id") or payload.get("channel") or ""),
            name=str(payload.get("name") or ""),
            type=str(payload.get("type") or ""),
            area=str(area or payload.get("area") or ""),
            group=str(payload.get("group") or ""),
            secret=bool(payload.get("secret")),
            payload=dict(payload),
        )

    @classmethod
    def _to_channel_group_model(cls, payload: dict, *, area: str = "") -> models.ChannelGroup:
        channels = payload.get("channels", [])
        if channels is None:
            channels = []
        if not isinstance(channels, list):
            raise ValueError("channel groups响应格式异常")
        for channel in channels:
            if not isinstance(channel, dict):
                raise ValueError("channel groups响应格式异常")
        return models.ChannelGroup(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            channels=[
                cls._to_channel_model(ch, area=area)
                for ch in channels
            ],
            payload=dict(payload),
        )

    @staticmethod
    def _to_channel_setting_model(payload: dict) -> models.ChannelSetting:
        def _normalize_list_field(field_name: str, *, stringify: bool = False) -> list:
            value = payload.get(field_name)
            if value is None:
                return []
            if not isinstance(value, list):
                raise ValueError("频道设置响应格式异常")
            normalized = []
            for item in value:
                if item is None or isinstance(item, (dict, list, tuple, set)):
                    raise ValueError("频道设置响应格式异常")
                if stringify:
                    text = str(item).strip()
                    if text:
                        normalized.append(text)
                    continue
                normalized.append(item)
            return normalized

        text_roles = _normalize_list_field("textRoles")
        voice_roles = _normalize_list_field("voiceRoles")
        accessible = _normalize_list_field("accessible")
        accessible_members = _normalize_list_field("accessibleMembers", stringify=True)
        return models.ChannelSetting(
            channel=str(payload.get("channel") or payload.get("id") or ""),
            area=str(payload.get("area") or ""),
            name=str(payload.get("name") or ""),
            text_gap_second=int(payload.get("textGapSecond", 0) or 0),
            voice_quality=str(payload.get("voiceQuality") or "64k"),
            voice_delay=str(payload.get("voiceDelay") or "LOW"),
            max_member=int(payload.get("maxMember", 30000) or 30000),
            voice_control_enabled=bool(payload.get("voiceControlEnabled")),
            text_control_enabled=bool(payload.get("textControlEnabled")),
            text_roles=text_roles,
            voice_roles=voice_roles,
            access_control_enabled=bool(payload.get("accessControlEnabled")),
            accessible=accessible,
            accessible_members=accessible_members,
            secret=bool(payload.get("secret")),
            has_password=bool(payload.get("hasPassword")),
            password=str(payload.get("password") or ""),
            payload=dict(payload),
        )

    @staticmethod
    def _ok_result(payload: dict, *, response=None, message: str = "") -> models.OperationResult:
        return models.OperationResult(
            ok=True,
            message=str(payload.get("message") or message),
            payload=payload,
            response=response,
        )

    async def get_area_channels(
        self,
        area: Optional[str] = None,
        quiet: bool = False,
        *,
        as_model: bool = False,
    ) -> list | dict | models.ChannelGroupsResult:
        """获取域内完整频道列表（含分组）。"""
        area = self._resolve_area(area)
        url_path = "/client/v1/area/v1/detail/v1/channels"
        params = {"area": area}

        try:
            resp = await self._await_if_needed(self._get(url_path, params=params))
            if resp.status_code != 200:
                logger.error("获取频道列表失败: HTTP %d", resp.status_code)
                if as_model:
                    return self._model_error(
                        models.ChannelGroupsResult,
                        f"HTTP {resp.status_code}",
                        response=resp,
                    )
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                logger.error("获取频道列表失败: %s", msg)
                if as_model:
                    return self._model_error(
                        models.ChannelGroupsResult,
                        msg,
                        response=resp,
                        payload=result,
                    )
                return {"error": msg}
            groups = result.get("data", [])
            if not isinstance(groups, list):
                logger.error("获取频道列表失败: 响应格式异常")
                if as_model:
                    return self._model_error(
                        models.ChannelGroupsResult,
                        "channel groups响应格式异常",
                        response=resp,
                    )
                return {"error": "channel groups响应格式异常"}
            invalid_payload = self._invalid_dict_item_payload(
                groups,
                "channel groups响应格式异常",
                list_key="groups",
                payload={"groups": groups},
            )
            if invalid_payload:
                if as_model:
                    return self._model_error(
                        models.ChannelGroupsResult,
                        "channel groups响应格式异常",
                        response=resp,
                        payload=invalid_payload,
                    )
                return invalid_payload
            for group in groups:
                channels = group.get("channels", [])
                if channels is None:
                    channels = []
                invalid_channels_payload = self._invalid_dict_item_payload(
                    channels,
                    "channel groups响应格式异常",
                    list_key="channels",
                    payload={"groups": groups},
                )
                if invalid_channels_payload:
                    if as_model:
                        return self._model_error(
                            models.ChannelGroupsResult,
                            "channel groups响应格式异常",
                            response=resp,
                            payload=invalid_channels_payload,
                        )
                    return invalid_channels_payload
            if not quiet:
                total = sum(len(g.get("channels") or []) for g in groups)
                logger.info("获取频道列表: %d 个频道, %d 个分组", total, len(groups))
            if as_model:
                return models.ChannelGroupsResult(
                    groups=[
                        self._to_channel_group_model(group, area=str(area))
                        for group in groups
                    ],
                    payload={"groups": groups},
                    response=resp,
                )
            return groups
        except Exception as e:
            logger.error("获取频道列表异常: %s", e)
            if as_model:
                return self._model_error(models.ChannelGroupsResult, str(e))
            return {"error": str(e)}

    async def get_channel_setting_info(self, channel: str, *, as_model: bool = False) -> dict | models.ChannelSetting:
        """获取频道设置详情（名称、访问权限等）。"""
        channel = str(channel or "").strip()
        if not channel:
            if as_model:
                return self._model_error(
                    models.ChannelSetting,
                    "缺少 channel",
                    channel="",
                )
            return {"error": "缺少 channel"}

        url_path = "/area/v3/channel/setting/info"
        params = {"channel": channel}
        try:
            resp = await self._await_if_needed(self._get(url_path, params=params))
            if resp.status_code != 200:
                logger.error("获取频道设置失败: HTTP %d", resp.status_code)
                if as_model:
                    return self._model_error(
                        models.ChannelSetting,
                        f"HTTP {resp.status_code}",
                        response=resp,
                        channel=channel,
                    )
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                logger.error("获取频道设置失败: %s", msg)
                if as_model:
                    return self._model_error(
                        models.ChannelSetting,
                        msg,
                        response=resp,
                        payload=result,
                        channel=channel,
                    )
                return {"error": msg}
            data = result.get("data", {})
            if not isinstance(data, dict):
                if as_model:
                    return self._model_error(
                        models.ChannelSetting,
                        "频道设置响应格式异常",
                        response=resp,
                        channel=channel,
                    )
                return {"error": "频道设置响应格式异常"}
            try:
                model = self._to_channel_setting_model(data)
            except ValueError:
                if as_model:
                    return self._model_error(
                        models.ChannelSetting,
                        "频道设置响应格式异常",
                        response=resp,
                        channel=channel,
                )
                return {"error": "频道设置响应格式异常"}
            if as_model:
                return model
            return data
        except Exception as e:
            logger.error("获取频道设置异常: %s", e)
            if as_model:
                return self._model_error(
                    models.ChannelSetting,
                    str(e),
                    channel=channel,
                )
            return {"error": str(e)}

    async def _pick_channel_group(
        self,
        area: str,
        preferred_channel: Optional[str] = None,
        preferred_group_name: Optional[str] = None,
    ) -> Optional[str] | dict[str, str]:
        groups = await self.get_area_channels(area=area, quiet=True)
        if isinstance(groups, dict) and groups.get("error"):
            return {"error": str(groups["error"])}
        if not isinstance(groups, list):
            return {"error": "channel groups响应格式异常"}
        preferred_channel = str(preferred_channel or "").strip()
        preferred_group_name = str(preferred_group_name or "").strip().lower()

        fallback = None
        for group in groups:
            group_id = str(group.get("id") or "").strip()
            if not group_id:
                continue
            group_name = str(group.get("name") or "").strip().lower()
            if not fallback:
                fallback = group_id
            if preferred_group_name and group_name == preferred_group_name:
                return group_id
            channels = group.get("channels") or []
            if preferred_channel and any(str(ch.get("id") or "") == preferred_channel for ch in channels):
                return group_id
        if preferred_group_name:
            return None
        return fallback

    async def _rollback_created_channel(
        self,
        channel_id: str,
        area: str,
        message: str,
    ) -> dict[str, str]:
        cleanup_error = ""
        try:
            rollback_result = await self.delete_channel(channel_id, area=area)
        except Exception as exc:
            cleanup_error = str(exc)
        else:
            if isinstance(rollback_result, models.OperationResult):
                if rollback_result.ok:
                    return {"error": message}
                cleanup_error = str(rollback_result.message or "删除新建频道失败")
            elif isinstance(rollback_result, dict):
                cleanup_error = str(
                    rollback_result.get("error")
                    or rollback_result.get("message")
                    or "删除新建频道失败"
                )
            elif rollback_result:
                return {"error": message}
            else:
                cleanup_error = "删除新建频道失败"

        logger.error("回滚新建频道失败: channel=%s reason=%s", channel_id[:24], cleanup_error)
        return {
            "error": f"{message}；删除新建频道失败: {cleanup_error}",
            "cleanup_error": cleanup_error,
        }

    async def create_channel(
        self,
        area: Optional[str] = None,
        name: str = "",
        channel_type: str = "text",
        group_id: str = "",
    ) -> models.OperationResult:
        """创建频道。"""
        area = self._resolve_area(area)
        name = str(name or "").strip()
        if not name:
            return models.OperationResult(ok=False, message="频道名称不能为空")

        if not group_id:
            picked_group = await self._pick_channel_group(area)
            if isinstance(picked_group, dict) and picked_group.get("error"):
                return models.OperationResult(
                    ok=False,
                    message=f"获取频道分组失败: {picked_group['error']}",
                )
            group_id = str(picked_group or "")
            if not group_id:
                return models.OperationResult(ok=False, message="未找到可用频道分组")

        type_map = {"text": "TEXT", "voice": "VOICE", "audio": "VOICE"}
        resolved_type = type_map.get(channel_type.lower(), channel_type.upper())
        body: dict = {
            "area": area,
            "group": group_id,
            "name": name,
            "type": resolved_type,
            "secret": False,
            "maxMember": 100,
        }
        if resolved_type == "VOICE":
            body["isTemp"] = False

        try:
            resp = await self._await_if_needed(self._post("/client/v1/area/v1/channel/v1/create", body))
        except Exception as e:
            logger.error("创建频道异常: %s", e)
            return models.OperationResult(ok=False, message=str(e), payload=body)

        raw = resp.text or ""
        if resp.status_code != 200:
            return models.OperationResult(
                ok=False,
                message=f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else ""),
                payload=body,
                response=resp,
            )

        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(ok=False, message=f"响应非 JSON: {raw[:200]}", payload=body, response=resp)
        if not isinstance(result, dict):
            return models.OperationResult(
                ok=False,
                message="创建频道响应格式异常",
                payload={"payload": result},
                response=resp,
            )

        if not result.get("status"):
            msg = result.get("message") or "创建频道失败"
            code = result.get("code") or result.get("errorCode") or ""
            logger.warning("创建频道被拒: %s (code=%s), body=%s", msg, code, body)
            hint = "（可能需要域主/管理员权限）" if "服务" in msg or "权限" in msg else ""
            return models.OperationResult(ok=False, message=f"{msg}{hint}", payload=result, response=resp)

        data = result.get("data", {})
        channel_id = self._extract_channel_id(data) or self._extract_channel_id(result)
        if resolved_type == "VOICE":
            self._invalidate_voice_ids_cache(area)
        return models.OperationResult(
            ok=True,
            message="频道已创建",
            payload={"channel": channel_id or "", "name": name, "raw": result},
            response=resp,
        )

    async def update_channel(
        self,
        area: Optional[str] = None,
        channel_id: str = "",
        overrides: Optional[dict] = None,
        *,
        name: str = "",
    ) -> models.OperationResult:
        """修改频道设置。"""
        area = self._resolve_area(area)
        channel_id = str(channel_id or "").strip()
        if not channel_id:
            return models.OperationResult(ok=False, message="缺少 channel_id")

        setting = await self.get_channel_setting_info(channel_id, as_model=True)
        if isinstance(setting, dict):
            if setting.get("error"):
                return models.OperationResult(ok=False, message=f"获取频道设置失败: {setting['error']}")
            return models.OperationResult(ok=False, message="获取频道设置失败: 频道设置响应格式异常")
        if setting.payload.get("error"):
            return models.OperationResult(ok=False, message=f"获取频道设置失败: {setting.payload['error']}")

        _BOOL_FIELDS = ("secret", "hasPassword", "voiceControlEnabled",
                        "textControlEnabled", "accessControlEnabled")
        _INT_FIELDS = ("textGapSecond", "maxMember")
        _STR_FIELDS = ("name", "voiceQuality", "voiceDelay", "password")
        _LIST_FIELDS = ("textRoles", "voiceRoles", "accessible")

        edit_body = setting.to_edit_body(area=area)
        edit_body["channel"] = channel_id

        if name:
            edit_body["name"] = name
        if overrides:
            for k, v in overrides.items():
                if k in _INT_FIELDS:
                    edit_body[k] = int(v or 0)
                elif k in _BOOL_FIELDS:
                    edit_body[k] = bool(v)
                elif k in _STR_FIELDS:
                    edit_body[k] = str(v or "")
                elif k in _LIST_FIELDS:
                    if not isinstance(v, list):
                        return models.OperationResult(ok=False, message="频道设置响应格式异常")
                    if any(item is None or isinstance(item, (dict, list, tuple, set)) for item in v):
                        return models.OperationResult(ok=False, message="频道设置响应格式异常")
                    edit_body[k] = list(v)
                elif k == "accessibleMembers":
                    if not isinstance(v, list):
                        return models.OperationResult(ok=False, message="频道设置响应格式异常")
                    members = []
                    for item in v:
                        if item is None or isinstance(item, (dict, list, tuple, set)):
                            return models.OperationResult(ok=False, message="频道设置响应格式异常")
                        text = str(item).strip()
                        if text:
                            members.append(text)
                    edit_body[k] = members
                elif k in edit_body:
                    edit_body[k] = v

            if "secret" in overrides:
                want_secret = bool(overrides["secret"])
                edit_body["secret"] = want_secret
                edit_body["accessControlEnabled"] = want_secret
                if want_secret:
                    if "accessibleMembers" in overrides and isinstance(overrides["accessibleMembers"], list):
                        members = set(str(u) for u in overrides["accessibleMembers"] if u)
                    else:
                        members = set(edit_body.get("accessibleMembers") or [])
                    bot_uid = str(self._config.person_uid or "")
                    if bot_uid:
                        members.add(bot_uid)
                    edit_body["accessibleMembers"] = list(members)
                else:
                    edit_body["accessible"] = []
                    edit_body["accessibleMembers"] = []

        try:
            resp = await self._await_if_needed(self._post("/area/v3/channel/setting/edit", edit_body))
        except Exception as e:
            logger.error("更新频道异常: %s", e)
            return models.OperationResult(ok=False, message=str(e), payload=edit_body)

        raw = resp.text or ""
        if resp.status_code != 200:
            logger.error("更新频道 HTTP %d: %s", resp.status_code, raw[:300])
            return models.OperationResult(
                ok=False,
                message=f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else ""),
                payload=edit_body,
                response=resp,
            )

        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(ok=False, message=f"响应非 JSON: {raw[:200]}", payload=edit_body, response=resp)
        if not isinstance(result, dict):
            return models.OperationResult(
                ok=False,
                message="更新频道响应格式异常",
                payload={"payload": result},
                response=resp,
            )

        if not result.get("status"):
            return models.OperationResult(ok=False, message=str(result.get("message") or "更新频道失败"), payload=result, response=resp)

        return self._ok_result(result, response=resp, message="频道已更新")

    async def create_restricted_text_channel(
        self,
        target_uid: str,
        area: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict:
        """创建仅指定成员可见的文字频道。"""
        area = area or self._config.default_area
        target_uid = str(target_uid or "").strip()
        if not target_uid:
            return {"error": "缺少 target_uid"}

        picked_group = await self._pick_channel_group(area, preferred_channel=preferred_channel)
        if isinstance(picked_group, dict) and picked_group.get("error"):
            return {"error": f"获取频道分组失败: {picked_group['error']}"}
        group_id = str(picked_group or "")
        if not group_id:
            return {"error": "未找到可用频道分组"}

        default_name = f"登录-{target_uid[-4:]}-{time.strftime('%H%M%S')}"
        channel_name = (name or default_name).strip() or "登录"
        url_path = "/client/v1/area/v1/channel/v1/create"
        body = {
            "area": area,
            "group": group_id,
            "name": channel_name,
            "type": "TEXT",
            "secret": True,
        }

        try:
            resp = await self._await_if_needed(self._post(url_path, body))
        except Exception as e:
            logger.error("创建受限频道异常: %s", e)
            return {"error": str(e)}

        raw = resp.text or ""
        logger.info("创建受限频道 POST %s -> HTTP %d, body: %s", url_path, resp.status_code, raw[:300])
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")}

        try:
            result = resp.json()
        except Exception:
            return {"error": f"响应非 JSON: {raw[:200]}"}
        if not isinstance(result, dict):
            return {"error": "创建频道响应格式异常"}

        if not result.get("status"):
            msg = result.get("message") or result.get("error") or "创建频道失败"
            return {"error": str(msg)}

        data = result.get("data", {})
        channel_id = self._extract_channel_id(data) or self._extract_channel_id(result)
        if not channel_id:
            return {"error": "创建频道成功，但未能提取频道 ID"}

        setting = await self.get_channel_setting_info(channel_id, as_model=True)
        if isinstance(setting, dict):
            if setting.get("error"):
                logger.warning("获取新频道设置失败，回滚新建频道: %s", setting["error"])
                return await self._rollback_created_channel(
                    channel_id,
                    area,
                    f"获取频道设置失败: {setting['error']}",
                )
            logger.warning("获取新频道设置失败，回滚新建频道: 频道设置响应格式异常")
            return await self._rollback_created_channel(
                channel_id,
                area,
                "获取频道设置失败: 频道设置响应格式异常",
            )
        if setting.payload.get("error"):
            logger.warning("获取新频道设置失败，回滚新建频道: %s", setting.payload["error"])
            return await self._rollback_created_channel(
                channel_id,
                area,
                f"获取频道设置失败: {setting.payload['error']}",
            )

        edit_body = setting.to_edit_body(area=area)
        edit_body["channel"] = channel_id
        edit_body["name"] = str(setting.name or channel_name)
        edit_body["accessControlEnabled"] = True
        edit_body["accessible"] = []
        edit_body["accessibleMembers"] = [
            uid for uid in dict.fromkeys([
                str(target_uid),
                str(self._config.person_uid or ""),
            ]) if uid
        ]
        edit_body["secret"] = True
        edit_body["hasPassword"] = bool(setting.has_password)
        edit_body["password"] = str(setting.password or "")

        edit_path = "/area/v3/channel/setting/edit"
        try:
            edit_resp = await self._await_if_needed(self._post(edit_path, edit_body))
        except Exception as e:
            logger.error("设置受限频道权限异常: %s", e)
            return await self._rollback_created_channel(channel_id, area, str(e))

        edit_raw = edit_resp.text or ""
        logger.info("设置受限频道权限 POST %s -> HTTP %d, body: %s", edit_path, edit_resp.status_code, edit_raw[:300])
        if edit_resp.status_code != 200:
            return await self._rollback_created_channel(
                channel_id,
                area,
                f"HTTP {edit_resp.status_code}" + (f" | {edit_raw[:200]}" if edit_raw else ""),
            )

        try:
            edit_result = edit_resp.json()
        except Exception:
            return await self._rollback_created_channel(
                channel_id,
                area,
                f"权限设置响应非 JSON: {edit_raw[:200]}",
            )
        if not isinstance(edit_result, dict):
            return await self._rollback_created_channel(
                channel_id,
                area,
                "权限设置响应格式异常",
            )

        if not edit_result.get("status"):
            msg = edit_result.get("message") or edit_result.get("error") or "权限设置失败"
            return await self._rollback_created_channel(channel_id, area, str(msg))

        logger.info("创建受限频道成功: channel=%s target=%s", channel_id[:24], target_uid[:12])
        return {
            "status": True,
            "channel": channel_id,
            "group": group_id,
            "name": edit_body["name"],
        }

    async def delete_channel(self, channel: str, area: Optional[str] = None) -> models.OperationResult:
        """删除频道。"""
        area = area or self._config.default_area
        channel = str(channel or "").strip()
        if not channel:
            return models.OperationResult(ok=False, message="缺少 channel")

        url_path = f"/client/v1/area/v1/channel/v1/delete?channel={channel}&area={area}"

        try:
            resp = await self._await_if_needed(self._delete(url_path))
        except Exception as e:
            logger.error("删除频道异常: %s", e)
            return models.OperationResult(ok=False, message=str(e))

        raw = resp.text or ""
        logger.info("删除频道 DELETE %s -> HTTP %d, body: %s", url_path, resp.status_code, raw[:300])
        if resp.status_code != 200:
            return models.OperationResult(
                ok=False,
                message=f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else ""),
                response=resp,
            )

        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(ok=False, message=f"响应非 JSON: {raw[:200]}", response=resp)
        if not isinstance(result, dict):
            return models.OperationResult(
                ok=False,
                message="删除频道响应格式异常",
                payload={"payload": result},
                response=resp,
            )

        if result.get("status") is True:
            self._invalidate_voice_ids_cache(area)
            return self._ok_result(result, response=resp, message="已删除频道")

        err = result.get("message") or result.get("error") or str(result)
        logger.error("删除频道失败: %s", err)
        return models.OperationResult(ok=False, message=str(err), payload=result, response=resp)

    async def enter_channel(self, channel: Optional[str] = None, area: Optional[str] = None,
                      channel_type: str = "TEXT", from_channel: str = "",
                      from_area: str = "", pid: str = "") -> dict:
        """进入指定频道。"""
        area = area or self._config.default_area
        channel = channel or self._config.default_channel
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

        try:
            resp = await self._await_if_needed(self._post(url_path, body))
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                return {"error": result.get("message") or "未知错误"}
            return result.get("data", {})
        except Exception as e:
            logger.error("进入频道异常: %s", e)
            return {"error": str(e)}

    async def leave_voice_channel(self, channel: str, area: Optional[str] = None,
                            target: Optional[str] = None) -> dict:
        """退出语音频道。"""
        area = area or self._config.default_area
        target = target or self._config.person_uid
        url_path = "/client/v1/area/v1/member/v1/removeFromChannel"
        query = f"?area={area}&channel={channel}&target={target}"
        full_path = url_path + query

        try:
            resp = await self._await_if_needed(
                self._request(
                    "DELETE",
                    url_path,
                    params={"area": area, "channel": channel, "target": target},
                )
            )
        except Exception as e:
            logger.error("退出语音频道异常: %s", e)
            return {"error": str(e)}

        raw = resp.text or ""
        logger.info("退出语音频道 DELETE %s -> HTTP %d", full_path, resp.status_code)

        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")}

        try:
            result = resp.json()
        except Exception:
            return {"error": f"响应非 JSON: {raw[:200]}"}

        if result.get("status") is True:
            logger.info("已退出语音频道")
            return {"status": True, "message": "已退出语音频道"}

        err = result.get("message") or result.get("error") or str(result)
        logger.error("退出语音频道失败: %s", err)
        return {"error": err}

    async def _get_voice_channel_ids(self, area: str) -> list[str] | dict[str, str]:
        cache_store = self._get_voice_ids_cache_store()
        cached = cache_store.get(area)
        if cached and time.time() - cached["ts"] < 300:
            return cached["ids"]
        groups = await self.get_area_channels(area, quiet=True)
        if isinstance(groups, dict) and groups.get("error"):
            return {"error": str(groups["error"])}
        if not isinstance(groups, list):
            return {"error": "channel groups响应格式异常"}
        ids = []
        for g in groups:
            for ch in g.get("channels") or []:
                if str(ch.get("type", "")).upper() in ("VOICE", "AUDIO"):
                    ids.append(ch["id"])
        cache_store[area] = {"ids": ids, "ts": time.time()}
        return ids

    async def get_voice_channel_members(
        self,
        area: Optional[str] = None,
        *,
        as_model: bool = False,
    ) -> dict | models.VoiceChannelMembersResult:
        """获取域内各语音频道的在线成员列表。"""
        area = self._resolve_area(area)
        voice_ids = await self._await_if_needed(self._get_voice_channel_ids(area))
        if isinstance(voice_ids, dict) and voice_ids.get("error"):
            if as_model:
                return self._model_error(
                    models.VoiceChannelMembersResult,
                    str(voice_ids["error"]),
                    payload=voice_ids,
                )
            return voice_ids
        if not voice_ids:
            if as_model:
                return models.VoiceChannelMembersResult()
            return {}

        url_path = "/area/v3/channel/membersByChannels"
        body = {"area": area, "channels": voice_ids}
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = await self._await_if_needed(self._post(url_path, body))
                if resp.status_code == 429:
                    wait = min(2 ** attempt, 4)
                    logger.warning("获取语音频道成员被限流 (429)，%ds 后重试 (%d/%d)", wait, attempt + 1, max_retries)
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.error("获取语音频道成员失败: HTTP %d", resp.status_code)
                    if as_model:
                        return self._model_error(
                            models.VoiceChannelMembersResult,
                            f"HTTP {resp.status_code}",
                            response=resp,
                        )
                    return {"error": f"HTTP {resp.status_code}"}
                result = resp.json()
                if not result.get("status"):
                    if as_model:
                        return self._model_error(
                            models.VoiceChannelMembersResult,
                            self._error_message(result),
                            response=resp,
                            payload=result,
                        )
                    return {"error": self._error_message(result)}
                payload_data = result.get("data", {})
                if not isinstance(payload_data, dict):
                    if as_model:
                        return self._model_error(
                            models.VoiceChannelMembersResult,
                            "voice channel members响应格式异常",
                            response=resp,
                        )
                    logger.error("获取语音频道成员失败: 响应格式异常")
                    return {"error": "voice channel members响应格式异常"}
                data = payload_data.get("channelMembers", {})
                if not isinstance(data, dict):
                    if as_model:
                        return self._model_error(
                            models.VoiceChannelMembersResult,
                            "voice channel members响应格式异常",
                            response=resp,
                        )
                    logger.error("获取语音频道成员失败: channelMembers格式异常")
                    return {"error": "voice channel members响应格式异常"}
                for channel_id, members in data.items():
                    invalid_members_payload = self._invalid_dict_item_payload(
                        members,
                        "voice channel members响应格式异常",
                        list_key=f"channelMembers.{channel_id}",
                        payload=result,
                    )
                    if invalid_members_payload:
                        if as_model:
                            return self._model_error(
                                models.VoiceChannelMembersResult,
                                "voice channel members响应格式异常",
                                response=resp,
                                payload=invalid_members_payload,
                            )
                        return invalid_members_payload
                if as_model:
                    return models.VoiceChannelMembersResult(
                        channels={
                            str(channel_id): [
                                models.Member(
                                    uid=str(member.get("uid") or member.get("id") or ""),
                                    name=str(member.get("name") or member.get("nickname") or ""),
                                    nickname=str(member.get("name") or member.get("nickname") or ""),
                                    avatar=str(member.get("avatar") or member.get("avatarUrl") or ""),
                                    online=bool(member.get("online") in (1, True)),
                                    payload=dict(member),
                                )
                                for member in members
                            ]
                            for channel_id, members in data.items()
                        },
                        payload=result,
                        response=resp,
                    )
                return data
            except Exception as e:
                logger.error("获取语音频道成员异常: %s", e)
                if as_model:
                    return self._model_error(models.VoiceChannelMembersResult, str(e))
                return {"error": str(e)}
        logger.error("获取语音频道成员失败: 重试次数用尽")
        if as_model:
            return self._model_error(models.VoiceChannelMembersResult, "重试次数用尽")
        return {"error": "重试次数用尽"}

    async def get_voice_channel_for_user(self, user_uid: str, area: Optional[str] = None) -> Optional[str]:
        """获取用户当前所在的语音频道 ID，不在任何语音频道则返回 None。"""
        members = await self.get_voice_channel_members(area=area)
        if isinstance(members, dict) and members.get("error"):
            raise OopzApiError(
                str(members.get("error") or "voice channel members查询失败"),
                response=members,
            )
        if not isinstance(members, dict):
            raise OopzApiError(
                "voice channel members响应格式异常",
                response={"error": "voice channel members响应格式异常"},
            )
        for ch_id, ch_members in members.items():
            if not ch_members:
                continue
            for m in ch_members:
                uid = m.get("uid", m.get("id", "")) if isinstance(m, dict) else str(m)
                if uid == user_uid:
                    return ch_id
        return None
