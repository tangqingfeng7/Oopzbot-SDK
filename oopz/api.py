"""Oopz 平台 API Mixin -- 域/成员/频道/语音/角色/禁言等查询与操作。"""

from __future__ import annotations

import copy
import dataclasses
import json
import logging
import re
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .config import OopzConfig
    from .models import (
        AreaInfo,
        AreaMembersPage,
        AreaBlocksResult,
        ChannelGroupsResult,
        ChannelMessage,
        ChannelSetting,
        DailySpeechResult,
        JoinedAreasResult,
        OperationResult,
        PersonDetail,
        PersonInfo,
        SelfDetail,
        VoiceChannelMembersResult,
    )

from .exceptions import OopzApiError, OopzConnectionError, OopzRateLimitError
from .models import (
    AreaBlock,
    AreaBlocksResult,
    ChannelGroupsResult,
    ChannelMessage,
    ChannelSetting,
    DailySpeechResult,
    JoinedAreasResult,
    OperationResult,
    PersonDetail,
    SelfDetail,
    VoiceChannelMembersResult,
)
from .response import (
    ensure_success_payload,
    raise_api_error,
    require_dict_data,
    require_list_data,
    retry_delay_from_exception,
)

logger = logging.getLogger("oopz.api")


class OopzApiMixin:
    """平台 API 操作集合。

    使用方需在实例上提供 ``_config: OopzConfig``、``session``、``signer``
    以及 ``_get`` / ``_post`` / ``_delete`` / ``_throttle`` 等底层方法。
    """

    _config: OopzConfig

    def _resolve_area(self, area: Optional[str]) -> str:
        value = str(area or self._config.default_area).strip()
        if not value:
            raise ValueError("缺少 area，且未配置 default_area")
        return value

    def _resolve_channel(self, channel: Optional[str]) -> str:
        value = str(channel or self._config.default_channel).strip()
        if not value:
            raise ValueError("缺少 channel，且未配置 default_channel")
        return value

    @staticmethod
    def _require_text(value: object, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} 不能为空")
        return text

    @staticmethod
    def _build_operation_result(
        payload: dict[str, object],
        *,
        message: str,
        response=None,
    ) -> OperationResult:
        return OperationResult(ok=True, message=message, payload=payload, response=response)

    def _get_query_cache_store(self) -> dict[tuple[object, ...], dict[str, object]]:
        store = getattr(self, "_query_cache", None)
        if not isinstance(store, dict):
            store = {}
            self._query_cache = store
        return store

    def _copy_cache_value(self, value: object) -> object:
        if dataclasses.is_dataclass(value):
            if hasattr(value, "response"):
                value = dataclasses.replace(value, response=None)
            return copy.deepcopy(value)
        return copy.deepcopy(value)

    def _get_cached_value(
        self,
        cache_key: tuple[object, ...],
        *,
        max_age: float,
    ) -> object | None:
        store = self._get_query_cache_store()
        cached = store.get(cache_key)
        if not isinstance(cached, dict):
            return None
        ts = cached.get("ts")
        data = cached.get("data")
        if not isinstance(ts, (int, float)):
            return None
        if time.time() - float(ts) > max_age:
            return None
        return self._copy_cache_value(data)

    def _set_cached_value(self, cache_key: tuple[object, ...], data: object) -> None:
        store = self._get_query_cache_store()
        max_entries = int(getattr(self._config, "cache_max_entries", 200))
        if len(store) >= max_entries:
            oldest = min(store, key=lambda key: store[key].get("ts", 0) if isinstance(store[key], dict) else 0)
            store.pop(oldest, None)
        store[cache_key] = {"ts": time.time(), "data": self._copy_cache_value(data)}

    @staticmethod
    def _mark_result_from_cache(result: object, *, stale: bool = False, rate_limited: bool = False) -> object:
        if isinstance(result, dict):
            result["from_cache"] = True
            if stale:
                result["stale"] = True
            if rate_limited:
                result["rateLimited"] = True
            return result
        if hasattr(result, "from_cache"):
            setattr(result, "from_cache", True)
        if stale and hasattr(result, "stale"):
            setattr(result, "stale", True)
        if rate_limited and hasattr(result, "rate_limited"):
            setattr(result, "rate_limited", True)
        return result

    def _load_cached_fallback(
        self,
        cache_key: tuple[object, ...],
        *,
        max_age: float,
        stale: bool = False,
        rate_limited: bool = False,
    ) -> object | None:
        cached = self._get_cached_value(cache_key, max_age=max_age)
        if cached is None:
            return None
        return self._mark_result_from_cache(cached, stale=stale, rate_limited=rate_limited)

    def _call_with_retries(
        self,
        action: str,
        callback,
        *,
        max_attempts: int = 3,
    ):
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return callback()
            except (OopzRateLimitError, OopzConnectionError) as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                wait_seconds = retry_delay_from_exception(exc, attempt)
                logger.warning("%s，%.1fs 后重试 (%d/%d): %s", action, wait_seconds, attempt, max_attempts - 1, exc)
                time.sleep(wait_seconds)
        if last_error is not None:
            raise last_error
        raise OopzApiError(f"{action}: 未知错误")

    def _build_channel_setting_result(self, payload: dict[str, object], *, response=None) -> ChannelSetting:
        accessible_members = [
            str(item) for item in payload.get("accessibleMembers", []) if str(item).strip()
        ] if isinstance(payload.get("accessibleMembers"), list) else []
        return ChannelSetting(
            channel=str(payload.get("channel") or payload.get("id") or ""),
            area=str(payload.get("area") or ""),
            name=str(payload.get("name") or ""),
            text_gap_second=int(payload.get("textGapSecond", 0) or 0),
            voice_quality=str(payload.get("voiceQuality") or "64k"),
            voice_delay=str(payload.get("voiceDelay") or "LOW"),
            max_member=int(payload.get("maxMember", 30000) or 30000),
            voice_control_enabled=bool(payload.get("voiceControlEnabled")),
            text_control_enabled=bool(payload.get("textControlEnabled")),
            text_roles=list(payload.get("textRoles") or []),
            voice_roles=list(payload.get("voiceRoles") or []),
            access_control_enabled=bool(payload.get("accessControlEnabled")),
            accessible=list(payload.get("accessible") or []),
            accessible_members=accessible_members,
            secret=bool(payload.get("secret")),
            has_password=bool(payload.get("hasPassword")),
            password=str(payload.get("password") or ""),
            payload=dict(payload),
            response=response,
        )

    def _build_person_detail_result(self, payload: dict[str, object], *, response=None) -> PersonDetail:
        return PersonDetail(
            uid=str(payload.get("uid") or payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("nickname") or ""),
            avatar=str(payload.get("avatar") or payload.get("avatarUrl") or ""),
            common_id=str(payload.get("commonId") or ""),
            bio=str(payload.get("bio") or payload.get("signature") or ""),
            payload=dict(payload),
            response=response,
        )

    def _build_self_detail_result(
        self,
        payload: dict[str, object],
        *,
        response=None,
        from_cache: bool = False,
    ) -> SelfDetail:
        return SelfDetail(
            uid=str(payload.get("uid") or payload.get("id") or self._config.person_uid),
            name=str(payload.get("name") or payload.get("nickname") or ""),
            avatar=str(payload.get("avatar") or payload.get("avatarUrl") or ""),
            mobile=str(payload.get("mobile") or ""),
            from_cache=from_cache,
            payload=dict(payload),
            response=response,
        )

    @staticmethod
    def _build_voice_channel_members_result(
        payload: dict[str, object],
        *,
        response=None,
    ) -> VoiceChannelMembersResult:
        raw_members = payload.get("channelMembers", {})
        channels: dict[str, list[dict[str, object]]] = {}
        if isinstance(raw_members, dict):
            for channel_id, members in raw_members.items():
                normalized: list[dict[str, object]] = []
                if isinstance(members, list):
                    for member in members:
                        if isinstance(member, dict):
                            normalized.append(member)
                channels[str(channel_id)] = normalized
        return VoiceChannelMembersResult(channels=channels, payload=dict(payload), response=response)

    @staticmethod
    def _build_daily_speech_result(payload: dict[str, object], *, response=None) -> DailySpeechResult:
        return DailySpeechResult(
            words=str(payload.get("words") or payload.get("content") or ""),
            author=str(payload.get("author") or payload.get("from") or ""),
            source=str(payload.get("source") or payload.get("book") or ""),
            payload=dict(payload),
            response=response,
        )

    @staticmethod
    def _build_channel_messages_result(
        payload: dict[str, object],
        *,
        response=None,
    ) -> list[ChannelMessage]:
        raw_list = payload.get("messages", [])
        if not isinstance(raw_list, list):
            raise OopzApiError("获取频道消息失败: 响应格式异常", status_code=getattr(response, "status_code", None), response=payload)
        messages: list[ChannelMessage] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            attachments = item.get("attachments", [])
            messages.append(
                ChannelMessage(
                    message_id=str(item.get("messageId") or item.get("id") or ""),
                    area=str(item.get("area") or ""),
                    channel=str(item.get("channel") or ""),
                    person=str(item.get("person") or ""),
                    content=str(item.get("content") or item.get("text") or ""),
                    timestamp=str(item.get("timestamp") or ""),
                    attachments=[entry for entry in attachments if isinstance(entry, dict)] if isinstance(attachments, list) else [],
                    payload=dict(item),
                    response=response,
                )
            )
        return messages

    @staticmethod
    def _build_area_blocks_result(payload: object, *, response=None) -> AreaBlocksResult:
        blocks: list[AreaBlock] = []
        if isinstance(payload, list):
            raw_blocks = payload
        elif isinstance(payload, dict):
            raw_blocks = payload.get("blocks", payload.get("list", []))
        else:
            raw_blocks = []
        if isinstance(raw_blocks, list):
            for item in raw_blocks:
                if not isinstance(item, dict):
                    continue
                blocks.append(
                    AreaBlock(
                        uid=str(item.get("uid") or item.get("target") or item.get("id") or ""),
                        name=str(item.get("name") or item.get("nickname") or ""),
                        reason=str(item.get("reason") or item.get("message") or ""),
                        payload=dict(item),
                    )
                )
        normalized_payload = payload if isinstance(payload, dict) else {"blocks": [block.payload for block in blocks]}
        return AreaBlocksResult(blocks=blocks, payload=dict(normalized_payload), response=response)

    # ---- 域成员查询 ----

    def _get_area_members_cache_store(self) -> dict:
        store = getattr(self, "_area_members_cache", None)
        if not isinstance(store, dict):
            store = {}
            self._area_members_cache = store
        return store

    def _get_cached_area_members(
        self,
        cache_key: tuple[str, int, int],
        *,
        max_age: float,
    ) -> Optional[dict]:
        store = self._get_area_members_cache_store()
        cached = store.get(cache_key)
        if not isinstance(cached, dict):
            return None
        ts = cached.get("ts")
        data = cached.get("data")
        if not isinstance(ts, (int, float)) or not isinstance(data, dict):
            return None
        if time.time() - float(ts) > max_age:
            return None
        return copy.deepcopy(data)

    def _set_cached_area_members(self, cache_key: tuple[str, int, int], data: dict) -> None:
        store = self._get_area_members_cache_store()
        max_entries = int(getattr(self._config, "cache_max_entries", 200))
        if len(store) >= max_entries:
            oldest = min(store, key=lambda k: store[k].get("ts", 0) if isinstance(store[k], dict) else 0)
            store.pop(oldest, None)
        store[cache_key] = {"ts": time.time(), "data": copy.deepcopy(data)}

    def get_area_members(self, area: Optional[str] = None, offset_start: int = 0, offset_end: int = 49, quiet: bool = False) -> "AreaMembersPage":
        """获取域内成员列表及在线状态。"""
        area = self._resolve_area(area)
        url_path = "/area/v3/members"
        params = {"area": area, "offsetStart": str(offset_start), "offsetEnd": str(offset_end)}
        max_attempts = 3
        cache_key = (str(area), int(offset_start), int(offset_end))
        cache_ttl = float(getattr(self._config, "area_members_cache_ttl", 2.0))
        stale_ttl = float(getattr(self._config, "area_members_stale_ttl", 300.0))

        if quiet:
            cached = self._get_cached_area_members(cache_key, max_age=cache_ttl)
            if cached is not None:
                cached["from_cache"] = True
                return cached

        try:
            resp = None
            for attempt in range(1, max_attempts + 1):
                resp = self._get(url_path, params=params)
                if resp.status_code != 429:
                    break

                retry_after = 0
                try:
                    retry_after = int(resp.headers.get("Retry-After", "0") or "0")
                except Exception:
                    retry_after = 0
                wait_seconds = retry_after if retry_after > 0 else min(attempt, 3)

                if attempt >= max_attempts:
                    stale_cached = self._get_cached_area_members(cache_key, max_age=stale_ttl)
                    if stale_cached is not None:
                        stale_cached["stale"] = True
                        stale_cached["rateLimited"] = True
                        stale_cached["from_cache"] = True
                        logger.warning(
                            "获取域成员被限流，返回 %.1fs 内缓存数据 (area=%s, offset=%s-%s)",
                            stale_ttl, area, offset_start, offset_end,
                        )
                        return stale_cached
                    logger.warning(
                        "获取域成员被限流: HTTP 429 (area=%s, offset=%s-%s, 已重试%d次)",
                        area, offset_start, offset_end, max_attempts - 1,
                    )
                    raise_api_error(resp, "获取域成员失败")

                logger.warning(
                    "获取域成员被限流: HTTP 429 (area=%s, offset=%s-%s), %.1fs 后重试 (%d/%d)",
                    area, offset_start, offset_end, float(wait_seconds), attempt, max_attempts - 1,
                )
                time.sleep(wait_seconds)

            if resp is None:
                raise OopzApiError("获取域成员失败: 未获得响应")

            result = ensure_success_payload(resp, "获取域成员失败")

            data = require_dict_data(result, "获取域成员失败")
            members = data.get("members", [])
            online = sum(1 for m in members if m.get("online") == 1)
            fetched = len(members)
            api_total = data.get("totalCount") or data.get("userCount")
            try:
                total = int(api_total) if api_total is not None else fetched
            except Exception:
                total = fetched

            role_count = data.get("roleCount", [])
            online_from_api = sum(
                rc.get("count", 0) for rc in role_count if rc.get("role", 0) != -1
            ) if role_count else online

            if not quiet:
                logger.info("获取域成员成功: 本页 %d 人, 在线 %d 人, 域总人数 %d", fetched, online_from_api, total)
            data["onlineCount"] = online_from_api or online
            data["totalCount"] = total
            data["userCount"] = total
            data["fetchedCount"] = fetched
            data["stale"] = False
            data["rateLimited"] = False
            data["from_cache"] = False
            self._set_cached_area_members(cache_key, data)
            return data
        except Exception as e:
            logger.error("获取域成员异常: %s", e)
            stale = self._get_cached_area_members(cache_key, max_age=stale_ttl)
            if stale is not None:
                stale["stale"] = True
                stale["from_cache"] = True
                return stale
            raise

    # ---- 频道列表 ----

    def get_area_channels(self, area: Optional[str] = None, quiet: bool = False) -> "ChannelGroupsResult":
        """获取域内完整频道列表（含分组）。"""
        area = self._resolve_area(area)
        url_path = "/client/v1/area/v1/detail/v1/channels"
        params = {"area": area}

        cache_key = ("area_channels", area)
        cache_ttl = float(getattr(self._config, "query_cache_ttl", 15.0))
        stale_ttl = float(getattr(self._config, "query_cache_stale_ttl", 300.0))
        if quiet:
            cached = self._load_cached_fallback(cache_key, max_age=cache_ttl)
            if cached is not None:
                return cached

        def _load_channels() -> tuple[dict[str, object], object]:
            resp_local = self._get(url_path, params=params)
            return ensure_success_payload(resp_local, "获取频道列表失败"), resp_local

        try:
            result, resp = self._call_with_retries("获取频道列表失败", _load_channels)
        except (OopzRateLimitError, OopzConnectionError):
            cached = self._load_cached_fallback(cache_key, max_age=stale_ttl, stale=True)
            if cached is not None:
                return cached
            raise
        groups = require_list_data(result, "获取频道列表失败")
        typed_groups = [group for group in groups if isinstance(group, dict)]
        payload = ChannelGroupsResult(groups=typed_groups, from_cache=False, payload=result, response=resp)
        self._set_cached_value(cache_key, payload)
        if not quiet:
            total = sum(len(g.get("channels") or []) for g in payload.groups if isinstance(g, dict))
            logger.info("获取频道列表: %d 个频道, %d 个分组", total, len(payload.groups))
        return payload

    def get_channel_setting_info(self, channel: str) -> "ChannelSetting":
        """获取频道设置详情（名称、访问权限等）。"""
        channel = self._require_text(channel, "channel")

        url_path = "/area/v3/channel/setting/info"
        params = {"channel": channel}
        def _load_setting() -> tuple[dict[str, object], object]:
            resp_local = self._get(url_path, params=params)
            return ensure_success_payload(resp_local, "获取频道设置失败"), resp_local

        result, resp = self._call_with_retries("获取频道设置失败", _load_setting)
        data = require_dict_data(result, "获取频道设置失败")
        return self._build_channel_setting_result(data, response=resp)

    def _pick_channel_group(
        self,
        area: str,
        preferred_channel: Optional[str] = None,
        preferred_group_name: Optional[str] = None,
    ) -> Optional[str]:
        groups_result = self.get_area_channels(area=area, quiet=True)
        groups = groups_result.groups
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

    def create_channel(
        self,
        area: Optional[str] = None,
        name: str = "",
        channel_type: str = "text",
        group_id: str = "",
    ) -> OperationResult:
        """创建频道。"""
        area = self._resolve_area(area)
        name = self._require_text(name, "name")

        if not group_id:
            group_id = self._pick_channel_group(area) or ""
            if not group_id:
                raise OopzApiError("创建频道失败: 未找到可用频道分组")

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

        resp = self._post("/client/v1/area/v1/channel/v1/create", body)
        result = ensure_success_payload(resp, "创建频道失败")
        data = require_dict_data(result, "创建频道失败")
        channel_id = self._extract_channel_id(data) or self._extract_channel_id(result)
        return self._build_operation_result(
            {
                "channel": channel_id or "",
                "name": name,
                **result,
            },
            message="频道已创建",
            response=resp,
        )

    def update_channel(
        self,
        area: Optional[str] = None,
        channel_id: str = "",
        overrides: Optional[dict] = None,
        *,
        name: str = "",
    ) -> OperationResult:
        """修改频道设置。"""
        area = self._resolve_area(area)
        channel_id = self._require_text(channel_id, "channel_id")

        setting = self.get_channel_setting_info(channel_id)

        _BOOL_FIELDS = ("secret", "hasPassword", "voiceControlEnabled",
                        "textControlEnabled", "accessControlEnabled")
        _INT_FIELDS = ("textGapSecond", "maxMember")
        _STR_FIELDS = ("name", "voiceQuality", "voiceDelay", "password")

        edit_body = setting.to_edit_body(area=area)

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

        resp = self._post("/area/v3/channel/setting/edit", edit_body)
        result = ensure_success_payload(resp, "更新频道失败")
        return self._build_operation_result(result, message="频道已更新", response=resp)

    def create_restricted_text_channel(
        self,
        target_uid: str,
        area: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        name: Optional[str] = None,
    ) -> OperationResult:
        """创建仅指定成员可见的文字频道。"""
        area = self._resolve_area(area)
        target_uid = self._require_text(target_uid, "target_uid")

        group_id = self._pick_channel_group(area, preferred_channel=preferred_channel)
        if not group_id:
            raise OopzApiError("创建受限频道失败: 未找到可用频道分组")

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

        resp = self._post(url_path, body)
        result = ensure_success_payload(resp, "创建受限频道失败")
        data = require_dict_data(result, "创建受限频道失败")
        channel_id = self._extract_channel_id(data) or self._extract_channel_id(result)
        if not channel_id:
            raise OopzApiError("创建受限频道失败: 未能提取频道 ID", status_code=resp.status_code, response=result)

        setting = self.get_channel_setting_info(channel_id)
        edit_body = setting.to_edit_body(area=area)
        edit_body.update({
            "name": setting.name or channel_name,
            "accessControlEnabled": True,
            "accessible": [],
            "accessibleMembers": [
                uid for uid in dict.fromkeys([
                    str(target_uid),
                    str(self._config.person_uid or ""),
                ]) if uid
            ],
            "secret": setting.secret,
            "hasPassword": setting.has_password,
            "password": setting.password,
        })

        edit_path = "/area/v3/channel/setting/edit"
        try:
            edit_resp = self._post(edit_path, edit_body)
            edit_result = ensure_success_payload(edit_resp, "设置受限频道权限失败")
        except Exception:
            self.delete_channel(channel_id, area=area)
            raise

        logger.info("创建受限频道成功: channel=%s target=%s", channel_id[:24], target_uid[:12])
        return self._build_operation_result(
            {
                "channel": channel_id,
                "group": group_id,
                "name": edit_body["name"],
                **edit_result,
            },
            message="受限频道已创建",
            response=edit_resp,
        )

    def delete_channel(self, channel: str, area: Optional[str] = None) -> OperationResult:
        """删除频道。"""
        area = self._resolve_area(area)
        channel = self._require_text(channel, "channel")

        url_path = f"/client/v1/area/v1/channel/v1/delete?channel={channel}&area={area}"
        resp = self._delete(url_path)
        result = ensure_success_payload(resp, "删除频道失败")
        return self._build_operation_result(result, message=str(result.get("message") or "已删除频道"), response=resp)

    # ---- 已加入的域列表 ----

    def get_joined_areas(self, quiet: bool = False) -> "JoinedAreasResult":
        """获取当前用户已加入（订阅）的域列表。"""
        url_path = "/userSubscribeArea/v1/list"
        cache_key = ("joined_areas", self._config.person_uid)
        cache_ttl = float(getattr(self._config, "query_cache_ttl", 15.0))
        stale_ttl = float(getattr(self._config, "query_cache_stale_ttl", 300.0))
        if quiet:
            cached = self._load_cached_fallback(cache_key, max_age=cache_ttl)
            if cached is not None:
                return cached
        

        def _load_areas() -> tuple[dict[str, object], object]:
            resp_local = self._get(url_path)
            return ensure_success_payload(resp_local, "获取已加入域列表失败"), resp_local

        try:
            result, resp = self._call_with_retries("获取已加入域列表失败", _load_areas)
        except (OopzRateLimitError, OopzConnectionError):
            cached = self._load_cached_fallback(cache_key, max_age=stale_ttl, stale=True)
            if cached is not None:
                return cached
            raise

        areas = require_list_data(result, "获取已加入域列表失败")
        typed_areas = [area for area in areas if isinstance(area, dict)]
        payload = JoinedAreasResult(areas=typed_areas, from_cache=False, payload=result, response=resp)
        self._set_cached_value(cache_key, payload)
        if not quiet:
            logger.info("获取已加入域列表: %d 个域", len(payload.areas))
            for a in payload.areas:
                if isinstance(a, dict):
                    logger.info("  域: %s (ID=%s, code=%s)", a.get("name"), a.get("id"), a.get("code"))
        return payload

    # ---- 域详情 ----

    def get_area_info(self, area: Optional[str] = None) -> "AreaInfo":
        """获取域详细信息（含角色列表、主页频道等）。"""
        area = self._resolve_area(area)
        url_path = "/area/v3/info"
        params = {"area": area}
        resp = self._get(url_path, params=params)
        result = ensure_success_payload(resp, "获取域详情失败")
        return require_dict_data(result, "获取域详情失败")

    # ---- 批量获取用户信息 ----

    def get_person_infos_batch(self, uids: list[str]) -> dict[str, dict]:
        """批量获取用户基本信息。"""
        if not uids:
            return {}
        url_path = "/client/v1/person/v1/personInfos"
        result_map: dict[str, dict] = {}
        batch_size = 30
        for i in range(0, len(uids), batch_size):
            batch = uids[i : i + batch_size]
            body = {"persons": batch, "commonIds": []}
            resp = self._post(url_path, body)
            data = ensure_success_payload(resp, "批量获取用户信息失败")
            person_list = require_list_data(data, "批量获取用户信息失败")
            for person in person_list:
                if not isinstance(person, dict):
                    continue
                uid = str(person.get("uid") or "")
                if uid:
                    result_map[uid] = person
        return result_map

    # ---- 个人详细信息 ----

    def get_person_detail(self, uid: Optional[str] = None) -> PersonDetail:
        """获取用户信息（可查询任意用户）。"""
        uid = str(uid or self._config.person_uid).strip()
        url_path = "/client/v1/person/v1/personInfos"
        body = {"persons": [uid], "commonIds": []}

        def _load_person() -> tuple[dict[str, object], object]:
            resp_local = self._post(url_path, body)
            return ensure_success_payload(resp_local, "获取个人信息失败"), resp_local

        result, resp = self._call_with_retries("获取个人信息失败", _load_person)
        data_list = require_list_data(result, "获取个人信息失败")
        if not data_list or not isinstance(data_list[0], dict):
            raise OopzApiError("获取个人信息失败: 未找到该用户", status_code=resp.status_code, response=result)

        person = data_list[0]
        logger.info("获取个人信息成功: %s", person.get("name", "未知"))
        return self._build_person_detail_result(person, response=resp)

    def get_person_detail_full(self, uid: str) -> PersonDetail:
        """获取他人完整详细资料（含 VIP、IP 属地等）。"""
        url_path = "/client/v1/person/v1/personDetail"
        params = {"uid": self._require_text(uid, "uid")}
        def _load_person_full() -> tuple[dict[str, object], object]:
            resp_local = self._get(url_path, params=params)
            return ensure_success_payload(resp_local, "获取他人详细资料失败"), resp_local

        result, resp = self._call_with_retries("获取他人详细资料失败", _load_person_full)
        data = require_dict_data(result, "获取他人详细资料失败")
        return self._build_person_detail_result(data, response=resp)

    def get_self_detail(self) -> SelfDetail:
        """获取当前登录用户的完整详细资料。"""
        uid = self._config.person_uid
        url_path = "/client/v1/person/v2/selfDetail"
        params = {"uid": uid}
        cache_key = ("self_detail", uid)
        stale_ttl = float(getattr(self._config, "query_cache_stale_ttl", 300.0))

        def _load_self_detail() -> tuple[dict[str, object], object]:
            resp_local = self._get(url_path, params=params)
            return ensure_success_payload(resp_local, "获取自身详细资料失败"), resp_local

        try:
            result, resp = self._call_with_retries("获取自身详细资料失败", _load_self_detail)
        except (OopzRateLimitError, OopzConnectionError):
            cached = self._load_cached_fallback(cache_key, max_age=stale_ttl, stale=True)
            if cached is not None:
                return cached
            raise

        data = require_dict_data(result, "获取自身详细资料失败")
        detail = self._build_self_detail_result(data, response=resp, from_cache=False)
        self._set_cached_value(cache_key, detail)
        return detail

    def get_level_info(self) -> dict:
        """获取当前用户等级、积分信息。"""
        url_path = "/user_points/v1/level_info"
        resp = self._get(url_path)
        result = ensure_success_payload(resp, "获取等级信息失败")
        return require_dict_data(result, "获取等级信息失败")

    # ---- 用户在域内的角色 / 禁言状态 ----

    def get_user_area_detail(self, target: str, area: Optional[str] = None) -> dict:
        """获取指定用户在域内的角色列表和禁言/禁麦状态。"""
        area = self._resolve_area(area)
        url_path = "/area/v3/userDetail"
        params = {"area": area, "target": self._require_text(target, "target")}
        resp = self._get(url_path, params=params)
        result = ensure_success_payload(resp, "获取用户域内详情失败")
        return require_dict_data(result, "获取用户域内详情失败")

    # ---- 可分配的角色列表 ----

    def get_assignable_roles(self, target: str, area: Optional[str] = None) -> list[dict]:
        """获取当前用户可以分配给目标用户的角色列表。"""
        area = self._resolve_area(area)
        url_path = "/area/v3/role/canGiveList"
        params = {"area": area, "target": self._require_text(target, "target")}
        resp = self._get(url_path, params=params)
        result = ensure_success_payload(resp, "获取可分配角色失败")
        data = require_dict_data(result, "获取可分配角色失败")
        roles = data.get("roles", [])
        if not isinstance(roles, list):
            raise OopzApiError("获取可分配角色失败: 响应格式异常", status_code=resp.status_code, response=result)
        return [role for role in roles if isinstance(role, dict)]

    def edit_user_role(
        self,
        target_uid: str,
        role_id: int,
        add: bool,
        area: Optional[str] = None,
    ) -> OperationResult:
        """给目标用户添加或取消指定身份组。"""
        area = self._resolve_area(area)
        detail = self.get_user_area_detail(target_uid, area=area)
        current_list = detail.get("list") or []
        current_ids = [int(r["roleID"]) for r in current_list if r.get("roleID") is not None]
        role_id = int(role_id)
        if add:
            if role_id not in current_ids:
                current_ids.append(role_id)
        else:
            current_ids = [x for x in current_ids if x != role_id]
        url_path = "/area/v3/role/editUserRole"
        body = {"area": area, "target": target_uid, "targetRoleIDs": current_ids}
        resp = self._post(url_path, body)
        result = ensure_success_payload(resp, "编辑用户角色失败")
        return self._build_operation_result(
            result,
            message=str(result.get("message") or ("已给身份组" if add else "已取消身份组")),
            response=resp,
        )

    # ---- 搜索域成员 ----

    def search_area_members(self, area: Optional[str] = None, keyword: str = "") -> list["PersonInfo"]:
        """搜索域内成员。"""
        area = self._resolve_area(area)
        url_path = "/area/v3/search/areaSettingMembers"
        body = {"area": area, "name": keyword, "offset": 0, "limit": 50}
        resp = self._post(url_path, body)
        result = ensure_success_payload(resp, "搜索域成员失败")
        data = require_dict_data(result, "搜索域成员失败")
        members = data.get("members", [])
        if not isinstance(members, list):
            raise OopzApiError("搜索域成员失败: 响应格式异常", status_code=resp.status_code, response=result)
        return [member for member in members if isinstance(member, dict)]

    # ---- 各语音频道在线成员 ----

    _voice_ids_cache: dict = {}

    def _get_voice_channel_ids(self, area: str) -> list[str]:
        cached = self._voice_ids_cache.get(area)
        if cached and time.time() - cached["ts"] < 300:
            return cached["ids"]
        groups = self.get_area_channels(area, quiet=True).groups
        ids = []
        for g in groups:
            for ch in g.get("channels") or []:
                if str(ch.get("type", "")).upper() in ("VOICE", "AUDIO"):
                    ids.append(ch["id"])
        self._voice_ids_cache[area] = {"ids": ids, "ts": time.time()}
        return ids

    def get_voice_channel_members(self, area: Optional[str] = None) -> VoiceChannelMembersResult:
        """获取域内各语音频道的在线成员列表。"""
        area = self._resolve_area(area)
        voice_ids = self._get_voice_channel_ids(area)
        if not voice_ids:
            return VoiceChannelMembersResult(channels={})

        url_path = "/area/v3/channel/membersByChannels"
        body = {"area": area, "channels": voice_ids}
        def _load_voice_members() -> tuple[dict[str, object], object]:
            resp_local = self._post(url_path, body)
            return ensure_success_payload(resp_local, "获取语音频道成员失败"), resp_local

        result, resp = self._call_with_retries("获取语音频道成员失败", _load_voice_members)
        data = require_dict_data(result, "获取语音频道成员失败")
        return self._build_voice_channel_members_result(data, response=resp)

    def get_voice_channel_for_user(self, user_uid: str, area: Optional[str] = None) -> Optional[str]:
        """获取用户当前所在的语音频道 ID，不在任何语音频道则返回 None。"""
        members = self.get_voice_channel_members(area=area)
        for ch_id, ch_members in members.channels.items():
            if not ch_members:
                continue
            for m in ch_members:
                uid = m.get("uid", m.get("id", "")) if isinstance(m, dict) else str(m)
                if uid == user_uid:
                    return ch_id
        return None

    # ---- 进入域 / 进入频道 ----

    def enter_area(self, area: Optional[str] = None, recover: bool = False) -> dict:
        """进入指定域。"""
        area = self._resolve_area(area)
        url_path = f"/client/v1/area/v1/enter?area={area}&recover={str(recover).lower()}"
        body = {"area": area, "recover": recover}
        resp = self._post(url_path, body)
        result = ensure_success_payload(resp, "进入域失败")
        return require_dict_data(result, "进入域失败")

    def enter_channel(self, channel: Optional[str] = None, area: Optional[str] = None,
                      channel_type: str = "TEXT", from_channel: str = "",
                      from_area: str = "", pid: str = "") -> dict:
        """进入指定频道。"""
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
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

        resp = self._post(url_path, body)
        result = ensure_success_payload(resp, "进入频道失败")
        return require_dict_data(result, "进入频道失败")

    def leave_voice_channel(self, channel: str, area: Optional[str] = None,
                            target: Optional[str] = None) -> OperationResult:
        """退出语音频道。"""
        area = self._resolve_area(area)
        channel = self._require_text(channel, "channel")
        target = str(target or self._config.person_uid).strip()
        url_path = "/client/v1/area/v1/member/v1/removeFromChannel"
        query = f"?area={area}&channel={channel}&target={target}"
        full_path = url_path + query

        resp = self._delete(full_path)
        result = ensure_success_payload(resp, "退出语音频道失败")
        logger.info("已退出语音频道")
        return self._build_operation_result(result, message="已退出语音频道", response=resp)

    # ---- 每日一句 ----

    def get_daily_speech(self) -> DailySpeechResult:
        """获取开屏每日一句（名言）。"""
        url_path = "/general/v1/speech"

        def _load_speech() -> tuple[dict[str, object], object]:
            resp_local = self._get(url_path)
            return ensure_success_payload(resp_local, "获取每日一句失败"), resp_local

        result, resp = self._call_with_retries("获取每日一句失败", _load_speech)
        data = require_dict_data(result, "获取每日一句失败")
        speech = self._build_daily_speech_result(data, response=resp)
        logger.info("每日一句: %s...", speech.words[:30])
        return speech

    # ---- 获取频道消息 ----

    def get_channel_messages(
        self,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        size: int = 50,
    ) -> list[ChannelMessage]:
        """获取频道最近的消息列表。"""
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        url_path = "/im/session/v2/messageBefore"
        params = {"area": area, "channel": channel, "size": str(size)}

        def _load_messages() -> tuple[dict[str, object], object]:
            resp_local = self._get(url_path, params=params)
            return ensure_success_payload(resp_local, "获取频道消息失败"), resp_local

        result, resp = self._call_with_retries("获取频道消息失败", _load_messages)
        data = require_dict_data(result, "获取频道消息失败")
        messages = self._build_channel_messages_result(data, response=resp)
        logger.info("获取频道消息: %d 条", len(messages))
        return messages

    def find_message_timestamp(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Optional[str]:
        """从频道最近消息中查找指定 messageId 的 timestamp。"""
        messages = self.get_channel_messages(area=area, channel=channel)
        for msg in messages:
            if msg.message_id == message_id:
                return msg.timestamp
        return None

    # ---- 禁言 / 禁麦 ----

    _TEXT_INTERVALS = {1: "60秒", 2: "5分钟", 3: "1小时", 4: "1天", 5: "3天", 6: "7天"}
    _VOICE_INTERVALS = {7: "60秒", 8: "5分钟", 9: "1小时", 10: "1天", 11: "3天", 12: "7天"}

    @staticmethod
    def _minutes_to_interval_id(minutes: int, voice: bool = False) -> str:
        thresholds = [(1, 7), (5, 8), (60, 9), (1440, 10), (4320, 11), (10080, 12)] if voice \
            else [(1, 1), (5, 2), (60, 3), (1440, 4), (4320, 5), (10080, 6)]
        for limit, iid in thresholds:
            if minutes <= limit:
                return str(iid)
        return str(thresholds[-1][1])

    def mute_user(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None, duration: int = 10) -> OperationResult:
        """禁言用户。"""
        area = self._resolve_area(area)
        interval_id = self._minutes_to_interval_id(duration, voice=False)
        url_path = "/client/v1/area/v1/member/v1/disableText"
        query = f"?area={area}&target={uid}&intervalId={interval_id}"
        body = {"area": area, "target": uid, "intervalId": interval_id}
        return self._manage_patch("禁言", url_path, query, body)

    def unmute_user(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None) -> OperationResult:
        """解除禁言。"""
        area = self._resolve_area(area)
        url_path = "/client/v1/area/v1/member/v1/recoverText"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return self._manage_patch("解除禁言", url_path, query, body)

    def mute_mic(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None, duration: int = 10) -> OperationResult:
        """禁麦用户。"""
        area = self._resolve_area(area)
        interval_id = self._minutes_to_interval_id(duration, voice=True)
        url_path = "/client/v1/area/v1/member/v1/disableVoice"
        query = f"?area={area}&target={uid}&intervalId={interval_id}"
        body = {"area": area, "target": uid, "intervalId": interval_id}
        return self._manage_patch("禁麦", url_path, query, body)

    def unmute_mic(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None) -> OperationResult:
        """解除禁麦。"""
        area = self._resolve_area(area)
        url_path = "/client/v1/area/v1/member/v1/recoverVoice"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return self._manage_patch("解除禁麦", url_path, query, body)

    def remove_from_area(self, uid: str, area: Optional[str] = None) -> OperationResult:
        """将用户移出当前域（踢出域）。"""
        area = self._resolve_area(area)
        url_path = f"/area/v3/remove?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        resp = self._post(url_path, body)
        result = ensure_success_payload(resp, "移出域失败")
        logger.info("移出域成功")
        return self._build_operation_result(result, message="已移出域", response=resp)

    def block_user_in_area(self, uid: str, area: Optional[str] = None) -> OperationResult:
        """封禁用户。"""
        area = self._resolve_area(area)
        url_path = f"/client/v1/area/v1/block?area={area}&target={uid}"
        resp = self._delete(url_path)
        result = ensure_success_payload(resp, "封禁失败")
        msg = str(result.get("message") or "已封禁")
        logger.info("封禁成功: %s", msg)
        return self._build_operation_result(result, message=msg, response=resp)

    def get_area_blocks(self, area: Optional[str] = None, name: str = "") -> AreaBlocksResult:
        """获取域内封禁列表。"""
        area = self._resolve_area(area)
        url_path = "/client/v1/area/v1/areaSettings/v1/blocks"
        params = {"area": area, "name": name}

        def _load_blocks() -> tuple[dict[str, object], object]:
            resp_local = self._get(url_path, params=params)
            return ensure_success_payload(resp_local, "获取域封禁列表失败"), resp_local

        result, resp = self._call_with_retries("获取域封禁列表失败", _load_blocks)
        data = result.get("data", {})
        blocks = self._build_area_blocks_result(data, response=resp)
        logger.info("获取域封禁列表: %d 人", len(blocks.blocks))
        return blocks

    def unblock_user_in_area(self, uid: str, area: Optional[str] = None) -> OperationResult:
        """解除域内封禁。"""
        area = self._resolve_area(area)
        url_path = "/client/v1/area/v1/unblock"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return self._manage_patch("解除域内封禁", url_path, query, body)

    def _manage_patch(self, action: str, url_path: str, query: str, body: dict) -> OperationResult:
        """通用 PATCH 管理操作（禁言/禁麦等）。"""
        full_path = url_path + query
        resp = self._patch(full_path, body)
        result = ensure_success_payload(resp, f"{action}失败")
        msg = str(result.get("message") or f"{action}成功")
        logger.info("%s成功: %s", action, msg)
        return self._build_operation_result(result, message=msg, response=resp)

    # ---- 撤回消息 ----

    def recall_message(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        timestamp: Optional[str] = None,
        target: str = "",
    ) -> OperationResult:
        """撤回指定消息（需要管理员权限）。"""
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        timestamp = timestamp or self.signer.timestamp_us()
        message_id = self._require_text(message_id, "message_id")

        url_path = "/im/session/v1/recallGim"
        query = (
            f"?area={area}&channel={channel}"
            f"&messageId={message_id}&timestamp={timestamp}&target={target}"
        )
        full_path = url_path + query

        body = {
            "area": area,
            "channel": channel,
            "messageId": message_id,
            "timestamp": timestamp,
            "target": target,
        }

        resp = self._post(full_path, body)
        result = ensure_success_payload(resp, "撤回消息失败")
        logger.info("撤回消息成功: %s", message_id)
        return self._build_operation_result(result, message="撤回成功", response=resp)

    # ---- 名称填充（仅在传入回调时可用） ----

    def populate_names(self, *, set_area=None, set_channel=None) -> OperationResult:
        """从 API 获取已加入域列表及各域频道列表，通过回调填充名称。

        Args:
            set_area: 可选回调 (area_id, area_name) -> None
            set_channel: 可选回调 (channel_id, channel_name) -> None

        Returns:
            {"areas_named": int, "channels_named": int}
        """
        areas_count = 0
        channels_count = 0
        areas = self.get_joined_areas().areas
        for a in areas:
            area_id = a.get("id", "")
            area_name = a.get("name", "")
            if area_id and area_name and set_area:
                set_area(area_id, area_name)
                areas_count += 1

            groups = self.get_area_channels(area_id).groups
            for group in groups:
                for ch in (group.get("channels") or []):
                    ch_id = ch.get("id", "")
                    ch_name = ch.get("name", "")
                    if ch_id and ch_name and set_channel:
                        set_channel(ch_id, ch_name)
                        channels_count += 1

        logger.info("名称自动填充完成: %d 个域, %d 个频道", areas_count, channels_count)
        return self._build_operation_result(
            {"areas_named": areas_count, "channels_named": channels_count},
            message="名称填充完成",
        )
