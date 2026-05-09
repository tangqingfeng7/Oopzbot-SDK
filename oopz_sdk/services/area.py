from __future__ import annotations

import inspect
import logging

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError

from . import BaseService

logger = logging.getLogger(__name__)


class AreaService(BaseService):
    """Area-related platform capabilities."""


    async def get_area_members(
            self,
            area: str,
            offset_start: int = 0,
            offset_end: int = 49,
            *,
            force: bool=False,
    ) -> models.AreaMembersPage:
        if area.strip() == "":
            raise ValueError("area cannot be empty")


        if not force:
            cached = self.cache.get_area_members_page(area, offset_start, offset_end)
            if cached is not None:
                return cached

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

        page = models.AreaMembersPage.from_api(data)

        self.cache.set_area_members_page(area, offset_start, offset_end, page)

        return page

    async def get_all_area_members(
            self,
            area: str,
            *,
            page_size: int = 100,
            max_pages: int | None = None,
            force: bool = False,
    ) -> list[models.AreaMemberInfo]:
        if area.strip() == "":
            raise ValueError("area cannot be empty")

        members: list[models.AreaMemberInfo] = []
        offset_start = 0
        page_count = 0

        while True:
            offset_end = offset_start + page_size - 1

            page = await self.get_area_members(
                area,
                offset_start=offset_start,
                offset_end=offset_end,
                force=force
            )

            members.extend(page.members)

            page_count += 1


            if max_pages is not None and page_count >= max_pages:
                break

            if not page.members:
                break

            if page.total_count and len(members) >= page.total_count:
                break

            if len(page.members) < page_size:
                break

            offset_start += page_size

        return members

    async def get_joined_areas(
        self
    ) -> list[models.JoinedAreaInfo]:
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

    async def edit_area_name(self, area: str, name: str) -> models.OperationResult:
        if area.strip() == "":
            raise ValueError("area cannot be empty")
        if name.strip() == "":
            raise ValueError("name cannot be empty")
        url_path = "/client/v1/area/v1/areaSettings/v1/editAreaName"
        data = await self._request_data("PUT", url_path, body={
            "area": area,
            "name": name,
        })
        return models.OperationResult.from_api(data)

    async def enter_area(self, area: str, recover: bool = False) -> dict:
        """进入指定域。"""
        if area.strip() == "":
            raise ValueError("area is required for enter_area")

        data = await self._request_data(
            "POST",
            "/client/v1/area/v1/enter",
            params={"area": area, "recover": str(recover).lower()},
            body={"area": area, "recover": recover},
        )
        return data if isinstance(data, dict) else {}



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

        if not isinstance(data, dict):
            raise OopzApiError(
                "area can give roles response format error: expected dict",
                payload=data,
            )
        roles = data.get("roles")
        if not isinstance(roles, list):
            raise OopzApiError(
                "area can give roles response format error: expected 'roles' list",
                payload=data,
            )

        return [models.RoleInfo.from_api(role) for role in roles]


    async def edit_user_role(
            self,
            area: str,
            target_uid: str,
            role_id: int,
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
        result = models.OperationResult.from_api(resp)

        # 当用户信息发生修改的时候清除域的缓存
        self.cache.invalidate_area_members_pages(area)
        return result


    async def get_user_area_nicknames(
            self,
            area: str,
            uids: list[str] | str,
            *,
            force: bool = False,
    ) -> dict[str, str]:
        """批量获取用户在域内的昵称（备注）。

        Example:
            {"2ce12124c07111ef9e5dc6b17c3481f1": "盐盐盐"}
        """
        if not area:
            raise ValueError("area is required for get_user_area_nicknames()")

        if isinstance(uids, str):
            uids = [uids]

        if not isinstance(uids, list):
            raise ValueError(
                "uids must be a list[str] or str for get_user_area_nicknames()"
            )

        if not all(isinstance(uid, str) for uid in uids):
            raise ValueError(
                "uids must contain only str values for get_user_area_nicknames()"
            )

        if not uids:
            raise ValueError("uids cannot be empty for get_user_area_nicknames()")

        result: dict[str, str] = {}
        missing_uids: list[str] = []

        if not force:
            for uid in uids:
                cached = self.cache.get_area_user_nickname(area, uid)
                if cached is not None:
                    result[uid] = cached
                else:
                    missing_uids.append(uid)
        else:
            missing_uids = uids

        # 全部命中缓存
        if not missing_uids:
            return result

        data = await self._request_data("POST", "/area/v2/getUserAreaNicknames", body={
            "area": area,
            "uids": missing_uids,
        })

        if not isinstance(data, dict):
            raise OopzApiError(
                "area nicknames response format error: expected dict",
                payload=data,
            )

        nicknames = data.get("nicknames")
        if not isinstance(nicknames, dict):
            raise OopzApiError(
                "area nicknames response format error: expected 'nicknames' dict",
                payload=data,
            )

        for uid, nick in nicknames.items():
            uid = str(uid)
            nick = str(nick)

            result[uid] = nick
            self.cache.set_area_user_nickname(area, uid, nick)

        return result

    async def leave_area(self, area: str) -> models.OperationResult:
        """离开指定域。"""
        if area.strip() == "":
            raise ValueError("area is required for leave_area")

        data = await self._request_data(
            "DELETE",
            "/client/v1/area/v1/quit",
            body={"area": area},
        )
        return models.OperationResult.from_api(data)

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
                    result = set_area(area.area_id, area.name)
                    if inspect.isawaitable(result):
                        await result
                    areas_count += 1

            groups = await self.get_area_channels(area.area_id)
            for group in groups:
                for ch in group.channels:
                    if ch.channel_id and ch.name:
                        if set_channel:
                            result = set_channel(ch.channel_id, ch.name)
                            if inspect.isawaitable(result):
                                await result
                            channels_count += 1

        logger.info("Name population completed: %d areas, %d channels", areas_count, channels_count)
        return {"areas_named": areas_count, "channels_named": channels_count}
