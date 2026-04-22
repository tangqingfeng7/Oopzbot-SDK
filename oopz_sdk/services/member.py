from __future__ import annotations

import logging
from typing import Any, Optional

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.member")


class Member(BaseService):
    """用户相关能力：个人资料、成员搜索、身份组分配等。"""

    async def get_person_infos_batch(self, uids: list[str]) -> list[models.Member]:
        """批量获取用户基本信息。"""
        if not uids:
            return []

        url_path = "/client/v1/person/v1/personInfos"
        batch_size = 30
        result: list[models.Member] = []

        for i in range(0, len(uids), batch_size):
            batch = uids[i : i + batch_size]
            body = {"persons": batch, "commonIds": []}
            data = await self._request_data("POST", url_path, body=body)
            if not isinstance(data, list):
                raise OopzApiError(
                    "person infos response format error: expected list",
                    payload=data,
                )
            for item in data:
                result.append(models.Member.from_api(item))

        return result

    async def get_person_detail(self, uid: Optional[str] = None) -> models.PersonDetail:
        """获取指定用户的基本信息，默认当前登录用户。"""
        uid = uid or getattr(self._config, "person_uid", None)
        if not uid:
            raise ValueError("uid is required for get_person_detail()")

        url_path = "/client/v1/person/v1/personInfos"
        body = {"persons": [uid], "commonIds": []}
        data = await self._request_data("POST", url_path, body=body)

        if not isinstance(data, list):
            raise OopzApiError(
                "person detail response format error: expected list",
                payload=data,
            )
        if not data:
            raise OopzApiError(
                "person detail not found",
                payload={"uid": uid},
            )
        return models.PersonDetail.from_api(data[0])

    async def get_person_detail_full(self, uid: str) -> dict:
        """获取他人完整详细资料（含 VIP、IP 属地等）。"""
        if not uid:
            raise ValueError("uid is required for get_person_detail_full()")

        url_path = "/client/v1/person/v1/personDetail"
        data = await self._request_data("GET", url_path, params={"uid": uid})
        if not isinstance(data, dict):
            raise OopzApiError(
                "person detail full response format error: expected dict",
                payload=data,
            )
        return data

    async def get_self_detail(self) -> models.SelfDetail:
        """获取当前登录用户的完整详细资料。"""
        uid = getattr(self._config, "person_uid", None)
        if not uid:
            raise ValueError("person_uid is required for get_self_detail()")

        url_path = "/client/v1/person/v2/selfDetail"
        data = await self._request_data("GET", url_path, params={"uid": uid})
        if not isinstance(data, dict):
            raise OopzApiError(
                "self detail response format error: expected dict",
                payload=data,
            )
        return models.SelfDetail.from_api(data)

    async def get_level_info(self) -> dict:
        """获取当前用户等级、积分信息。"""
        url_path = "/user_points/v1/level_info"
        data = await self._request_data("GET", url_path)
        if not isinstance(data, dict):
            raise OopzApiError(
                "level info response format error: expected dict",
                payload=data,
            )
        return data

    async def get_user_area_detail(self, target: str, area: str) -> dict:
        """获取指定用户在域内的角色列表和禁言/禁麦状态。"""
        if not target:
            raise ValueError("target is required for get_user_area_detail()")
        if not area:
            raise ValueError("area is required for get_user_area_detail()")

        url_path = "/area/v3/userDetail"
        params = {"area": area, "target": target}
        data = await self._request_data("GET", url_path, params=params)
        if not isinstance(data, dict):
            raise OopzApiError(
                "user area detail response format error: expected dict",
                payload=data,
            )
        return data

    async def get_assignable_roles(
        self,
        target: str,
        area: Optional[str] = None,
    ) -> list[dict]:
        """获取当前用户可以分配给目标用户的角色列表。"""
        if not target:
            raise ValueError("target is required for get_assignable_roles()")
        if not area:
            raise ValueError("area is required for get_assignable_roles()")

        url_path = "/area/v3/role/canGiveList"
        params = {"area": area, "target": target}
        data = await self._request_data_with_retry(
            "GET", url_path, params=params,
            retry_on_429=True, max_attempts=3,
        )
        if not isinstance(data, dict):
            raise OopzApiError(
                "assignable roles response format error: expected dict",
                payload=data,
            )
        roles = data.get("roles", [])
        if not isinstance(roles, list):
            raise OopzApiError(
                "assignable roles response format error: roles must be a list",
                payload=data,
            )
        for idx, role in enumerate(roles):
            if not isinstance(role, dict):
                raise OopzApiError(
                    f"assignable roles response format error: roles[{idx}] must be a dict",
                    payload=data,
                )
        return roles

    async def edit_user_role(
        self,
        target_uid: str,
        role_id: int,
        add: bool,
        area: Optional[str] = None,
    ) -> models.OperationResult:
        """给目标用户添加或取消指定身份组。"""
        if not target_uid:
            raise ValueError("target_uid is required for edit_user_role()")
        if not area:
            raise ValueError("area is required for edit_user_role()")

        detail = await self.get_user_area_detail(target_uid, area=area)
        current_list = detail.get("list") or []
        if not isinstance(current_list, list) or any(
            not isinstance(role, dict) for role in current_list
        ):
            raise OopzApiError(
                "user area detail response format error: list must be a list of dicts",
                payload=detail,
            )

        current_ids = [
            int(r["roleID"]) for r in current_list if r.get("roleID") is not None
        ]
        role_id = int(role_id)
        if add:
            if role_id not in current_ids:
                current_ids.append(role_id)
        else:
            current_ids = [x for x in current_ids if x != role_id]

        body = {"area": area, "target": target_uid, "targetRoleIDs": current_ids}
        resp = await self._request_data("POST", "/area/v3/role/editUserRole", body=body)
        return models.OperationResult.from_api(resp)

    async def search_area_members(
        self,
        area: str,
        keyword: str = "",
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[models.Member]:
        """搜索域内成员。"""
        if not area:
            raise ValueError("area is required for search_area_members()")

        url_path = "/area/v3/search/areaSettingMembers"
        body = {"area": area, "name": keyword, "offset": offset, "limit": limit}
        data = await self._request_data("POST", url_path, body=body)
        if not isinstance(data, dict):
            raise OopzApiError(
                "search area members response format error: expected dict",
                payload=data,
            )
        members = data.get("members", [])
        if not isinstance(members, list):
            raise OopzApiError(
                "search area members response format error: members must be a list",
                payload=data,
            )
        return [models.Member.from_api(item) for item in members]
