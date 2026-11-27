from __future__ import annotations

import logging
from typing import Optional

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError

from . import BaseService, _require_int, _require_non_empty_str, _require_str

logger = logging.getLogger(__name__)

_PERSON_DETAIL_PATH = "/client/v1/person/v1/personDetail"
_SELF_DETAIL_PATH = "/client/v1/person/v2/selfDetail"


class Person(BaseService):
    """管理个人资料、当前动态和好友关系。"""

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

    async def get_person_detail_full(
            self,
            uid: str,
            *,
            force: bool = False,
    ) -> models.Profile:
        """获取他人完整详细资料（含 VIP、IP 属地等）。

        默认优先使用 person profile cache；force=True 时强制从接口刷新。
        """
        if not uid:
            raise ValueError("uid is required for get_person_detail_full()")

        uid = str(uid)

        if not force:
            cached = self.cache.get_person_profile(uid)
            if cached is not None:
                return cached

        data = await self._request_data(
            "GET",
            _PERSON_DETAIL_PATH,
            params={"uid": uid},
        )

        profile = models.Profile.from_api(data)
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

        uid = getattr(self._config, "person_uid", None)
        if not uid:
            raise ValueError("person_uid is required for get_self_detail()")

        data = await self._request_data(
            "GET",
            _SELF_DETAIL_PATH,
            params={"uid": str(uid)},
        )

        profile = models.Profile.from_api(data)
        self.cache.set_identity(profile)
        return profile

    async def get_playing_state(self, uid: str | None = None) -> models.PlayingState:
        """实时读取用户的游戏或音乐动态，省略 uid 时读取当前账号。"""
        self_uid = self._config.person_uid
        uid = _require_non_empty_str(self_uid if uid is None else uid, "uid")
        path = _SELF_DETAIL_PATH if uid == self_uid else _PERSON_DETAIL_PATH
        data = await self._request_data("GET", path, params={"uid": uid})
        return models.PlayingState.from_api(data)

    async def set_game_state(self, name: str, *, game_id: int = 0) -> models.OperationResult:
        """展示「正在玩」文案，可通过 game_id 指定官方游戏图标。"""
        name = _require_non_empty_str(name, "name")
        game_id = _require_int(game_id, "game_id", min_value=0)
        return await self._save_playing_state("GAME", playing_state=name, game_id=game_id)

    async def set_music_state(self, app: str, song: str = "") -> models.OperationResult:
        """展示「正在听」的音乐软件和歌名，歌名可留空。"""
        app = _require_non_empty_str(app, "app")
        song = _require_str(song, "song").strip()
        return await self._save_playing_state("MUSIC", music_state=app, song_state=song)

    async def clear_playing_state(self) -> models.OperationResult:
        """清空当前账号展示的动态。"""
        return await self._save_playing_state("")

    async def _save_playing_state(
        self,
        display: str,
        *,
        playing_state: str = "",
        music_state: str = "",
        song_state: str = "",
        game_id: int = 0,
    ) -> models.OperationResult:
        body: dict[str, str | int] = {
            "display": display,
            "playingState": playing_state,
            "musicState": music_state,
            "songState": song_state,
        }
        if game_id:
            body["gameId"] = game_id
        data = await self._request_data("POST", "/person/v1/playingState/save", body=body)
        result = models.OperationResult.from_api(data)
        if result.ok:
            self.cache.invalidate_identity()
            self.cache.invalidate_person_profile(self._config.person_uid)
            self.cache.invalidate_area_members_pages_for_user(self._config.person_uid)
        return result

    async def update_self_introduction(self, introduction: str) -> models.OperationResult:
        if not isinstance(introduction, str):
            raise ValueError("The introduction of update_self_introduction() needs to be of type `str`.")
        data = await self._request_data("PUT", "/client/v1/person/v1/introduction", body={
            "introduction": introduction
        })
        return models.OperationResult.from_api(data)

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
