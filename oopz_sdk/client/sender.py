from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Optional

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.client.rest import OopzRESTClient
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzConnectionError, OopzRateLimitError

logger = logging.getLogger("oopz_sdk.client.sender")

_SUCCESS_CODES = (0, "0", 200, "200", "success")


class OopzSender(OopzRESTClient):
    """Compatibility facade that exposes the legacy oopz sender API on top of oopz_sdk."""

    def __init__(self, config: OopzConfig):
        super().__init__(config)
        self._config = config

    @property
    def session(self):
        return self.transport.session

    def _request(
        self,
        method: str,
        url_path: str,
        body: dict | None = None,
        params: dict | None = None,
    ):
        return self.transport.request(method, url_path, body=body, params=params)

    def _get(self, url_path: str, params: dict | None = None):
        return self.transport.get(url_path, params=params)

    def _post(self, url_path: str, body: dict):
        return self.transport.post(url_path, body)

    def _put(self, url_path: str, body: dict):
        return self.transport.put(url_path, body)

    def _patch(self, url_path: str, body: dict):
        return self.transport.patch(url_path, body)

    def _delete(self, url_path: str, body: dict | None = None):
        return self.transport.delete(url_path, body)

    @staticmethod
    def _safe_json(response) -> dict[str, Any] | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _error_message_from_payload(payload: dict[str, Any] | None, default_message: str) -> str:
        if not payload:
            return default_message
        for key in ("message", "error", "msg", "reason"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return default_message

    @staticmethod
    def _is_success_payload(payload: dict[str, Any]) -> bool:
        status = payload.get("status")
        code = payload.get("code")
        if status is True:
            return True
        if status is False:
            return code in _SUCCESS_CODES
        if payload.get("success") is True:
            return True
        if payload.get("success") is False:
            return False
        if code in _SUCCESS_CODES:
            return True
        return False

    def _raise_api_error(self, response, default_message: str) -> None:
        payload = self._safe_json(response)
        message = self._error_message_from_payload(payload, default_message)
        if not payload and response.text:
            message = f"{message}: {response.text[:200]}"
        if response.status_code == 429:
            retry_after = 0
            try:
                retry_after = int(response.headers.get("Retry-After", "0") or "0")
            except Exception:
                retry_after = 0
            raise OopzRateLimitError(message=message, retry_after=retry_after, response=payload)
        raise OopzApiError(message, status_code=response.status_code, response=payload)

    def _ensure_success_payload(self, response, default_message: str) -> dict[str, Any]:
        if response.status_code != 200:
            self._raise_api_error(response, default_message)
        payload = self._safe_json(response)
        if payload is None:
            raise OopzApiError(
                f"{default_message}: response is not JSON",
                status_code=response.status_code,
            )
        if not self._is_success_payload(payload):
            raise OopzApiError(
                self._error_message_from_payload(payload, default_message),
                status_code=response.status_code,
                response=payload,
            )
        return payload

    @staticmethod
    def _require_dict_data(payload: dict[str, Any], default_message: str) -> dict[str, Any]:
        data = payload.get("data", {})
        if not isinstance(data, dict):
            raise OopzApiError(default_message, status_code=200, response=payload)
        return data

    @staticmethod
    def _require_list_data(payload: dict[str, Any], default_message: str) -> list[Any]:
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise OopzApiError(default_message, status_code=200, response=payload)
        return data

    @staticmethod
    def _extract_dict_list(
        payload: dict[str, Any],
        *,
        keys: tuple[str, ...],
        default_message: str,
    ) -> list[dict[str, Any]]:
        data = payload.get("data", {})
        if isinstance(data, dict):
            for key in keys:
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        raise OopzApiError(default_message, status_code=200, response=payload)

    @staticmethod
    def _extract_json_dict_data(payload: dict[str, Any], *, default_message: str) -> dict[str, Any]:
        data = payload.get("data", {})
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except (json.JSONDecodeError, ValueError) as exc:
                raise OopzApiError(f"{default_message}: invalid JSON string") from exc
            if isinstance(parsed, dict):
                return parsed
        raise OopzApiError(default_message, status_code=200, response=payload)

    @staticmethod
    def _normalize_mention_list(value: object) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        if not isinstance(value, list):
            return normalized
        for item in value:
            if isinstance(item, dict):
                person = str(item.get("person") or item.get("uid") or "").strip()
                if not person:
                    continue
                normalized.append(
                    {
                        "person": person,
                        "isBot": bool(item.get("isBot", False)),
                        "botType": str(item.get("botType") or ""),
                        "offset": int(item.get("offset", -1)),
                    }
                )
                continue
            person = str(item or "").strip()
            if person:
                normalized.append(
                    {"person": person, "isBot": False, "botType": "", "offset": -1}
                )
        return normalized

    @staticmethod
    def _build_v2_message_content(text: str, mention_list: list[dict[str, object]]) -> str:
        if not mention_list:
            return text
        mention_prefix = "".join(f" (met){item['person']}(met)" for item in mention_list)
        return f"{mention_prefix} {text}".rstrip()

    @staticmethod
    def _build_operation_result(
        payload: dict[str, Any],
        *,
        message: str,
        response=None,
    ) -> models.OperationResult:
        return models.OperationResult(
            ok=True,
            message=str(payload.get("message") or message),
            payload=payload,
            response=response,
        )

    def send_message(self, text: str, area: Optional[str] = None, channel: Optional[str] = None, auto_recall: Optional[bool] = None, **kwargs):
        return self.messages.send_message(
            text,
            area=area,
            channel=channel,
            auto_recall=auto_recall,
            **kwargs,
        )

    def send_to_default(self, text: str, **kwargs):
        return self.messages.send_to_default(text, **kwargs)

    def send_message_v2(
        self,
        text: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        auto_recall: Optional[bool] = None,
        **kwargs,
    ) -> models.MessageSendResult:
        area = self.messages._resolve_area(area)
        channel = self.messages._resolve_channel(channel)
        target = str(kwargs.get("target", ""))
        client_message_id = self.signer.client_message_id()
        timestamp = self.signer.timestamp_us()
        mention_list = self._normalize_mention_list(kwargs.get("mentionList", []))
        content = self._build_v2_message_content(text, mention_list)
        default_style = ["IMPORTANT"] if self._config.use_announcement_style else []
        message = {
            "area": area,
            "channel": channel,
            "target": target,
            "clientMessageId": client_message_id,
            "timestamp": timestamp,
            "isMentionAll": kwargs.get("isMentionAll", False),
            "mentionList": mention_list,
            "styleTags": kwargs.get("styleTags", default_style),
            "referenceMessageId": kwargs.get("referenceMessageId"),
            "animated": kwargs.get("animated", False),
            "displayName": kwargs.get("displayName", ""),
            "duration": kwargs.get("duration", 0),
            "text": text,
            "content": content,
            "attachments": kwargs.get("attachments", []),
        }
        body = {"message": message}
        resp = self._post("/im/session/v2/sendGimMessage", body)
        payload = self._ensure_success_payload(resp, "failed to send message")
        result = self.messages._build_send_result(
            payload,
            response=resp,
            area=area,
            channel=channel,
            target=target,
            client_message_id=client_message_id,
            timestamp=timestamp,
        )
        if auto_recall is not False and result.message_id:
            self.messages._schedule_auto_recall(result.message_id, area, channel)
        return result

    def open_private_session(self, target: str):
        return self.private.open_private_session(target)

    def send_private_message(self, target: str, text: str, **kwargs):
        attachments = kwargs.get("attachments")
        style_tags = kwargs.get("styleTags")
        channel = kwargs.get("channel")
        return self.private.send_private_message(
            target,
            text,
            attachments=attachments,
            style_tags=style_tags,
            channel=channel,
        )

    def list_sessions(self, last_time: str = "") -> list[dict[str, Any]]:
        body = {"lastTime": str(last_time or "")}
        resp = self._post("/im/session/v1/sessions", body)
        payload = self._ensure_success_payload(resp, "failed to list sessions")
        return self._require_list_data(payload, "failed to list sessions")

    def get_private_messages(self, channel: str, size: int = 50, before_message_id: str = "") -> list[models.Message]:
        params = {"area": "", "channel": str(channel), "size": str(size)}
        if before_message_id:
            params["messageId"] = str(before_message_id)
        resp = self._get("/im/session/v2/messageBefore", params=params)
        payload = self._ensure_success_payload(resp, "failed to get private messages")
        data = self._require_dict_data(payload, "failed to get private messages")
        messages = data.get("messages", [])
        if not isinstance(messages, list):
            raise OopzApiError("failed to get private messages", status_code=resp.status_code, response=payload)
        return [models.Message.from_dict(item) for item in messages if isinstance(item, dict)]

    def save_read_status(self, channel: str, *, message_id: str) -> models.OperationResult:
        body = {
            "area": "",
            "status": [
                {
                    "person": self._config.person_uid,
                    "channel": str(channel),
                    "messageId": str(message_id),
                }
            ],
        }
        resp = self._post("/im/session/v1/saveReadStatus", body)
        payload = self._ensure_success_payload(resp, "failed to save read status")
        return self._build_operation_result(payload, message="已保存已读状态", response=resp)

    def get_system_message_unread_count(self) -> int:
        resp = self._get("/im/systemMessage/v1/unreadCount")
        payload = self._ensure_success_payload(resp, "failed to get unread count")
        data = self._require_dict_data(payload, "failed to get unread count")
        return int(data.get("unreadCount") or 0)

    def get_system_message_list(self, offset_time: str = "") -> list[dict[str, Any]]:
        params = {"offsetTime": str(offset_time)} if offset_time else None
        resp = self._get("/im/systemMessage/v1/messageList", params=params)
        payload = self._ensure_success_payload(resp, "failed to get system messages")
        return self._extract_dict_list(
            payload,
            keys=("list", "messages"),
            default_message="failed to get system messages",
        )

    def get_top_messages(self, area: Optional[str] = None, channel: Optional[str] = None) -> list[dict[str, Any]]:
        params = {
            "area": self.messages._resolve_area(area),
            "channel": self.messages._resolve_channel(channel),
        }
        resp = self._get("/im/session/v2/topMessages", params=params)
        payload = self._ensure_success_payload(resp, "failed to get top messages")
        return self._extract_dict_list(
            payload,
            keys=("topMessages", "messages", "list"),
            default_message="failed to get top messages",
        )

    def get_areas_unread(self, areas: list[str]) -> dict[str, Any]:
        body = {"areas": [str(area) for area in areas if str(area or "").strip()]}
        resp = self._post("/im/session/v1/areasUnread", body)
        payload = self._ensure_success_payload(resp, "failed to get area unread counts")
        return self._require_dict_data(payload, "failed to get area unread counts")

    def get_areas_mention_unread(self, areas: list[str]) -> dict[str, Any]:
        body = {"areas": [str(area) for area in areas if str(area or "").strip()]}
        resp = self._post("/im/session/v1/areasMentionUnread", body)
        payload = self._ensure_success_payload(resp, "failed to get area mention counts")
        return self._require_dict_data(payload, "failed to get area mention counts")

    def get_gim_reactions(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        resp = self._post("/im/session/v1/gimReactions", items)
        return self._ensure_success_payload(resp, "failed to get reactions")

    def get_gim_message_details(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._post("/im/session/v1/gimMessageDetails", payload)
        return self._ensure_success_payload(resp, "failed to get message details")

    def upload_file(self, file_path: str, file_type: str = "IMAGE", ext: str = ".webp"):
        return self.media.upload_file(file_path, file_type=file_type, ext=ext)

    def upload_file_from_url(self, image_url: str):
        return self.media.upload_file_from_url(image_url)

    def upload_audio_from_url(self, audio_url: str, filename: str = "music.mp3", duration_ms: int = 0):
        return self.media.upload_audio_from_url(audio_url, filename=filename, duration_ms=duration_ms)

    def upload_and_send_image(self, file_path: str, text: str = "", **kwargs):
        return self.media.send_image(file_path, text=text, **kwargs)

    def upload_and_send_private_image(self, target: str, file_path: str, text: str = ""):
        return self.media.send_private_image(target, file_path, text=text)

    def get_area_members(self, area: Optional[str] = None, offset_start: int = 0, offset_end: int = 49, quiet: bool = False):
        return self.areas.get_area_members(area=area, offset_start=offset_start, offset_end=offset_end, quiet=quiet)

    def get_area_channels(self, area: Optional[str] = None, quiet: bool = False) -> models.ChannelGroupsResult:
        return self.channels.get_area_channels(area=area, quiet=quiet, as_model=True)

    def get_channel_setting_info(self, channel: str) -> models.ChannelSetting:
        result = self.channels.get_channel_setting_info(channel, as_model=True)
        if isinstance(result, dict):
            raise OopzApiError(result.get("error") or "failed to get channel setting")
        return result

    def create_channel(self, area: Optional[str] = None, name: str = "", channel_type: str = "text", group_id: str = ""):
        return self.channels.create_channel(area=area, name=name, channel_type=channel_type, group_id=group_id)

    def update_channel(self, area: Optional[str] = None, channel_id: str = "", overrides: Optional[dict] = None, *, name: str = ""):
        return self.channels.update_channel(area=area, channel_id=channel_id, overrides=overrides, name=name)

    def create_restricted_text_channel(self, target_uid: str, area: Optional[str] = None, preferred_channel: Optional[str] = None, name: Optional[str] = None):
        return self.channels.create_restricted_text_channel(target_uid, area=area, preferred_channel=preferred_channel, name=name)

    def delete_channel(self, channel: str, area: Optional[str] = None):
        return self.channels.delete_channel(channel, area=area)

    def copy_channel(self, channel: str, *, area: Optional[str] = None, name: str = "") -> models.OperationResult:
        area_value = self.channels._resolve_area(area)
        channel_value = str(channel or "").strip()
        body = {"area": area_value, "channel": channel_value, "name": str(name or "").strip()}
        resp = self._post("/area/v1/channel/v1/copy", body)
        payload = self._ensure_success_payload(resp, "failed to copy channel")
        channel_id = self.channels._extract_channel_id(payload.get("data", {})) or self.channels._extract_channel_id(payload)
        return models.OperationResult(
            ok=True,
            message=str(payload.get("message") or "频道已复制"),
            payload={"channel": channel_id or "", "name": body["name"], "raw": payload},
            response=resp,
        )

    def get_joined_areas(self, quiet: bool = False) -> models.JoinedAreasResult:
        return self.areas.get_joined_areas(quiet=quiet, as_model=True)

    def get_area_info(self, area: Optional[str] = None) -> dict | models.Area:
        return self.areas.get_area_info(area=area, as_model=True)

    def get_person_infos_batch(self, uids: list[str]) -> dict[str, dict]:
        return self.members.get_person_infos_batch(uids)

    def get_person_detail(self, uid: Optional[str] = None) -> models.PersonDetail:
        result = self.members.get_person_detail(uid, as_model=True)
        if isinstance(result, dict):
            raise OopzApiError(result.get("error") or "failed to get person detail")
        return result

    def get_person_detail_full(self, uid: str) -> models.PersonDetail:
        result = self.members.get_person_detail_full(uid)
        if isinstance(result, dict) and "error" in result:
            raise OopzApiError(result.get("error") or "failed to get person detail")
        if isinstance(result, models.PersonDetail):
            return result
        payload = result if isinstance(result, dict) else {}
        return models.PersonDetail(
            uid=str(payload.get("uid") or payload.get("id") or ""),
            name=str(payload.get("name") or payload.get("nickname") or ""),
            avatar=str(payload.get("avatar") or payload.get("avatarUrl") or ""),
            common_id=str(payload.get("commonId") or ""),
            bio=str(payload.get("bio") or payload.get("signature") or ""),
            payload=dict(payload),
        )

    def get_self_detail(self) -> models.SelfDetail:
        result = self.members.get_self_detail(as_model=True)
        if isinstance(result, dict):
            raise OopzApiError(result.get("error") or "failed to get self detail")
        return result

    def get_level_info(self) -> dict:
        return self.members.get_level_info()

    def get_novice_guide(self) -> dict[str, Any]:
        resp = self._get("/client/v1/person/v1/noviceGuide")
        payload = self._ensure_success_payload(resp, "failed to get novice guide")
        return self._require_dict_data(payload, "failed to get novice guide")

    def get_notice_setting(self) -> dict[str, Any]:
        resp = self._get("/person/v1/userNoticeSetting/noticeSetting")
        payload = self._ensure_success_payload(resp, "failed to get notice settings")
        return self._require_dict_data(payload, "failed to get notice settings")

    def get_user_remark_names(self, uid: str) -> list[dict[str, Any]]:
        resp = self._get("/person/v1/remarkName/getUserRemarkNames", params={"uid": str(uid)})
        payload = self._ensure_success_payload(resp, "failed to get remark names")
        return self._extract_dict_list(payload, keys=("userRemarkNames", "list"), default_message="failed to get remark names")

    def check_block_status(self, target_uid: str) -> dict[str, Any]:
        resp = self._get("/person/v1/blockCheck", params={"targetUid": str(target_uid)})
        payload = self._ensure_success_payload(resp, "failed to check block status")
        return self._require_dict_data(payload, "failed to check block status")

    def get_privacy_settings(self) -> dict[str, Any]:
        resp = self._get("/client/v1/person/v1/privacy/v1/query")
        payload = self._ensure_success_payload(resp, "failed to get privacy settings")
        return self._require_dict_data(payload, "failed to get privacy settings")

    def get_notification_settings(self) -> dict[str, Any]:
        resp = self._get("/client/v1/person/v1/notification/v1/query")
        payload = self._ensure_success_payload(resp, "failed to get notification settings")
        return self._require_dict_data(payload, "failed to get notification settings")

    def get_real_name_auth_status(self) -> dict[str, Any]:
        resp = self._get("/client/v1/person/v2/realNameAuth")
        payload = self._ensure_success_payload(resp, "failed to get real-name auth status")
        return self._require_dict_data(payload, "failed to get real-name auth status")

    def get_friend_list(self) -> list[dict[str, Any]]:
        resp = self._get("/client/v1/list/v1/friendship")
        payload = self._ensure_success_payload(resp, "failed to get friend list")
        return self._extract_dict_list(payload, keys=("friends", "friendships", "items", "list"), default_message="failed to get friend list")

    def get_blocked_list(self) -> list[dict[str, Any]]:
        resp = self._get("/client/v1/list/v1/blocked")
        payload = self._ensure_success_payload(resp, "failed to get blocked list")
        return self._extract_dict_list(payload, keys=("blocked", "blocks", "items", "list"), default_message="failed to get blocked list")

    def get_friend_requests(self) -> list[dict[str, Any]]:
        resp = self._get("/client/v1/friendship/v1/requests")
        payload = self._ensure_success_payload(resp, "failed to get friend requests")
        return self._extract_dict_list(payload, keys=("requests", "items", "list"), default_message="failed to get friend requests")

    def get_diamond_remain(self) -> dict[str, Any]:
        resp = self._get("/diamond/v1/remain")
        payload = self._ensure_success_payload(resp, "failed to get diamond remain")
        return self._require_dict_data(payload, "failed to get diamond remain")

    def get_mixer_settings(self) -> dict[str, Any]:
        resp = self._get("/client/v1/settings/v1/mixer")
        payload = self._ensure_success_payload(resp, "failed to get mixer settings")
        return self._extract_json_dict_data(payload, default_message="failed to get mixer settings")

    def set_user_remark_name(self, remark_uid: str, remark_name: str) -> models.OperationResult:
        resp = self._post("/person/v1/remarkName/setUserRemarkName", {"remarkUid": str(remark_uid), "remarkName": str(remark_name or "")})
        payload = self._ensure_success_payload(resp, "failed to set remark name")
        return self._build_operation_result(payload, message="已设置备注名", response=resp)

    def send_friend_request(self, target_uid: str) -> models.OperationResult:
        resp = self._post("/friendship/v1/request", {"target": str(target_uid)})
        payload = self._ensure_success_payload(resp, "failed to send friend request")
        return self._build_operation_result(payload, message="已发送好友申请", response=resp)

    def respond_friend_request(self, target_uid: str, *, agree: bool, friend_request_id: Optional[str] = None) -> models.OperationResult:
        body: dict[str, Any] = {"target": str(target_uid), "agree": bool(agree)}
        if friend_request_id:
            body["friendRequestId"] = str(friend_request_id)
        resp = self._post("/friendship/v1/response", body)
        payload = self._ensure_success_payload(resp, "failed to respond friend request")
        message = "已同意好友申请" if agree else "已拒绝好友申请"
        return self._build_operation_result(payload, message=message, response=resp)

    def remove_friend(self, target_uid: str) -> models.OperationResult:
        resp = self._delete(f"/friendship/v1/remove?target={str(target_uid)}")
        payload = self._ensure_success_payload(resp, "failed to remove friend")
        return self._build_operation_result(payload, message="已删除好友", response=resp)

    def edit_privacy_settings(
        self,
        *,
        everyone_add: bool,
        with_friend_add: bool,
        area_member_add: bool,
        not_friend_chat: bool,
        uid: Optional[str] = None,
    ) -> models.OperationResult:
        body = {
            "areaMemberAdd": bool(area_member_add),
            "notFriendChat": bool(not_friend_chat),
            "everyoneAdd": bool(everyone_add),
            "withFriendAdd": bool(with_friend_add),
            "uid": str(uid or self._config.person_uid),
        }
        resp = self._patch("/person/v1/privacy/v1/edit", body)
        payload = self._ensure_success_payload(resp, "failed to update privacy settings")
        return self._build_operation_result(payload, message="已更新隐私设置", response=resp)

    def edit_notification_settings(self, settings: dict[str, Any], *, mobile: bool = False) -> models.OperationResult:
        path = "/person/v1/notification/v1/mobileEdit" if mobile else "/person/v1/notification/v1/edit"
        resp = self._patch(path, dict(settings))
        payload = self._ensure_success_payload(resp, "failed to update notification settings")
        return self._build_operation_result(payload, message="已更新通知设置", response=resp)

    def get_user_area_detail(self, target: str, area: Optional[str] = None) -> dict:
        return self.members.get_user_area_detail(target, area=area)

    def get_assignable_roles(self, target: str, area: Optional[str] = None) -> list:
        return self.members.get_assignable_roles(target, area=area)

    def edit_user_role(self, target_uid: str, role_id: int, add: bool, area: Optional[str] = None):
        return self.members.edit_user_role(target_uid, role_id, add, area=area)

    def search_area_members(self, area: Optional[str] = None, keyword: str = "") -> list:
        return self.members.search_area_members(area=area, keyword=keyword)

    def search_area_private_setting_members(self, *, area: Optional[str] = None, keyword: str = "", page: int = 1) -> list[dict[str, Any]]:
        params = {
            "area": self.channels._resolve_area(area),
            "keyword": str(keyword or ""),
            "page": str(max(int(page), 1)),
        }
        resp = self._get("/area/v3/search/areaPrivateSettingMembers", params=params)
        payload = self._ensure_success_payload(resp, "failed to search private-setting members")
        data = self._require_dict_data(payload, "failed to search private-setting members")
        members = data.get("members", data.get("list", []))
        if not isinstance(members, list):
            raise OopzApiError("failed to search private-setting members", status_code=resp.status_code, response=payload)
        return [member for member in members if isinstance(member, dict)]

    def get_voice_channel_members(self, area: Optional[str] = None) -> models.VoiceChannelMembersResult:
        result = self.channels.get_voice_channel_members(area=area, as_model=True)
        if isinstance(result, dict):
            raise OopzApiError(result.get("error") or "failed to get voice channel members")
        return result

    def get_voice_channel_for_user(self, user_uid: str, area: Optional[str] = None) -> Optional[str]:
        return self.channels.get_voice_channel_for_user(user_uid, area=area)

    def enter_area(self, area: Optional[str] = None, recover: bool = False) -> dict:
        return self.areas.enter_area(area=area, recover=recover)

    def enter_channel(self, channel: Optional[str] = None, area: Optional[str] = None, channel_type: str = "TEXT", from_channel: str = "", from_area: str = "", pid: str = "") -> dict:
        return self.channels.enter_channel(channel=channel, area=area, channel_type=channel_type, from_channel=from_channel, from_area=from_area, pid=pid)

    def leave_voice_channel(self, channel: str, area: Optional[str] = None, target: Optional[str] = None):
        return self.channels.leave_voice_channel(channel, area=area, target=target)

    def get_daily_speech(self) -> models.DailySpeechResult:
        resp = self._get("/general/v1/speech")
        payload = self._ensure_success_payload(resp, "failed to get daily speech")
        data = self._require_dict_data(payload, "failed to get daily speech")
        return models.DailySpeechResult(
            words=str(data.get("words") or ""),
            author=str(data.get("author") or ""),
            source=str(data.get("source") or ""),
            payload=dict(data),
            response=resp,
        )

    def get_channel_messages(self, area: Optional[str] = None, channel: Optional[str] = None, size: int = 50) -> list[models.Message]:
        return self.messages.get_channel_messages(area=area, channel=channel, size=size, as_model=True)

    def find_message_timestamp(self, message_id: str, area: Optional[str] = None, channel: Optional[str] = None) -> Optional[str]:
        return self.messages.find_message_timestamp(message_id, area=area, channel=channel)

    def mute_user(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None, duration: int = 10):
        return self.moderation.mute_user(uid, area=area, channel=channel, duration=duration)

    def unmute_user(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None):
        return self.moderation.unmute_user(uid, area=area, channel=channel)

    def mute_mic(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None, duration: int = 10):
        return self.moderation.mute_mic(uid, area=area, channel=channel, duration=duration)

    def unmute_mic(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None):
        return self.moderation.unmute_mic(uid, area=area, channel=channel)

    def remove_from_area(self, uid: str, area: Optional[str] = None):
        return self.moderation.remove_from_area(uid, area=area)

    def block_user_in_area(self, uid: str, area: Optional[str] = None):
        return self.moderation.block_user_in_area(uid, area=area)

    def get_area_blocks(self, area: Optional[str] = None, name: str = "") -> models.AreaBlocksResult:
        result = self.moderation.get_area_blocks(area=area, name=name, as_model=True)
        if isinstance(result, dict):
            raise OopzApiError(result.get("error") or "failed to get area blocks")
        return result

    def unblock_user_in_area(self, uid: str, area: Optional[str] = None):
        return self.moderation.unblock_user_in_area(uid, area=area)

    def recall_message(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        timestamp: Optional[str] = None,
        target: str = "",
    ):
        return self.messages.recall_message(message_id, area=area, channel=channel, timestamp=timestamp, target=target)

    def populate_names(self, *, set_area=None, set_channel=None) -> models.OperationResult:
        payload = self.areas.populate_names(set_area=set_area, set_channel=set_channel)
        if isinstance(payload, dict):
            return models.OperationResult(ok=True, message="名称填充完成", payload=payload)
        return payload

    def send_multiple(self, messages: list[str], interval: float = 1.0) -> list[models.MessageSendResult]:
        results: list[models.MessageSendResult] = []
        for index, message in enumerate(messages, 1):
            results.append(self.send_to_default(message))
            if index < len(messages):
                time.sleep(interval)
        return results
