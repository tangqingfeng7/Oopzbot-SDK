from __future__ import annotations

import logging
from typing import Any, Optional

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.member")


class Member(BaseService):
    """用户相关能力：个人资料、成员搜索、身份组分配等。"""

    async def get_person_infos_batch(self, uids: list[str]) -> list[models.UserInfo]:
        """批量获取用户基本信息。"""
        if not uids:
            return []

        url_path = "/client/v1/person/v1/personInfos"
        batch_size = 30
        result: list[models.UserInfo] = []

        for i in range(0, len(uids), batch_size):
            batch = uids[i: i + batch_size]
            body = {"persons": batch, "commonIds": []}
            data = await self._request_data("POST", url_path, body=body)
            if not isinstance(data, list):
                raise OopzApiError(
                    "person infos response format error: expected list",
                    payload=data,
                )
            for item in data:
                result.append(models.UserInfo.from_api(item))

        return result

    async def get_person_info(self, uid: str = None) -> models.UserInfo:
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
        return models.UserInfo.from_api(data[0])

    async def get_person_detail_full(self, uid: str) -> models.Profile:
        """获取他人完整详细资料（含 VIP、IP 属地等）。"""
        if not uid:
            raise ValueError("uid is required for get_person_detail_full()")

        url_path = "/client/v1/person/v1/personDetail"
        data = await self._request_data("GET", url_path, params={"uid": uid})
        return models.Profile.from_api(data)

    async def get_self_detail(self) -> models.Profile:
        """获取当前登录用户的完整详细资料。"""
        uid = getattr(self._config, "person_uid", None)
        if not uid:
            raise ValueError("person_uid is required for get_self_detail()")

        url_path = "/client/v1/person/v2/selfDetail"
        data = await self._request_data("GET", url_path, params={"uid": uid})
        return models.Profile.from_api(data)

    async def get_level_info(self) -> models.UserLevelInfo:
        """获取当前用户等级、积分信息。"""
        url_path = "/user_points/v1/level_info"
        data = await self._request_data("GET", url_path)
        return models.UserLevelInfo.from_api(data)

