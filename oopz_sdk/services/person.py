from __future__ import annotations

import logging
from typing import Optional
from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError

from . import BaseService

logger = logging.getLogger(__name__)


class Person(BaseService):
    """用户相关能力：个人资料、成员搜索、身份组分配等。"""

    async def get_person_infos_batch(
            self,
            uids: list[str],
            *,
            force: bool = False,
    ) -> list[models.UserInfo]:
        """批量获取用户基本信息。

        Args:
            uids: 用户 ID 列表。
            force: 是否跳过缓存读取并强制请求接口。请求成功后仍会更新缓存。
        """
        if not uids:
            return []

        users_by_uid: dict[str, models.UserInfo] = {}
        missing_uids: list[str] = []

        if not force:
            for uid in uids:
                cached = self.cache.get_userinfo(uid)
                if cached is not None:
                    users_by_uid[uid] = cached
                else:
                    missing_uids.append(uid)
        else:
            missing_uids = uids

        url_path = "/client/v1/person/v1/personInfos"
        batch_size = 30

        for i in range(0, len(missing_uids), batch_size):
            batch = missing_uids[i: i + batch_size]
            body = {"persons": batch, "commonIds": []}

            data = await self._request_data("POST", url_path, body=body)

            if not isinstance(data, list):
                raise OopzApiError(
                    "person infos response format error: expected list",
                    payload=data,
                )

            for item in data:
                user = models.UserInfo.from_api(item)

                if not user.uid:
                    continue

                users_by_uid[user.uid] = user
                self.cache.set_userinfo(user.uid, user)

        return [
            users_by_uid[uid]
            for uid in uids
            if uid in users_by_uid
        ]

    async def get_person_info(
            self,
            uid: Optional[str] = None,
            *,
            force=False
    ) -> models.UserInfo:
        """获取指定用户的基本信息，默认当前登录用户。"""
        uid = uid or getattr(self._config, "person_uid", None)
        if not uid:
            raise ValueError("uid is required for get_person_info()")

        users = await self.get_person_infos_batch(
            [str(uid)],
            force=force
        )

        if not users:
            raise OopzApiError(
                "person detail not found",
                payload={"uid": uid},
            )

        return users[0]

    async def fetch_person_detail_full(self, uid: str) -> models.Profile:
        """强制从接口获取他人完整详细资料，不读写 cache。"""
        if not uid:
            raise ValueError("uid is required for fetch_person_detail_full()")

        url_path = "/client/v1/person/v1/personDetail"
        data = await self._request_data("GET", url_path, params={"uid": uid})
        return models.Profile.from_api(data)

    async def get_person_detail_full(
            self,
            uid: str,
            *,
            force: bool = False,
    ) -> models.Profile:
        """获取他人完整详细资料（含 VIP、IP 属地等）。

        默认优先使用 person cache；force=True 时强制从接口刷新。
        """
        if not uid:
            raise ValueError("uid is required for get_person_detail_full()")

        if not force:
            cached = self.cache.get_person_profile(uid)
            if cached is not None:
                return cached

        profile = await self.fetch_person_detail_full(uid)
        self.cache.set_person_profile(uid, profile)
        return profile

    async def get_self_detail(
            self,
            *,
            force: bool = False,
    ) -> models.Profile:
        """获取当前登录用户完整资料。

        默认优先使用 identity cache；force=True 时强制从接口刷新。
        """
        if not force:
            cached = self.cache.get_identity()
            if cached is not None:
                return cached

        return await self.fetch_self_detail()

    async def fetch_self_detail(self) -> models.Profile:
        """从接口获取当前登录用户完整资料，并更新 identity cache。"""
        uid = getattr(self._config, "person_uid", None)
        if not uid:
            raise ValueError("person_uid is required for fetch_self_detail()")

        url_path = "/client/v1/person/v2/selfDetail"
        data = await self._request_data("GET", url_path, params={"uid": uid})

        profile = models.Profile.from_api(data)
        self.cache.set_identity(profile)

        return profile

    async def get_level_info(self) -> models.UserLevelInfo:
        """获取当前用户等级、积分信息。"""
        url_path = "/user_points/v1/level_info"
        data = await self._request_data("GET", url_path)
        return models.UserLevelInfo.from_api(data)

    async def get_friendship(self) -> list[models.Friendship]:
        """获取好友信息"""
        url_path = "/client/v1/list/v1/friendship"
        data = await self._request_data("GET", url_path)
        if not isinstance(data, list):
            raise OopzApiError(f"friendship response format error: {data}")

        return [models.Friendship.from_api(d) for d in data]

    async def get_friendship_requests(self) -> list[models.FriendshipRequest]:
        """获取好友请求列表"""
        url_path = "/client/v1/friendship/v1/requests"
        data = await self._request_data("GET", url_path)
        if not isinstance(data, dict):
            raise OopzApiError(f"friendship request response format error: {data}")

        requests = data.get("requests")
        if not isinstance(requests, list):
            raise OopzApiError(f"friendship request response format error: {data}")

        return [models.FriendshipRequest.from_api(item) for item in requests]

    async def post_friendship_response(self, target: str, friend_request_id: int, agree: bool) -> models.OperationResult:
        """接受或拒绝好友请求"""
        # POST /client/v1/friendship/v1/respond
        url_path = "/client/v1/friendship/v1/response"
        data = await self._request_data("POST", url_path, body={
            "agree": agree,
            "friendRequestId": friend_request_id,
            "target": target,
        })
        return models.OperationResult.from_api(data)

    async def get_person_remark_name(self, uid: str) -> models.UserRemarkNamesResponse:
        """获取bot自己给别人的备注名。"""
        if not uid:
            raise ValueError("uid is required for get_person_remark_name()")

        url_path = "/person/v1/remarkName/getUserRemarkNames"
        data = await self._request_data("GET", url_path, params={"uid": uid})

        return models.UserRemarkNamesResponse.from_api(data)

    async def set_user_remark_name(self, uid: str, remark_name: str = "") -> models.OperationResult:
        """设置bot自己给别人的备注名。"""
        if not uid:
            raise ValueError("uid is required for set_user_remark_name()")

        url_path = "/person/v1/remarkName/setUserRemarkName"
        data = await self._request_data("POST", url_path, body={"remarkUid": uid, "remarkName": remark_name})
        return models.OperationResult.from_api(data)