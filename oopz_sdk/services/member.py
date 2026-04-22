from __future__ import annotations
import logging
from typing import Any, Optional

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.member")


class Member(BaseService):
    """Member-related platform capabilities."""

    @staticmethod
    def _to_member_model(payload: dict) -> models.Member:
        return models.Member(
            uid=str(payload.get("uid") or payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("nickname") or ""),
            nickname=str(payload.get("name") or payload.get("nickname") or ""),
            avatar=str(payload.get("avatar") or payload.get("avatarUrl") or ""),
            common_id=str(payload.get("commonId") or ""),
            bio=str(payload.get("bio") or payload.get("signature") or ""),
            online=bool(payload.get("online") in (1, True)),
            payload=dict(payload),
        )

    @staticmethod
    def _to_person_detail_model(payload: dict) -> models.PersonDetail:
        return models.PersonDetail(
            uid=str(payload.get("uid") or payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("nickname") or ""),
            avatar=str(payload.get("avatar") or payload.get("avatarUrl") or ""),
            common_id=str(payload.get("commonId") or ""),
            bio=str(payload.get("bio") or payload.get("signature") or ""),
            payload=dict(payload),
        )

    @staticmethod
    def _to_self_detail_model(payload: dict) -> models.SelfDetail:
        return models.SelfDetail(
            uid=str(payload.get("uid") or payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("nickname") or ""),
            avatar=str(payload.get("avatar") or payload.get("avatarUrl") or ""),
            mobile=str(payload.get("mobile") or ""),
            payload=dict(payload),
        )

    async def get_person_infos_batch(self, uids: list[str]) -> dict[str, dict] | dict:
        """批量获取用户基本信息。"""
        if not uids:
            return {}
        url_path = "/client/v1/person/v1/personInfos"
        result_map: dict[str, dict] = {}
        batch_size = 30

        def _partial_error(
            message: str,
            *,
            status_code: int | None = None,
            retry_after: int | None = None,
        ) -> dict[str, Any]:
            error_payload: dict[str, Any] = {"error": message}
            if status_code is not None:
                error_payload["status_code"] = status_code
            if retry_after is not None:
                error_payload["retry_after"] = retry_after
            if result_map:
                error_payload["partial_results"] = dict(result_map)
            return error_payload

        for i in range(0, len(uids), batch_size):
            batch = uids[i : i + batch_size]
            body = {"persons": batch, "commonIds": []}
            try:
                resp = await self._post(url_path, body)
                if resp.status_code != 200:
                    logger.error("批量获取用户信息失败: HTTP %d", resp.status_code)
                    if resp.status_code == 429:
                        return _partial_error(
                            "批量获取用户信息失败: HTTP 429",
                            status_code=429,
                            retry_after=self._retry_after_seconds(resp),
                        )
                    return _partial_error(f"批量获取用户信息失败: HTTP {resp.status_code}")
                data = resp.json()
                if not data.get("status"):
                    msg = self._error_message(data)
                    logger.error("批量获取用户信息失败: %s", msg)
                    return _partial_error(f"批量获取用户信息失败: {msg}")
                persons = data.get("data", [])
                if not isinstance(persons, list):
                    logger.error("批量获取用户信息失败: 响应格式异常")
                    return _partial_error("批量获取用户信息失败: person infos响应格式异常")
                for person in persons:
                    if not isinstance(person, dict):
                        logger.error("批量获取用户信息失败: 用户条目格式异常")
                        return _partial_error("批量获取用户信息失败: person infos响应格式异常")
                    uid = person.get("uid", "")
                    if uid:
                        result_map[uid] = person
            except Exception as e:
                logger.error("批量获取用户信息异常: %s", e)
                return _partial_error(f"批量获取用户信息失败: {e}")
        return result_map

    async def get_person_detail(
        self,
        uid: Optional[str] = None,
        *,
        as_model: bool = False,
    ) -> dict | models.PersonDetail:
        """获取用户信息（可查询任意用户）。"""
        uid = uid or self._config.person_uid
        url_path = "/client/v1/person/v1/personInfos"
        body = {"persons": [uid], "commonIds": []}
        request_payload = {"uid": uid}

        try:
            resp = await self._post(url_path, body)
            if resp.status_code != 200:
                logger.error("获取个人信息失败: HTTP %d", resp.status_code)
                if as_model:
                    return self._model_error(
                        models.PersonDetail,
                        f"HTTP {resp.status_code}",
                        response=resp,
                    )
                return self._error_payload(
                    f"HTTP {resp.status_code}",
                    payload={**request_payload, "error": f"HTTP {resp.status_code}"},
                )

            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                logger.error("获取个人信息失败: %s", msg)
                if as_model:
                    return self._model_error(
                        models.PersonDetail,
                        msg,
                        response=resp,
                        payload=result,
                    )
                return self._error_payload(
                    msg,
                    payload={**request_payload, **result, "error": msg},
                )

            data_list = result.get("data", [])
            if not isinstance(data_list, list):
                if as_model:
                    return self._model_error(
                        models.PersonDetail,
                        "person detail响应格式异常",
                        response=resp,
                    )
                logger.error("获取个人信息失败: 响应格式异常")
                return self._error_payload(
                    "person detail响应格式异常",
                    payload={**request_payload, "error": "person detail响应格式异常"},
                )
            if not data_list:
                if as_model:
                    return self._model_error(models.PersonDetail, "未找到该用户", response=resp)
                return self._error_payload(
                    "未找到该用户",
                    payload={**request_payload, "error": "未找到该用户"},
                )

            person = data_list[0]
            if not isinstance(person, dict):
                if as_model:
                    return self._model_error(
                        models.PersonDetail,
                        "person detail响应格式异常",
                        response=resp,
                    )
                logger.error("获取个人信息失败: 用户条目格式异常")
                return self._error_payload(
                    "person detail响应格式异常",
                    payload={**request_payload, "error": "person detail响应格式异常"},
                )
            logger.info("获取个人信息成功: %s", person.get("name", "未知"))
            if as_model:
                return self._to_person_detail_model(person)
            return person
        except Exception as e:
            logger.error("获取个人信息异常: %s", e)
            if as_model:
                return self._model_error(models.PersonDetail, str(e))
            return self._error_payload(str(e), payload={**request_payload, "error": str(e)})

    async def get_person_detail_full(self, uid: str) -> dict:
        """获取他人完整详细资料（含 VIP、IP 属地等）。"""
        url_path = "/client/v1/person/v1/personDetail"
        params = {"uid": uid}
        request_payload = {"uid": uid}
        try:
            resp = await self._get(url_path, params=params)
            if resp.status_code != 200:
                return self._error_payload(
                    f"HTTP {resp.status_code}",
                    payload={**request_payload, "error": f"HTTP {resp.status_code}"},
                )
            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                return self._error_payload(
                    msg,
                    payload={**request_payload, **result, "error": msg},
                )
            return result.get("data", {})
        except Exception as e:
            logger.error("获取他人详细资料异常: %s", e)
            return self._error_payload(str(e), payload={**request_payload, "error": str(e)})

    async def get_self_detail(self, *, as_model: bool = False) -> dict | models.SelfDetail:
        """获取当前登录用户的完整详细资料。"""
        uid = self._config.person_uid
        url_path = "/client/v1/person/v2/selfDetail"
        params = {"uid": uid}
        request_payload = {"uid": uid}
        try:
            resp = await self._get(url_path, params=params)
            if resp.status_code != 200:
                if as_model:
                    return self._model_error(
                        models.SelfDetail,
                        f"HTTP {resp.status_code}",
                        response=resp,
                    )
                return self._error_payload(
                    f"HTTP {resp.status_code}",
                    payload={**request_payload, "error": f"HTTP {resp.status_code}"},
                )
            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                if as_model:
                    return self._model_error(
                        models.SelfDetail,
                        msg,
                        response=resp,
                        payload=result,
                    )
                return self._error_payload(
                    msg,
                    payload={**request_payload, **result, "error": msg},
                )
            data = result.get("data", {})
            if as_model:
                if not isinstance(data, dict):
                    return self._model_error(
                        models.SelfDetail,
                        "self detail响应格式异常",
                        response=resp,
                    )
                return self._to_self_detail_model(data)
            return data
        except Exception as e:
            logger.error("获取自身详细资料异常: %s", e)
            if as_model:
                return self._model_error(models.SelfDetail, str(e))
            return self._error_payload(str(e), payload={**request_payload, "error": str(e)})

    async def get_level_info(self) -> dict:
        """获取当前用户等级、积分信息。"""
        url_path = "/user_points/v1/level_info"
        try:
            resp = await self._get(url_path)
            if resp.status_code != 200:
                return self._error_payload(f"HTTP {resp.status_code}")
            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                return self._error_payload(msg, payload={**result, "error": msg})
            return result.get("data", {})
        except Exception as e:
            logger.error("获取等级信息异常: %s", e)
            return self._error_payload(str(e))

    async def get_user_area_detail(self, target: str, area: Optional[str] = None) -> dict:
        """获取指定用户在域内的角色列表和禁言/禁麦状态。"""
        if not area:
            raise ValueError("缺少 area")
        url_path = "/area/v3/userDetail"
        params = {"area": area, "target": target}
        request_payload = {"area": area, "target": target}
        try:
            resp = await self._get(url_path, params=params)
            if resp.status_code != 200:
                return self._error_payload(
                    f"HTTP {resp.status_code}",
                    payload={**request_payload, "error": f"HTTP {resp.status_code}"},
                )
            result = resp.json()
            if not isinstance(result, dict):
                return self._error_payload(
                    "user area detail响应格式异常",
                    payload={**request_payload, "error": "user area detail响应格式异常"},
                )
            if not result.get("status"):
                return self._error_payload(
                    self._error_message(result),
                    payload={**request_payload, **result, "error": self._error_message(result)},
                )
            data = result.get("data", {})
            if not isinstance(data, dict):
                return self._error_payload(
                    "user area detail响应格式异常",
                    payload={**request_payload, "error": "user area detail响应格式异常"},
                )
            return data
        except Exception as e:
            logger.error("获取用户域内详情异常: %s", e)
            return self._error_payload(str(e), payload={**request_payload, "error": str(e)})

    async def get_assignable_roles(self, target: str, area: Optional[str] = None) -> list | dict:
        """获取当前用户可以分配给目标用户的角色列表。"""
        url_path = "/area/v3/role/canGiveList"
        params = {"area": area, "target": target}
        request_payload = {"area": area, "target": target}
        try:
            resp = await self._get(url_path, params=params)
            if resp.status_code != 200:
                logger.error("获取可分配角色失败: HTTP %d", resp.status_code)
                error_payload = self._error_payload(
                    f"HTTP {resp.status_code}",
                    payload={**request_payload, "error": f"HTTP {resp.status_code}"},
                )
                if resp.status_code == 429:
                    error_payload["status_code"] = 429
                    error_payload["retry_after"] = self._retry_after_seconds(resp)
                return error_payload
            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                logger.error("获取可分配角色失败: %s", msg)
                return self._error_payload(msg, payload={**request_payload, **result, "error": msg})
            data = result.get("data")
            if not isinstance(data, dict):
                logger.error("获取可分配角色失败: 响应格式异常")
                return self._error_payload(
                    "assignable roles响应格式异常",
                    payload={**request_payload, "error": "assignable roles响应格式异常"},
                )
            roles = data.get("roles", [])
            if not isinstance(roles, list):
                logger.error("获取可分配角色失败: roles格式异常")
                return self._error_payload(
                    "assignable roles响应格式异常",
                    payload={**request_payload, "roles": roles, "error": "assignable roles响应格式异常"},
                )
            invalid_payload = self._invalid_dict_item_payload(
                roles,
                "assignable roles响应格式异常",
                list_key="roles",
                payload={**request_payload, "roles": roles},
            )
            if invalid_payload:
                logger.error("获取可分配角色失败: roles条目格式异常")
                return invalid_payload
            return roles
        except Exception as e:
            logger.error("获取可分配角色异常: %s", e)
            return self._error_payload(str(e), payload={**request_payload, "error": str(e)})

    async def edit_user_role(
        self,
        target_uid: str,
        role_id: int,
        add: bool,
        area: str = None,
    ) -> dict:
        """给目标用户添加或取消指定身份组。"""
        request_payload = {"area": area, "target": target_uid, "targetRoleIDs": []}
        detail = await self.get_user_area_detail(target_uid, area=area)
        if not isinstance(detail, dict):
            return self._error_payload(
                "user area detail响应格式异常",
                payload={**request_payload, "error": "user area detail响应格式异常"},
            )
        if detail.get("error"):
            return detail
        current_list = detail.get("list")
        if current_list is None:
            current_list = []
        if not isinstance(current_list, list):
            return self._error_payload(
                "user area detail响应格式异常",
                payload={**request_payload, "error": "user area detail响应格式异常"},
            )
        if any(not isinstance(role, dict) for role in current_list):
            return self._error_payload(
                "user area detail响应格式异常",
                payload={**request_payload, "error": "user area detail响应格式异常"},
            )
        current_ids = [int(r["roleID"]) for r in current_list if r.get("roleID") is not None]
        role_id = int(role_id)
        if add:
            if role_id not in current_ids:
                current_ids.append(role_id)
        else:
            current_ids = [x for x in current_ids if x != role_id]
        url_path = "/area/v3/role/editUserRole"
        body = {"area": area, "target": target_uid, "targetRoleIDs": current_ids}
        try:
            resp = await self._post(url_path, body)
            raw = resp.text or ""
            logger.info("editUserRole POST %s add=%s -> %d, body: %s", url_path, add, resp.status_code, raw[:200])
            if resp.status_code != 200:
                message = f"HTTP {resp.status_code}" + (f" | {raw[:150]}" if raw else "")
                return self._error_payload(message, payload={**body, "error": message})
            result = resp.json()
            if result.get("status") is True:
                return {"status": True, "message": result.get("message") or ("已给身份组" if add else "已取消身份组")}
            message = result.get("message") or result.get("error") or str(result)
            return self._error_payload(
                str(message),
                payload={**body, **result, "error": str(message)},
            )
        except Exception as e:
            logger.error("editUserRole 异常: %s", e)
            return self._error_payload(str(e), payload={**body, "error": str(e)})

    async def search_area_members(
        self,
        area: Optional[str] = None,
        keyword: str = "",
        *,
        as_model: bool = False,
    ) -> list | dict:
        """搜索域内成员。"""
        url_path = "/area/v3/search/areaSettingMembers"
        body = {"area": area, "name": keyword, "offset": 0, "limit": 50}
        request_payload = dict(body)
        try:
            resp = await self._post(url_path, body)
            if resp.status_code != 200:
                logger.error("搜索域成员失败: HTTP %d", resp.status_code)
                if as_model:
                    raise OopzApiError(
                        f"HTTP {resp.status_code}",
                        status_code=resp.status_code,
                        response={"error": f"HTTP {resp.status_code}"},
                    )
                error_payload = self._error_payload(
                    f"HTTP {resp.status_code}",
                    payload={**request_payload, "error": f"HTTP {resp.status_code}"},
                )
                if resp.status_code == 429:
                    error_payload["status_code"] = 429
                    error_payload["retry_after"] = self._retry_after_seconds(resp)
                return error_payload
            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                if as_model:
                    raise OopzApiError(msg, status_code=resp.status_code, response={"error": msg})
                return self._error_payload(
                    msg,
                    payload={**request_payload, **result, "error": msg},
                )
            data = result.get("data", {})
            if not isinstance(data, dict):
                if as_model:
                    raise OopzApiError(
                        "search area members响应格式异常",
                        status_code=resp.status_code,
                        response={"error": "search area members响应格式异常"},
                    )
                logger.error("搜索域成员失败: 响应格式异常")
                return self._error_payload(
                    "search area members响应格式异常",
                    payload={**request_payload, "error": "search area members响应格式异常"},
                )
            members = data.get("members", [])
            if not isinstance(members, list):
                if as_model:
                    raise OopzApiError(
                        "search area members响应格式异常",
                        status_code=resp.status_code,
                        response={"error": "search area members响应格式异常"},
                    )
                logger.error("搜索域成员失败: members格式异常")
                return self._error_payload(
                    "search area members响应格式异常",
                    payload={**request_payload, "error": "search area members响应格式异常"},
                )
            invalid_payload = self._invalid_dict_item_payload(
                members,
                "search area members响应格式异常",
                list_key="members",
                payload={**request_payload, "members": members},
            )
            if as_model:
                if invalid_payload:
                    raise OopzApiError(
                        "search area members响应格式异常",
                        status_code=resp.status_code,
                        response=invalid_payload,
                    )
                return [self._to_member_model(m) for m in members]
            if invalid_payload:
                logger.error("搜索域成员失败: members条目格式异常")
                return invalid_payload
            return members
        except OopzApiError:
            raise
        except Exception as e:
            logger.error("搜索域成员异常: %s", e)
            if as_model:
                raise OopzApiError(str(e), response={"error": str(e)})
            return self._error_payload(str(e), payload={**request_payload, "error": str(e)})
