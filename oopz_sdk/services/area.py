from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Optional, List

from oopz_sdk import models

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.area")


class AreaService(BaseService):
    """Area-related platform capabilities."""

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

    async def get_area_members(
            self,
            area: str,
            offset_start: int = 0,
            offset_end: int = 49,
    ) -> models.AreaMembersPage:
        if area.strip() == "":
            raise ValueError("area cannot be empty")
        cache_key = (area, offset_start, offset_end)
        cache_ttl = float(getattr(self._config, "area_members_cache_ttl", 15.0))

        cached = self._get_cached_area_members(cache_key, max_age=cache_ttl)
        if cached is not None:
            cached["from_cache"] = True
            model = models.AreaMembersPage.from_api(cached)
            return model

        data = await self._request_data_with_retry(
            "GET",
            "/area/v3/members",
            params={
                "area": area,
                "offsetStart": str(offset_start),
                "offsetEnd": str(offset_end),
            },
            retry_on_429=True,
            max_attempts=3,
        )
        model = models.AreaMembersPage.from_api(data)

        normalized = {
            "members": copy.deepcopy(model.members),
            "roleCount": copy.deepcopy(model.role_count),
            "totalCount": model.total_count,
            "payload": copy.deepcopy(model.payload),
        }

        self._set_cached_area_members(cache_key, normalized)
        return model

    async def get_joined_areas(
        self
    ) -> List[models.JoinedAreaInfo]:
        """获取当前用户已加入（订阅）的域列表。"""
        url_path = "/userSubscribeArea/v1/list"
        data = await self._request_data("GET", url_path)
        result: list[models.JoinedAreaInfo] = []
        for i, item in enumerate(data):
            result.append(models.JoinedAreaInfo.from_api(item))
        return result

    async def get_area_info(self, area: str) -> models.AreaInfo:
        """获取域详细信息（含角色列表、主页频道等）。"""
        if area.strip() == "":
            raise ValueError("area cannot be empty")
        url_path = "/area/v3/info"
        params = {"area": area}
        data = await self._request_data("GET", url_path, params=params)
        return models.AreaInfo.from_api(data)

    async def enter_area(self, area: str, recover: bool = False) -> dict:
        """进入指定域。todo"""
        url_path = f"/client/v1/area/v1/enter?area={area}&recover={str(recover).lower()}"
        body = {"area": area, "recover": recover}

        try:
            resp = await self._post(url_path, body)
            if resp.status_code != 200:
                return self._error_payload(
                    f"HTTP {resp.status_code}",
                    payload={**body, "error": f"HTTP {resp.status_code}"},
                )
            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                return self._error_payload(
                    msg,
                    payload={**body, **result, "error": msg},
                )
            return result.get("data", {})
        except Exception as e:
            logger.error("进入域异常: %s", e)
            return self._error_payload(str(e), payload={**body, "error": str(e)})



    async def get_area_channels(self, area: str) -> list[models.ChannelGroupInfo]:
        """Fetch all channel groups in an area."""
        if area.strip() == "":
            raise ValueError("area cannot be empty")
        url_path = "/client/v1/area/v1/detail/v1/channels"
        params = {"area": area}
        data = await self._request_data("GET", url_path, params=params)
        return [models.ChannelGroupInfo.from_api(item) for item in data]

    async def get_area_user_detail(self, area: str, target: str) -> models.AreaUserDetail:
        """获取指定用户在域内的角色列表和禁言/禁麦状态。"""
        if not target:
            raise ValueError("target is required for get_user_area_detail()")
        if not area:
            raise ValueError("area is required for get_user_area_detail()")

        url_path = "/area/v3/userDetail"
        params = {"area": area, "target": target}
        data = await self._request_data("GET", url_path, params=params)
        return models.AreaUserDetail.from_api(data)


    async def get_area_can_give_list(self, area: str, target: str) -> list[models.RoleInfo]:
        """获取当前用户可以分配给目标用户的角色列表。"""
        if not target:
            raise ValueError("target is required for get_assignable_roles()")
        if not area:
            raise ValueError("area is required for get_assignable_roles()")

        url_path = "/area/v3/role/canGiveList"

        data = await self._request_data("GET", url_path, params={"area": area, "target": target})

        roles = data.get('roles')
        if roles is None:
            raise ValueError("Invalid API response: 'roles' field is missing or not a list")

        return [models.RoleInfo.from_api(role) for role in roles]


    async def edit_user_role(
            self,
            target_uid: str,
            role_id: int,
            area: str,
            add: bool = True,
    ) -> models.OperationResult:
        """给目标用户添加或取消指定身份组。"""
        if target_uid.strip() == "":
            raise ValueError("target_uid is required for edit_user_role()")
        if area.strip() == "":
            raise ValueError("area is required for edit_user_role()")

        area_info = await self.get_area_user_detail(area, target_uid)

        current_ids = [role.role_id for role in area_info.roles]
        if add:
            if role_id not in current_ids:
                current_ids.append(role_id)
        else:
            current_ids = [x for x in current_ids if x != role_id]

        body = {"area": area, "target": target_uid, "targetRoleIDs": current_ids}
        resp = await self._request_data("POST", "/area/v3/role/editUserRole", body=body)
        return models.OperationResult.from_api(resp)

    # async def search_area_members(
    #         self,
    #         area: str,
    #         keyword: str = "",
    #         *,
    #         offset: int = 0,
    #         limit: int = 50,
    # ) -> None:
    #     """搜索域内成员。"""
    #     if not area:
    #         raise ValueError("area is required for search_area_members()")
    #
    #     url_path = "/area/v3/search/areaSettingMembers"
    #     body = {"area": area, "name": keyword, "offset": offset, "limit": limit}
    #
    #     raise NotImplementedError("unknown usage method")


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

        for area in areas:
            if area.area_id and area.name:
                if set_area:
                    set_area(area.area_id, area.name)
                    areas_count += 1

            groups = await self.get_area_channels(area.area_id)
            for group in groups:
                for ch in group.channels:
                    if ch.channel_id and ch.name:
                        if set_channel:
                            set_channel(ch.channel_id, ch.name)
                            channels_count += 1

        logger.info("Name population completed: %d areas, %d channels", areas_count, channels_count)
        return {"areas_named": areas_count, "channels_named": channels_count}
