from __future__ import annotations
import logging
from typing import Optional

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.member")


class Member(BaseService):
    """Member-related platform capabilities."""

    def __init__(
        self,
        config: OopzConfig,
        transport: HttpTransport | None = None,
        signer: Signer | None = None,
    ):
        resolved_signer = signer or Signer(config)
        resolved_transport = transport or HttpTransport(config, resolved_signer)
        super().__init__(config, resolved_transport, resolved_signer)

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
            try:
                resp = self._post(url_path, body)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if not data.get("status"):
                    continue
                for person in data.get("data", []):
                    uid = person.get("uid", "")
                    if uid:
                        result_map[uid] = person
            except Exception as e:
                logger.debug("批量获取用户信息部分失败: %s", e)
        return result_map

    def get_person_detail(
        self,
        uid: Optional[str] = None,
        *,
        as_model: bool = False,
    ) -> dict | models.PersonDetail:
        """获取用户信息（可查询任意用户）。"""
        uid = uid or self._config.person_uid
        url_path = "/client/v1/person/v1/personInfos"
        body = {"persons": [uid], "commonIds": []}

        try:
            resp = self._post(url_path, body)
            if resp.status_code != 200:
                logger.error("获取个人信息失败: HTTP %d", resp.status_code)
                return {"error": f"HTTP {resp.status_code}"}

            result = resp.json()
            if not result.get("status"):
                msg = result.get("message") or result.get("error") or "未知错误"
                logger.error("获取个人信息失败: %s", msg)
                return {"error": msg}

            data_list = result.get("data", [])
            if not data_list:
                return {"error": "未找到该用户"}

            person = data_list[0]
            logger.info("获取个人信息成功: %s", person.get("name", "未知"))
            if as_model:
                return self._to_person_detail_model(person)
            return person
        except Exception as e:
            logger.error("获取个人信息异常: %s", e)
            return {"error": str(e)}

    def get_person_detail_full(self, uid: str) -> dict:
        """获取他人完整详细资料（含 VIP、IP 属地等）。"""
        url_path = "/client/v1/person/v1/personDetail"
        params = {"uid": uid}
        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                return {"error": result.get("message") or "未知错误"}
            return result.get("data", {})
        except Exception as e:
            logger.error("获取他人详细资料异常: %s", e)
            return {"error": str(e)}

    def get_self_detail(self, *, as_model: bool = False) -> dict | models.SelfDetail:
        """获取当前登录用户的完整详细资料。"""
        uid = self._config.person_uid
        url_path = "/client/v1/person/v2/selfDetail"
        params = {"uid": uid}
        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                return {"error": result.get("message") or "未知错误"}
            data = result.get("data", {})
            if as_model and isinstance(data, dict):
                return self._to_self_detail_model(data)
            return data
        except Exception as e:
            logger.error("获取自身详细资料异常: %s", e)
            return {"error": str(e)}

    def get_level_info(self) -> dict:
        """获取当前用户等级、积分信息。"""
        url_path = "/user_points/v1/level_info"
        try:
            resp = self._get(url_path)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                return {"error": result.get("message") or "未知错误"}
            return result.get("data", {})
        except Exception as e:
            logger.error("获取等级信息异常: %s", e)
            return {"error": str(e)}

    def get_user_area_detail(self, target: str, area: Optional[str] = None) -> dict:
        """获取指定用户在域内的角色列表和禁言/禁麦状态。"""
        area = area or self._config.default_area
        url_path = "/area/v3/userDetail"
        params = {"area": area, "target": target}
        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            result = resp.json()
            if not result.get("status"):
                return {"error": result.get("message") or "未知错误"}
            return result.get("data", {})
        except Exception as e:
            logger.error("获取用户域内详情异常: %s", e)
            return {"error": str(e)}

    def get_assignable_roles(self, target: str, area: Optional[str] = None) -> list:
        """获取当前用户可以分配给目标用户的角色列表。"""
        area = area or self._config.default_area
        url_path = "/area/v3/role/canGiveList"
        params = {"area": area, "target": target}
        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                logger.error("获取可分配角色失败: HTTP %d", resp.status_code)
                return []
            result = resp.json()
            if not result.get("status"):
                return []
            data = result.get("data")
            if not isinstance(data, dict):
                return []
            return data.get("roles", [])
        except Exception as e:
            logger.error("获取可分配角色异常: %s", e)
            return []

    def edit_user_role(
        self,
        target_uid: str,
        role_id: int,
        add: bool,
        area: Optional[str] = None,
    ) -> dict:
        """给目标用户添加或取消指定身份组。"""
        area = area or self._config.default_area
        detail = self.get_user_area_detail(target_uid, area=area)
        if "error" in detail:
            return {"error": detail["error"]}
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
        try:
            resp = self._post(url_path, body)
            raw = resp.text or ""
            logger.info("editUserRole POST %s add=%s -> %d, body: %s", url_path, add, resp.status_code, raw[:200])
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}" + (f" | {raw[:150]}" if raw else "")}
            result = resp.json()
            if result.get("status") is True:
                return {"status": True, "message": result.get("message") or ("已给身份组" if add else "已取消身份组")}
            return {"error": result.get("message") or result.get("error") or str(result)}
        except Exception as e:
            logger.error("editUserRole 异常: %s", e)
            return {"error": str(e)}

    def search_area_members(
        self,
        area: Optional[str] = None,
        keyword: str = "",
        *,
        as_model: bool = False,
    ) -> list:
        """搜索域内成员。"""
        area = area or self._config.default_area
        url_path = "/area/v3/search/areaSettingMembers"
        body = {"area": area, "name": keyword, "offset": 0, "limit": 50}
        try:
            resp = self._post(url_path, body)
            if resp.status_code != 200:
                logger.error("搜索域成员失败: HTTP %d", resp.status_code)
                return []
            result = resp.json()
            if not result.get("status"):
                return []
            members = result.get("data", {}).get("members", [])
            if as_model:
                return [self._to_member_model(m) for m in members if isinstance(m, dict)]
            return members
        except Exception as e:
            logger.error("搜索域成员异常: %s", e)
            return []
