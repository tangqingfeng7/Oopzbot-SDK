from __future__ import annotations

import copy
import json
import logging
import re
import time
from typing import Optional

from oopz_sdk.models import Channel

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.channel")


class Channel(BaseService):
    """Channel-related platform capabilities."""

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

    @staticmethod
    def _to_channel_model(payload: dict, area: str = "") -> Channel:
        return Channel(
            id=str(payload.get("id") or payload.get("channel") or ""),
            name=str(payload.get("name") or ""),
            type=str(payload.get("type") or ""),
            area=str(area or payload.get("area") or ""),
        )

    def get_area_channels(
        self,
        area: Optional[str] = None,
        quiet: bool = False,
        *,
        as_model: bool = False,
    ) -> list:
        """获取域内完整频道列表（含分组）。"""
        area = area or self._config.default_area
        url_path = "/client/v1/area/v1/detail/v1/channels"
        params = {"area": area}

        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                logger.error("获取频道列表失败: HTTP %d", resp.status_code)
                return []
            result = resp.json()
            if not result.get("status"):
                logger.error("获取频道列表失败: %s", result.get("message") or result.get("error"))
                return []
            groups = result.get("data") or []
            if not quiet:
                total = sum(len(g.get("channels") or []) for g in groups)
                logger.info("获取频道列表: %d 个频道, %d 个分组", total, len(groups))
            if as_model:
                channels: list[Channel] = []
                for group in groups:
                    for ch in (group.get("channels") or []):
                        if isinstance(ch, dict):
                            channels.append(self._to_channel_model(ch, area=str(area)))
                return channels
            return groups
        except Exception as e:
            logger.error("获取频道列表异常: %s", e)
            return []

    def get_channel_setting_info(self, channel: str) -> dict:
        """获取频道设置详情（名称、访问权限等）。"""
        channel = str(channel or "").strip()
        if not channel:
            return {"error": "缺少 channel"}

        url_path = "/area/v3/channel/setting/info"
        params = {"channel": channel}
        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                logger.error("获取频道设置失败: HTTP %d", resp.status_code)
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                msg = result.get("message") or result.get("error") or "未知错误"
                logger.error("获取频道设置失败: %s", msg)
                return {"error": msg}
            data = result.get("data", {})
            if not isinstance(data, dict):
                return {"error": "频道设置响应格式异常"}
            return data
        except Exception as e:
            logger.error("获取频道设置异常: %s", e)
            return {"error": str(e)}

    def _pick_channel_group(
        self,
        area: str,
        preferred_channel: Optional[str] = None,
        preferred_group_name: Optional[str] = None,
    ) -> Optional[str]:
        groups = self.get_area_channels(area=area, quiet=True) or []
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
    ) -> dict:
        """创建频道。"""
        area = area or self._config.default_area
        name = str(name or "").strip()
        if not name:
            return {"error": "频道名称不能为空"}

        if not group_id:
            group_id = self._pick_channel_group(area) or ""
            if not group_id:
                return {"error": "未找到可用频道分组"}

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
            resp = self._post("/client/v1/area/v1/channel/v1/create", body)
        except Exception as e:
            logger.error("创建频道异常: %s", e)
            return {"error": str(e)}

        raw = resp.text or ""
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")}

        try:
            result = resp.json()
        except Exception:
            return {"error": f"响应非 JSON: {raw[:200]}"}

        if not result.get("status"):
            msg = result.get("message") or "创建频道失败"
            code = result.get("code") or result.get("errorCode") or ""
            logger.warning("创建频道被拒: %s (code=%s), body=%s", msg, code, body)
            hint = "（可能需要域主/管理员权限）" if "服务" in msg or "权限" in msg else ""
            return {"error": f"{msg}{hint}"}

        data = result.get("data", {})
        channel_id = self._extract_channel_id(data) or self._extract_channel_id(result)
        return {
            "status": True,
            "channel": channel_id or "",
            "name": name,
            "message": "频道已创建",
        }

    def update_channel(
        self,
        area: Optional[str] = None,
        channel_id: str = "",
        overrides: Optional[dict] = None,
        *,
        name: str = "",
    ) -> dict:
        """修改频道设置。"""
        area = area or self._config.default_area
        channel_id = str(channel_id or "").strip()
        if not channel_id:
            return {"error": "缺少 channel_id"}

        setting = self.get_channel_setting_info(channel_id)
        if isinstance(setting, dict) and "error" in setting:
            return {"error": f"获取频道设置失败: {setting['error']}"}

        _BOOL_FIELDS = ("secret", "hasPassword", "voiceControlEnabled",
                        "textControlEnabled", "accessControlEnabled")
        _INT_FIELDS = ("textGapSecond", "maxMember")
        _STR_FIELDS = ("name", "voiceQuality", "voiceDelay", "password")

        edit_body = {
            "channel": channel_id,
            "area": area,
            "name": str(setting.get("name") or ""),
            "textGapSecond": int(setting.get("textGapSecond", 0) or 0),
            "voiceQuality": str(setting.get("voiceQuality") or "64k"),
            "voiceDelay": str(setting.get("voiceDelay") or "LOW"),
            "maxMember": int(setting.get("maxMember", 30000) or 30000),
            "voiceControlEnabled": bool(setting.get("voiceControlEnabled")),
            "textControlEnabled": bool(setting.get("textControlEnabled")),
            "textRoles": list(setting.get("textRoles") or []),
            "voiceRoles": list(setting.get("voiceRoles") or []),
            "accessControlEnabled": bool(setting.get("accessControlEnabled")),
            "accessible": list(setting.get("accessible") or []),
            "accessibleMembers": list(setting.get("accessibleMembers") or []),
            "secret": bool(setting.get("secret")),
            "hasPassword": bool(setting.get("hasPassword")),
            "password": str(setting.get("password") or ""),
        }

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

        try:
            resp = self._post("/area/v3/channel/setting/edit", edit_body)
        except Exception as e:
            logger.error("更新频道异常: %s", e)
            return {"error": str(e)}

        raw = resp.text or ""
        if resp.status_code != 200:
            logger.error("更新频道 HTTP %d: %s", resp.status_code, raw[:300])
            return {"error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")}

        try:
            result = resp.json()
        except Exception:
            return {"error": f"响应非 JSON: {raw[:200]}"}

        if not result.get("status"):
            return {"error": result.get("message") or "更新频道失败"}

        return {"status": True, "message": "频道已更新"}

    def create_restricted_text_channel(
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

        group_id = self._pick_channel_group(area, preferred_channel=preferred_channel)
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
            resp = self._post(url_path, body)
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

        if not result.get("status"):
            msg = result.get("message") or result.get("error") or "创建频道失败"
            return {"error": str(msg)}

        data = result.get("data", {})
        channel_id = self._extract_channel_id(data) or self._extract_channel_id(result)
        if not channel_id:
            return {"error": "创建频道成功，但未能提取频道 ID"}

        setting = self.get_channel_setting_info(channel_id)
        if isinstance(setting, dict) and "error" in setting:
            logger.warning("获取新频道设置失败，改用默认值: %s", setting["error"])
            setting = {}

        edit_body = {
            "channel": channel_id,
            "name": str(setting.get("name") or channel_name),
            "textGapSecond": int(setting.get("textGapSecond", 0) or 0),
            "area": area,
            "voiceQuality": str(setting.get("voiceQuality") or "64k"),
            "voiceDelay": str(setting.get("voiceDelay") or "LOW"),
            "maxMember": int(setting.get("maxMember", 30000) or 30000),
            "voiceControlEnabled": bool(setting.get("voiceControlEnabled", False)),
            "textControlEnabled": bool(setting.get("textControlEnabled", False)),
            "textRoles": list(setting.get("textRoles") or []),
            "voiceRoles": list(setting.get("voiceRoles") or []),
            "accessControlEnabled": True,
            "accessible": [],
            "accessibleMembers": [
                uid for uid in dict.fromkeys([
                    str(target_uid),
                    str(self._config.person_uid or ""),
                ]) if uid
            ],
            "secret": bool(setting.get("secret", True)),
            "hasPassword": bool(setting.get("hasPassword", False)),
            "password": str(setting.get("password") or ""),
        }

        edit_path = "/area/v3/channel/setting/edit"
        try:
            edit_resp = self._post(edit_path, edit_body)
        except Exception as e:
            logger.error("设置受限频道权限异常: %s", e)
            self.delete_channel(channel_id, area=area)
            return {"error": str(e)}

        edit_raw = edit_resp.text or ""
        logger.info("设置受限频道权限 POST %s -> HTTP %d, body: %s", edit_path, edit_resp.status_code, edit_raw[:300])
        if edit_resp.status_code != 200:
            self.delete_channel(channel_id, area=area)
            return {"error": f"HTTP {edit_resp.status_code}" + (f" | {edit_raw[:200]}" if edit_raw else "")}

        try:
            edit_result = edit_resp.json()
        except Exception:
            self.delete_channel(channel_id, area=area)
            return {"error": f"权限设置响应非 JSON: {edit_raw[:200]}"}

        if not edit_result.get("status"):
            self.delete_channel(channel_id, area=area)
            msg = edit_result.get("message") or edit_result.get("error") or "权限设置失败"
            return {"error": str(msg)}

        logger.info("创建受限频道成功: channel=%s target=%s", channel_id[:24], target_uid[:12])
        return {
            "status": True,
            "channel": channel_id,
            "group": group_id,
            "name": edit_body["name"],
        }

    def delete_channel(self, channel: str, area: Optional[str] = None) -> dict:
        """删除频道。"""
        area = area or self._config.default_area
        channel = str(channel or "").strip()
        if not channel:
            return {"error": "缺少 channel"}

        url_path = f"/client/v1/area/v1/channel/v1/delete?channel={channel}&area={area}"

        try:
            resp = self._delete(url_path)
        except Exception as e:
            logger.error("删除频道异常: %s", e)
            return {"error": str(e)}

        raw = resp.text or ""
        logger.info("删除频道 DELETE %s -> HTTP %d, body: %s", url_path, resp.status_code, raw[:300])
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")}

        try:
            result = resp.json()
        except Exception:
            return {"error": f"响应非 JSON: {raw[:200]}"}

        if result.get("status") is True:
            return {"status": True, "message": result.get("message") or "已删除频道"}

        err = result.get("message") or result.get("error") or str(result)
        logger.error("删除频道失败: %s", err)
        return {"error": err}

    def enter_channel(self, channel: Optional[str] = None, area: Optional[str] = None,
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
            resp = self._post(url_path, body)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                return {"error": result.get("message") or "未知错误"}
            return result.get("data", {})
        except Exception as e:
            logger.error("进入频道异常: %s", e)
            return {"error": str(e)}

    def leave_voice_channel(self, channel: str, area: Optional[str] = None,
                            target: Optional[str] = None) -> dict:
        """退出语音频道。"""
        area = area or self._config.default_area
        target = target or self._config.person_uid
        url_path = "/client/v1/area/v1/member/v1/removeFromChannel"
        query = f"?area={area}&channel={channel}&target={target}"
        full_path = url_path + query

        try:
            body_str = ""
            headers = {**self.session.headers, **self.signer.oopz_headers(full_path, body_str)}
            url = self._config.base_url + full_path
            resp = self.session.delete(url, headers=headers)
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

    def _get_voice_channel_ids(self, area: str) -> list[str]:
        cache_store = self._get_voice_ids_cache_store()
        cached = cache_store.get(area)
        if cached and time.time() - cached["ts"] < 300:
            return cached["ids"]
        groups = self.get_area_channels(area, quiet=True)
        ids = []
        for g in groups:
            for ch in g.get("channels") or []:
                if str(ch.get("type", "")).upper() in ("VOICE", "AUDIO"):
                    ids.append(ch["id"])
        cache_store[area] = {"ids": ids, "ts": time.time()}
        return ids

    def get_voice_channel_members(self, area: Optional[str] = None) -> dict:
        """获取域内各语音频道的在线成员列表。"""
        area = area or self._config.default_area
        voice_ids = self._get_voice_channel_ids(area)
        if not voice_ids:
            return {}

        url_path = "/area/v3/channel/membersByChannels"
        body = {"area": area, "channels": voice_ids}
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = self._post(url_path, body)
                if resp.status_code == 429:
                    wait = min(2 ** attempt, 4)
                    logger.warning("获取语音频道成员被限流 (429)，%ds 后重试 (%d/%d)", wait, attempt + 1, max_retries)
                    time.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.error("获取语音频道成员失败: HTTP %d", resp.status_code)
                    return {}
                result = resp.json()
                if not result.get("status"):
                    return {}
                return result.get("data", {}).get("channelMembers", {})
            except Exception as e:
                logger.error("获取语音频道成员异常: %s", e)
                return {}
        logger.error("获取语音频道成员失败: 重试次数用尽")
        return {}

    def get_voice_channel_for_user(self, user_uid: str, area: Optional[str] = None) -> Optional[str]:
        """获取用户当前所在的语音频道 ID，不在任何语音频道则返回 None。"""
        members = self.get_voice_channel_members(area=area)
        for ch_id, ch_members in members.items():
            if not ch_members:
                continue
            for m in ch_members:
                uid = m.get("uid", m.get("id", "")) if isinstance(m, dict) else str(m)
                if uid == user_uid:
                    return ch_id
        return None
