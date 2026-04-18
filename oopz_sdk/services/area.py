from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Optional

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.area")


class AreaService(BaseService):
    """Area-related platform capabilities."""

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

    @staticmethod
    def _to_member_model(payload: dict) -> models.Member:
        return models.Member(
            uid=str(payload.get("uid") or payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("nickname") or ""),
            nickname=str(payload.get("name") or payload.get("nickname") or ""),
            avatar=str(payload.get("avatar") or payload.get("avatarUrl") or ""),
            online=bool(payload.get("online") in (1, True)),
            payload=dict(payload),
        )

    @staticmethod
    def _to_area_model(payload: dict) -> models.Area:
        return models.Area(
            id=str(payload.get("id") or payload.get("code") or ""),
            name=str(payload.get("name") or ""),
            code=str(payload.get("code") or ""),
            description=str(payload.get("description") or ""),
            payload=dict(payload),
        )

    async def get_area_members(
        self,
        area: Optional[str] = None,
        offset_start: int = 0,
        offset_end: int = 49,
        quiet: bool = False,
        *,
        as_model: bool = False,
    ) -> dict | models.AreaMembersPage:
        """获取域内成员列表及在线状态。"""
        area = area or self._config.default_area
        url_path = "/area/v3/members"
        params = {"area": area, "offsetStart": str(offset_start), "offsetEnd": str(offset_end)}
        max_attempts = 3
        cache_key = (str(area), int(offset_start), int(offset_end))
        cache_ttl = float(getattr(self._config, "area_members_cache_ttl", 2.0))
        stale_ttl = float(getattr(self._config, "area_members_stale_ttl", 300.0))

        if quiet:
            cached = self._get_cached_area_members(cache_key, max_age=cache_ttl)
            if cached is not None:
                return cached

        try:
            resp = None
            for attempt in range(1, max_attempts + 1):
                resp = await self._await_if_needed(self._get(url_path, params=params))
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
                        logger.warning(
                            "获取域成员被限流，返回 %.1fs 内缓存数据 (area=%s, offset=%s-%s)",
                            stale_ttl, area, offset_start, offset_end,
                        )
                        return stale_cached
                    logger.warning(
                        "获取域成员被限流: HTTP 429 (area=%s, offset=%s-%s, 已重试%d次)",
                        area, offset_start, offset_end, max_attempts - 1,
                    )
                    err = {"error": "HTTP 429"}
                    if as_model:
                        return models.AreaMembersPage(payload=err)
                    return err

                logger.warning(
                    "获取域成员被限流: HTTP 429 (area=%s, offset=%s-%s), %.1fs 后重试 (%d/%d)",
                    area, offset_start, offset_end, float(wait_seconds), attempt, max_attempts - 1,
                )
                await asyncio.sleep(wait_seconds)

            if resp is None:
                return {"error": "未获得响应"}

            if resp.status_code != 200:
                logger.debug("获取域成员失败: HTTP %d", resp.status_code)
                stale = self._get_cached_area_members(cache_key, max_age=stale_ttl)
                if stale is not None:
                    stale["stale"] = True
                    return stale
                err = {"error": f"HTTP {resp.status_code}"}
                if as_model:
                    return models.AreaMembersPage(payload=err, response=resp)
                return err

            if not resp.content:
                logger.debug("获取域成员失败: HTTP 200 但响应体为空")
                stale = self._get_cached_area_members(cache_key, max_age=stale_ttl)
                if stale is not None:
                    stale["stale"] = True
                    return stale
                err = {"error": "empty response"}
                if as_model:
                    return models.AreaMembersPage(payload=err, response=resp)
                return err

            try:
                result = resp.json()
            except ValueError:
                content_encoding = (resp.headers.get("Content-Encoding") or "").lower()
                if content_encoding in ("br", "zstd") or (
                    resp.content and resp.content[:4] != b'{"st'
                ):
                    logger.debug(
                        "获取域成员失败: 响应体可能未被正确解压 "
                        "(Content-Encoding=%s, len=%d)。"
                        "请确保已安装 brotli 和 zstandard 包",
                        content_encoding or "未知", len(resp.content),
                    )
                else:
                    logger.debug(
                        "获取域成员失败: 响应非合法 JSON (len=%d, status=%d, preview=%r)",
                        len(resp.content), resp.status_code, resp.content[:200],
                    )
                stale = self._get_cached_area_members(cache_key, max_age=stale_ttl)
                if stale is not None:
                    stale["stale"] = True
                    return stale
                err = {"error": "invalid JSON"}
                if as_model:
                    return models.AreaMembersPage(payload=err, response=resp)
                return err
            if not result.get("status"):
                msg = result.get("message") or result.get("error") or "未知错误"
                logger.debug("获取域成员失败: %s", msg)
                stale = self._get_cached_area_members(cache_key, max_age=stale_ttl)
                if stale is not None:
                    stale["stale"] = True
                    return stale
                err = {"error": msg}
                if as_model:
                    return models.AreaMembersPage(payload=err, response=resp)
                return err

            data = result.get("data", {})
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
            self._set_cached_area_members(cache_key, data)
            if as_model:
                members_payload = data.get("members") or []
                members = [
                    self._to_member_model(m) for m in members_payload if isinstance(m, dict)
                ]
                return models.AreaMembersPage(
                    members=members,
                    online_count=int(data.get("onlineCount") or 0),
                    total_count=int(data.get("totalCount") or 0),
                    user_count=int(data.get("userCount") or 0),
                    fetched_count=int(data.get("fetchedCount") or 0),
                    stale=bool(data.get("stale")),
                    rate_limited=bool(data.get("rateLimited")),
                    from_cache=bool(data.get("from_cache")),
                    payload=dict(data),
                    response=resp,
                )
            return data
        except Exception as e:
            logger.error("获取域成员异常: %s", e)
            stale = self._get_cached_area_members(cache_key, max_age=stale_ttl)
            if stale is not None:
                stale["stale"] = True
                return stale
            err = {"error": str(e)}
            if as_model:
                return models.AreaMembersPage(payload=err)
            return err

    async def get_joined_areas(
        self,
        quiet: bool = False,
        *,
        as_model: bool = False,
    ) -> list[dict] | models.JoinedAreasResult:
        """获取当前用户已加入（订阅）的域列表。"""
        url_path = "/userSubscribeArea/v1/list"
        try:
            resp = await self._await_if_needed(self._get(url_path))
            if resp.status_code != 200:
                logger.error("获取已加入域列表失败: HTTP %d", resp.status_code)
                return []
            result = resp.json()
            if not result.get("status"):
                logger.error("获取已加入域列表失败: %s", result.get("message") or result.get("error"))
                return []
            areas = result.get("data", [])
            if not quiet:
                logger.info("获取已加入域列表: %d 个域", len(areas))
                for a in areas:
                    logger.info("  域: %s (ID=%s, code=%s)", a.get("name"), a.get("id"), a.get("code"))
            if as_model:
                return models.JoinedAreasResult(
                    areas=[self._to_area_model(a) for a in areas if isinstance(a, dict)],
                    payload={"areas": areas},
                    response=resp,
                )
            return areas
        except Exception as e:
            logger.error("获取已加入域列表异常: %s", e)
            if as_model:
                return models.JoinedAreasResult(payload={"error": str(e)})
            return []

    async def get_area_info(self, area: Optional[str] = None, *, as_model: bool = False) -> dict | models.Area:
        """获取域详细信息（含角色列表、主页频道等）。"""
        area = self._resolve_area(area)
        url_path = "/area/v3/info"
        params = {"area": area}
        try:
            resp = await self._await_if_needed(self._get(url_path, params=params))
            if resp.status_code != 200:
                logger.error("获取域详情失败: HTTP %d", resp.status_code)
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                return {"error": result.get("message") or result.get("error") or "未知错误"}
            data = result.get("data", {})
            if as_model and isinstance(data, dict):
                return self._to_area_model(data)
            return data
        except Exception as e:
            logger.error("获取域详情异常: %s", e)
            return {"error": str(e)}

    async def enter_area(self, area: Optional[str] = None, recover: bool = False) -> dict:
        """进入指定域。"""
        area = area or self._config.default_area
        url_path = f"/client/v1/area/v1/enter?area={area}&recover={str(recover).lower()}"
        body = {"area": area, "recover": recover}
        try:
            resp = await self._await_if_needed(self._post(url_path, body))
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                return {"error": result.get("message") or result.get("error") or "未知错误"}
            return result.get("data", {})
        except Exception as e:
            logger.error("进入域异常: %s", e)
            return {"error": str(e)}

    async def get_area_channels(self, area: Optional[str] = None, quiet: bool = True) -> list:
        """Fetch all channel groups in an area."""
        area = area or self._config.default_area
        url_path = "/client/v1/area/v1/detail/v1/channels"
        params = {"area": area}

        try:
            resp = await self._await_if_needed(self._get(url_path, params=params))
            if resp.status_code != 200:
                logger.error("get_area_channels failed: HTTP %d", resp.status_code)
                return []

            result = resp.json()
            if not result.get("status"):
                logger.error("get_area_channels failed: %s", result.get("message") or result.get("error"))
                return []

            groups = result.get("data") or []
            if not quiet:
                total = sum(len(g.get("channels") or []) for g in groups)
                logger.info("get_area_channels success: %d channels in %d groups", total, len(groups))
            return groups
        except Exception as e:
            logger.error("get_area_channels exception: %s", e)
            return []

    async def populate_names(self, *, set_area=None, set_channel=None) -> dict:
        """从 API 获取已加入域列表及各域频道列表，通过回调填充名称。

        Args:
            set_area: 可选回调 (area_id, area_name) -> None
            set_channel: 可选回调 (channel_id, channel_name) -> None

        Returns:
            {"areas_named": int, "channels_named": int}
        """
        areas_count = 0
        channels_count = 0
        areas = await self.get_joined_areas()
        for a in areas:
            area_id = a.get("id", "")
            area_name = a.get("name", "")
            if area_id and area_name and set_area:
                set_area(area_id, area_name)
                areas_count += 1

            groups = await self.get_area_channels(area_id) or []
            for group in groups:
                for ch in (group.get("channels") or []):
                    ch_id = ch.get("id", "")
                    ch_name = ch.get("name", "")
                    if ch_id and ch_name and set_channel:
                        set_channel(ch_id, ch_name)
                        channels_count += 1

        logger.info("名称自动填充完成: %d 个域, %d 个频道", areas_count, channels_count)
        return {"areas_named": areas_count, "channels_named": channels_count}
