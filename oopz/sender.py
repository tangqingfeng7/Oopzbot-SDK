"""Oopz 消息发送器 -- 组合签名、API、上传功能。"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Optional

import requests

from .api import OopzApiMixin
from .config import OopzConfig
from .exceptions import OopzApiError
from .models import ChannelMessage, MessageSendResult, OperationResult, PrivateSessionResult
from .response import ensure_success_payload, raise_connection_error, require_dict_data, require_list_data
from .signer import Signer
from .upload import UploadMixin

logger = logging.getLogger("oopz.sender")


class OopzSender(UploadMixin, OopzApiMixin):
    """Oopz 平台消息发送、文件上传、平台 API 查询。

    Args:
        config: SDK 配置对象。
    """

    def __init__(self, config: OopzConfig):
        self._config = config
        self.signer = Signer(config)
        self.session = requests.Session()
        self.session.headers.update(config.get_headers())
        self._area_members_cache: dict[tuple[str, int, int], dict] = {}
        self._query_cache: dict[tuple[object, ...], dict[str, object]] = {}
        self._rate_lock = threading.Lock()
        self._last_request_time = 0.0

        logger.info("OopzSender 已初始化")
        logger.info("  用户: %s", config.person_uid)
        logger.info("  设备: %s", config.device_id)

    def _throttle(self) -> None:
        """阻塞直到距上次请求满足最小间隔，线程安全。"""
        interval = self._config.rate_limit_interval
        with self._rate_lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < interval:
                time.sleep(interval - elapsed)
            self._last_request_time = time.time()

    # ---- 内部 HTTP ----

    def _request(self, method: str, url_path: str, body: dict | None = None) -> requests.Response:
        self._throttle()
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            sign_str = body_str
            data = body_str.encode("utf-8")
        elif method.upper() in ("POST", "PUT", "PATCH"):
            sign_str = "{}"
            data = b"{}"
        else:
            sign_str = ""
            data = None
        headers = {**self.session.headers, **self.signer.oopz_headers(url_path, sign_str)}
        url = self._config.base_url + url_path
        try:
            return self.session.request(
                method,
                url,
                headers=headers,
                data=data,
                timeout=self._config.request_timeout,
            )
        except requests.RequestException as exc:
            raise_connection_error(exc)

    def _post(self, url_path: str, body: dict) -> requests.Response:
        return self._request("POST", url_path, body)

    def _put(self, url_path: str, body: dict) -> requests.Response:
        return self._request("PUT", url_path, body)

    def _patch(self, url_path: str, body: dict) -> requests.Response:
        return self._request("PATCH", url_path, body)

    def _delete(self, url_path: str, body: Optional[dict] = None) -> requests.Response:
        return self._request("DELETE", url_path, body)

    def _get(self, url_path: str, params: Optional[dict] = None) -> requests.Response:
        self._throttle()
        if params:
            from urllib.parse import urlencode
            sign_path = url_path + "?" + urlencode(params)
        else:
            sign_path = url_path

        headers = {**self.session.headers, **self.signer.oopz_headers(sign_path, "")}
        url = self._config.base_url + url_path
        try:
            return self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=self._config.request_timeout,
            )
        except requests.RequestException as exc:
            raise_connection_error(exc)

    def _resolve_area(self, area: Optional[str]) -> str:
        value = str(area or self._config.default_area).strip()
        if not value:
            raise ValueError("缺少 area，且未配置 default_area")
        return value

    def _resolve_channel(self, channel: Optional[str]) -> str:
        value = str(channel or self._config.default_channel).strip()
        if not value:
            raise ValueError("缺少 channel，且未配置 default_channel")
        return value

    @staticmethod
    def _extract_message_id(payload: dict[str, object]) -> str:
        data = payload.get("data", {})
        if isinstance(data, dict):
            value = data.get("messageId") or data.get("id")
            if value is not None:
                return str(value)
        value = payload.get("messageId") or payload.get("id")
        return str(value or "")

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
                normalized.append({"person": person, "isBot": False, "botType": "", "offset": -1})
        return normalized

    @staticmethod
    def _build_v2_message_content(text: str, mention_list: list[dict[str, object]]) -> str:
        if not mention_list:
            return text
        mention_prefix = "".join(f" (met){item['person']}(met)" for item in mention_list)
        return f"{mention_prefix} {text}".rstrip()

    def close(self) -> None:
        """关闭底层 HTTP Session。"""
        self.session.close()

    def __enter__(self) -> "OopzSender":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---- 发送消息 ----

    def send_message(
        self,
        text: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        auto_recall: Optional[bool] = None,
        **kwargs,
    ) -> MessageSendResult:
        """发送聊天消息。

        Args:
            text:    消息文本
            area:    区域 ID（默认取配置）
            channel: 频道 ID（默认取配置）
            auto_recall: 是否自动撤回（None=按配置决定）
            **kwargs: attachments, mentionList, referenceMessageId, styleTags 等
        """
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        default_style = ["IMPORTANT"] if self._config.use_announcement_style else []

        body = {
            "area": area,
            "channel": channel,
            "target": kwargs.get("target", ""),
            "clientMessageId": self.signer.client_message_id(),
            "timestamp": self.signer.timestamp_us(),
            "isMentionAll": kwargs.get("isMentionAll", False),
            "mentionList": kwargs.get("mentionList", []),
            "styleTags": kwargs.get("styleTags", default_style),
            "referenceMessageId": kwargs.get("referenceMessageId", None),
            "animated": kwargs.get("animated", False),
            "displayName": kwargs.get("displayName", ""),
            "duration": kwargs.get("duration", 0),
            "text": text,
            "attachments": kwargs.get("attachments", []),
        }

        url_path = "/im/session/v1/sendGimMessage"
        logger.info("发送消息: %s%s", text[:80], "..." if len(text) > 80 else "")

        try:
            resp = self._post(url_path, body)
            logger.info("响应状态: %d", resp.status_code)
            if resp.text:
                logger.debug("响应内容: %s", resp.text[:200])
            result = ensure_success_payload(resp, "发送消息失败")
            if auto_recall is not False:
                self._schedule_auto_recall(result, area, channel)
            return MessageSendResult(
                message_id=self._extract_message_id(result),
                area=area,
                channel=channel,
                target=str(body.get("target") or ""),
                client_message_id=str(body["clientMessageId"]),
                timestamp=str(body["timestamp"]),
                payload=result,
                response=resp,
            )
        except Exception as e:
            logger.error("发送失败: %s", e)
            raise

    def send_to_default(self, text: str, **kwargs) -> MessageSendResult:
        """发送到默认频道。"""
        return self.send_message(text, **kwargs)

    def send_message_v2(
        self,
        text: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        auto_recall: Optional[bool] = None,
        **kwargs,
    ) -> MessageSendResult:
        """使用 Web 端 v2 包裹格式发送频道消息。"""
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        default_style = ["IMPORTANT"] if self._config.use_announcement_style else []
        mention_list = self._normalize_mention_list(kwargs.get("mentionList", kwargs.get("mention_list", [])))
        content = str(kwargs.get("content") or self._build_v2_message_content(text, mention_list))

        message = {
            "area": area,
            "channel": channel,
            "target": kwargs.get("target", ""),
            "clientMessageId": self.signer.client_message_id(),
            "timestamp": self.signer.timestamp_us(),
            "isMentionAll": kwargs.get("isMentionAll", False),
            "mentionList": mention_list,
            "styleTags": kwargs.get("styleTags", default_style),
            "referenceMessageId": kwargs.get("referenceMessageId", None),
            "animated": kwargs.get("animated", False),
            "displayName": kwargs.get("displayName", ""),
            "duration": kwargs.get("duration", 0),
            "content": content,
            "attachments": kwargs.get("attachments", []),
        }
        body = {"message": message}
        url_path = "/im/session/v2/sendGimMessage"

        resp = self._post(url_path, body)
        result = ensure_success_payload(resp, "发送消息失败")
        if auto_recall is not False:
            self._schedule_auto_recall(result, area, channel)
        return MessageSendResult(
            message_id=self._extract_message_id(result),
            area=area,
            channel=channel,
            target=str(message.get("target") or ""),
            client_message_id=str(message["clientMessageId"]),
            timestamp=str(message["timestamp"]),
            payload=result,
            response=resp,
        )

    # ---- 私信 ----

    @staticmethod
    def _looks_like_private_channel(value: object) -> bool:
        if not isinstance(value, str):
            return False
        text = value.strip()
        if not text:
            return False
        if re.fullmatch(r"[a-f0-9]{32}", text):
            return False
        return bool(re.fullmatch(r"[0-9A-Z]{20,40}", text))

    @classmethod
    def _find_private_channel_candidate(cls, payload: object) -> Optional[str]:
        if isinstance(payload, dict):
            for value in payload.values():
                found = cls._find_private_channel_candidate(value)
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = cls._find_private_channel_candidate(item)
                if found:
                    return found
        elif cls._looks_like_private_channel(payload):
            return str(payload).strip()
        return None

    @staticmethod
    def _extract_private_channel(payload: object) -> Optional[str]:
        if isinstance(payload, dict):
            for key in (
                "channel", "chatChannel", "sessionChannel", "channelId",
                "chatChannelId", "sessionId", "imChannel", "imSessionChannel",
                "conversationId", "id",
            ):
                value = payload.get(key)
                if OopzSender._looks_like_private_channel(value):
                    return value.strip()
            for key in (
                "data", "result", "session", "chat", "conversation",
                "conversationInfo", "chatInfo", "currentSession", "imSession",
            ):
                nested = payload.get(key)
                found = OopzSender._extract_private_channel(nested)
                if found:
                    return found
            sessions = payload.get("sessions") or payload.get("list")
            if isinstance(sessions, list):
                for item in sessions:
                    found = OopzSender._extract_private_channel(item)
                    if found:
                        return found
            found = OopzSender._find_private_channel_candidate(payload)
            if found:
                return found
        elif isinstance(payload, list):
            for item in payload:
                found = OopzSender._extract_private_channel(item)
                if found:
                    return found
        return None

    @staticmethod
    def _extract_channel_id(payload: object) -> Optional[str]:
        return OopzSender._extract_private_channel(payload)

    @staticmethod
    def _short_payload(payload: object, limit: int = 240) -> str:
        try:
            text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            text = str(payload)
        return text[:limit]

    @staticmethod
    def _validate_private_send_result(result: object) -> tuple[bool, str]:
        if not isinstance(result, dict):
            return False, "响应不是 JSON 对象"

        if "status" in result:
            if result.get("status") is True:
                return True, ""
            return False, str(result.get("message") or result.get("error") or "status=false")

        if "success" in result:
            if result.get("success") is True:
                return True, ""
            return False, str(result.get("message") or result.get("msg") or result.get("error") or "success=false")

        if "code" in result:
            code = result.get("code")
            if code in (0, "0", ""):
                if any(key in result for key in ("data", "result", "messageId")):
                    return True, ""
                return False, "code=0 但无明确投递确认字段"
            return False, str(result.get("message") or result.get("msg") or result.get("error") or f"code={code}")

        if any(key in result for key in ("data", "result", "messageId")):
            return True, ""

        return False, "HTTP 200 但响应未明确确认私信已发送"

    def open_private_session(self, target: str) -> PrivateSessionResult:
        """打开或创建与指定用户的私信会话。"""
        target = str(target or "").strip()
        if not target:
            raise ValueError("target 不能为空")

        url_path = "/client/v1/chat/v1/to"
        query = f"?target={target}"
        full_path = url_path + query
        body = {"target": target}

        resp = self._patch(full_path, body)
        raw = resp.text or ""
        logger.info("打开私信会话 PATCH %s -> HTTP %d, body: %s", full_path, resp.status_code, raw[:300])
        result = ensure_success_payload(resp, "打开私信会话失败")

        channel = self._extract_private_channel(result)
        if not channel:
            raise OopzApiError("打开私信会话失败: 未能提取私信 channel", status_code=resp.status_code, response=result)
        return PrivateSessionResult(channel=channel, payload=result, response=resp)

    def send_private_message(
        self,
        target: str,
        text: str,
        *,
        attachments: Optional[list] = None,
        style_tags: Optional[list] = None,
        channel: Optional[str] = None,
    ) -> MessageSendResult:
        """发送私信消息。"""
        target = str(target or "").strip()
        if not target:
            raise ValueError("target 不能为空")

        if not channel:
            channel = self.open_private_session(target).channel

        if not channel:
            raise OopzApiError("发送私信失败: 私信 channel 不可用")

        body = {
            "message": {
                "area": "",
                "channel": channel,
                "target": target,
                "clientMessageId": self.signer.client_message_id(),
                "timestamp": self.signer.timestamp_us(),
                "isMentionAll": False,
                "mentionList": [],
                "styleTags": style_tags if style_tags is not None else [],
                "referenceMessageId": None,
                "animated": False,
                "displayName": "",
                "duration": 0,
                "content": text,
                "attachments": attachments or [],
            }
        }
        url_path = "/im/session/v2/sendImMessage"
        resp = self._post(url_path, body)

        raw = resp.text or ""
        logger.info("发送私信 POST %s -> HTTP %d, body: %s", url_path, resp.status_code, raw[:300])
        result = ensure_success_payload(resp, "发送私信失败")

        ok, reason = self._validate_private_send_result(result)
        if not ok:
            raise OopzApiError(f"发送私信失败: {reason}", status_code=resp.status_code, response=result)

        logger.info("发送私信成功: channel=%s", str(channel)[:24])
        message = body["message"]
        return MessageSendResult(
            message_id=self._extract_message_id(result),
            area="",
            channel=str(channel),
            target=target,
            client_message_id=str(message["clientMessageId"]),
            timestamp=str(message["timestamp"]),
            payload=result,
            response=resp,
        )

    def list_sessions(self, last_time: str = "") -> list[dict[str, object]]:
        """获取当前账号的会话列表。"""
        body: dict[str, object] = {}
        last_time = str(last_time or "").strip()
        if last_time:
            body["lastTime"] = last_time

        resp = self._post("/im/session/v1/sessions", body)
        result = ensure_success_payload(resp, "获取会话列表失败")
        sessions = require_list_data(result, "获取会话列表失败")
        return [item for item in sessions if isinstance(item, dict)]

    def get_private_messages(
        self,
        channel: str,
        *,
        size: int = 50,
        before_message_id: str = "",
    ) -> list[ChannelMessage]:
        """获取指定私信会话的历史消息。"""
        channel = str(channel or "").strip()
        if not channel:
            raise ValueError("channel 不能为空")

        params = {"area": "", "channel": channel, "size": str(int(size))}
        before_message_id = str(before_message_id or "").strip()
        if before_message_id:
            params["messageId"] = before_message_id

        resp = self._get("/im/session/v2/messageBefore", params=params)
        result = ensure_success_payload(resp, "获取私信历史消息失败")
        data = require_dict_data(result, "获取私信历史消息失败")
        return self._build_channel_messages_result(data, response=resp)

    def save_read_status(
        self,
        channel: str,
        *,
        message_id: str = "",
        area: str = "",
        person: Optional[str] = None,
    ) -> OperationResult:
        """保存会话已读状态，支持私信与频道会话。"""
        channel = str(channel or "").strip()
        if not channel:
            raise ValueError("channel 不能为空")

        person_uid = str(person or self._config.person_uid).strip()
        if not person_uid:
            raise ValueError("person 不能为空")

        status_item: dict[str, object] = {
            "person": person_uid,
            "channel": channel,
        }
        message_id = str(message_id or "").strip()
        if message_id:
            status_item["messageId"] = message_id

        body = {
            "area": str(area or ""),
            "status": [status_item],
        }
        resp = self._post("/im/session/v1/saveReadStatus", body)
        result = ensure_success_payload(resp, "保存已读状态失败")
        return self._build_operation_result(result, message="已保存已读状态", response=resp)

    def get_system_message_unread_count(self) -> int:
        """获取系统消息未读数。"""
        resp = self._get("/im/systemMessage/v1/unreadCount")
        result = ensure_success_payload(resp, "获取系统消息未读数失败")
        data = require_dict_data(result, "获取系统消息未读数失败")
        for key in ("count", "unreadCount", "total"):
            value = data.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        raise OopzApiError("获取系统消息未读数失败: 响应格式异常", status_code=resp.status_code, response=result)

    def get_system_message_list(self, offset_time: str = "") -> list[dict[str, object]]:
        """获取系统消息列表。"""
        params: dict[str, str] = {}
        offset_time = str(offset_time or "").strip()
        if offset_time:
            params["offsetTime"] = offset_time

        resp = self._get("/im/systemMessage/v1/messageList", params=params or None)
        result = ensure_success_payload(resp, "获取系统消息列表失败")
        data = require_dict_data(result, "获取系统消息列表失败")
        messages = data.get("messages", data.get("list", []))
        if not isinstance(messages, list):
            raise OopzApiError("获取系统消息列表失败: 响应格式异常", status_code=resp.status_code, response=result)
        return [item for item in messages if isinstance(item, dict)]

    def get_top_messages(
        self,
        *,
        area: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> list[dict[str, object]]:
        """获取频道置顶消息。"""
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        params = {"area": area, "channel": channel}
        resp = self._get("/im/session/v2/topMessages", params=params)
        result = ensure_success_payload(resp, "获取置顶消息失败")
        data = require_dict_data(result, "获取置顶消息失败")
        messages = data.get("messages", data.get("list", data.get("topMessages", [])))
        if not isinstance(messages, list):
            raise OopzApiError("获取置顶消息失败: 响应格式异常", status_code=resp.status_code, response=result)
        return [item for item in messages if isinstance(item, dict)]

    def get_areas_unread(self, areas: list[str]) -> dict[str, object]:
        """获取指定域列表的未读数。"""
        normalized = [str(area).strip() for area in areas if str(area).strip()]
        body = {"areas": normalized}
        resp = self._post("/im/session/v1/areasUnread", body)
        result = ensure_success_payload(resp, "获取区域未读数失败")
        return require_dict_data(result, "获取区域未读数失败")

    def get_areas_mention_unread(self, areas: list[str]) -> dict[str, object]:
        """获取指定域列表的 @ 未读数。"""
        normalized = [str(area).strip() for area in areas if str(area).strip()]
        body = {"areas": normalized}
        resp = self._post("/im/session/v1/areasMentionUnread", body)
        result = ensure_success_payload(resp, "获取区域 @ 未读数失败")
        return require_dict_data(result, "获取区域 @ 未读数失败")

    def get_gim_reactions(self, items: list[dict[str, object]]) -> dict[str, object]:
        """获取频道消息表情反应信息。"""
        normalized = [item for item in items if isinstance(item, dict)]
        resp = self._post("/im/session/v1/gimReactions", normalized)
        return ensure_success_payload(resp, "获取消息表情反应失败")

    def get_gim_message_details(self, payload: dict[str, object]) -> dict[str, object]:
        """获取频道消息详情。"""
        resp = self._post("/im/session/v1/gimMessageDetails", payload)
        return ensure_success_payload(resp, "获取消息详情失败")

    # ---- 自动撤回 ----

    def _schedule_auto_recall(self, payload: dict[str, object], area: str, channel: str) -> None:
        if not self._config.auto_recall_enabled:
            return
        delay = self._config.auto_recall_delay
        if delay <= 0:
            return

        try:
            data = payload.get("data", {})
            msg_id = None
            if isinstance(data, dict):
                msg_id = data.get("messageId")
            if not msg_id:
                msg_id = payload.get("messageId")
            if not msg_id:
                logger.debug("自动撤回: 无法从响应中提取 messageId，跳过")
                return
            msg_id = str(msg_id)

            timer = threading.Timer(
                delay, self._do_auto_recall, args=[msg_id, area, channel],
            )
            timer.daemon = True
            timer.start()
            logger.debug("已安排 %ds 后自动撤回: %s...", delay, msg_id[:16])
        except Exception as e:
            logger.debug("安排自动撤回失败: %s", e)

    def _do_auto_recall(self, message_id: str, area: str, channel: str):
        try:
            self.recall_message(message_id, area=area, channel=channel)
            logger.info("自动撤回成功: %s...", message_id[:16])
        except Exception as e:
            logger.error("自动撤回异常: %s", e)

    # ---- 批量 ----

    def send_multiple(self, messages: list[str], interval: float = 1.0) -> list[MessageSendResult]:
        """批量发送消息。"""
        results: list[MessageSendResult] = []
        for i, msg in enumerate(messages, 1):
            results.append(self.send_to_default(msg))
            if i < len(messages):
                time.sleep(interval)
        return results
