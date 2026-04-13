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
from .exceptions import OopzApiError, OopzRateLimitError
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
        elif method.upper() in ("POST", "PUT"):
            sign_str = "{}"
            data = b"{}"
        else:
            sign_str = ""
            data = None
        headers = {**self.session.headers, **self.signer.oopz_headers(url_path, sign_str)}
        url = self._config.base_url + url_path
        return self.session.request(
            method,
            url,
            headers=headers,
            data=data,
            timeout=self._config.request_timeout,
        )

    def _post(self, url_path: str, body: dict) -> requests.Response:
        return self._request("POST", url_path, body)

    def _put(self, url_path: str, body: dict) -> requests.Response:
        return self._request("PUT", url_path, body)

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
        return self.session.get(
            url,
            headers=headers,
            params=params,
            timeout=self._config.request_timeout,
        )

    @staticmethod
    def _safe_json(response: requests.Response) -> dict | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    @classmethod
    def _raise_api_error(cls, response: requests.Response, default_message: str) -> None:
        payload = cls._safe_json(response)
        message = default_message
        retry_after = 0

        if response.status_code == 429:
            try:
                retry_after = int(response.headers.get("Retry-After", "0") or "0")
            except Exception:
                retry_after = 0
            if payload:
                message = str(payload.get("message") or payload.get("error") or message)
            elif response.text:
                message = f"{message}: {response.text[:200]}"
            raise OopzRateLimitError(message=message, retry_after=retry_after, response=payload)

        if payload:
            message = str(payload.get("message") or payload.get("error") or message)
        elif response.text:
            message = f"{message}: {response.text[:200]}"

        raise OopzApiError(message, status_code=response.status_code, response=payload)

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
    ) -> requests.Response:
        """发送聊天消息。

        Args:
            text:    消息文本
            area:    区域 ID（默认取配置）
            channel: 频道 ID（默认取配置）
            auto_recall: 是否自动撤回（None=按配置决定）
            **kwargs: attachments, mentionList, referenceMessageId, styleTags 等
        """
        area = area or self._config.default_area
        channel = channel or self._config.default_channel
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
            if resp.status_code != 200:
                self._raise_api_error(resp, "发送消息失败")
            result = self._safe_json(resp)
            if result is None:
                raise OopzApiError("发送消息失败: 响应非 JSON", status_code=resp.status_code)
            if not result.get("status") and result.get("code") not in (0, "0", 200, "200", "success"):
                self._raise_api_error(resp, "发送消息失败")
            if auto_recall is not False:
                self._schedule_auto_recall(resp, area, channel)
            return resp
        except Exception as e:
            logger.error("发送失败: %s", e)
            raise

    def send_to_default(self, text: str, **kwargs) -> requests.Response:
        """发送到默认频道。"""
        return self.send_message(text, **kwargs)

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

    def open_private_session(self, target: str) -> dict:
        """打开或创建与指定用户的私信会话。"""
        target = str(target or "").strip()
        if not target:
            return {"error": "缺少 target"}

        url_path = "/client/v1/chat/v1/to"
        query = f"?target={target}"
        full_path = url_path + query
        body = {"target": target}

        try:
            self._throttle()
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            headers = {**self.session.headers, **self.signer.oopz_headers(full_path, body_str)}
            url = self._config.base_url + full_path
            resp = self.session.patch(url, headers=headers, data=body_str.encode("utf-8"))
        except Exception as e:
            logger.error("打开私信会话异常: %s", e)
            return {"error": str(e)}

        raw = resp.text or ""
        logger.info("打开私信会话 PATCH %s -> HTTP %d, body: %s", full_path, resp.status_code, raw[:300])

        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")}

        try:
            result = resp.json()
        except Exception:
            return {"error": f"响应非 JSON: {raw[:200]}"}

        channel = self._extract_private_channel(result)
        if not channel:
            logger.error("打开私信会话成功但未提取到 channel，响应: %s", self._short_payload(result))
            return {
                "error": "未能从响应中提取私信 channel",
                "raw": result,
                "debug_reason": "open_session_missing_channel",
            }
        return {"status": True, "channel": channel, "raw": result}

    def send_private_message(
        self,
        target: str,
        text: str,
        *,
        attachments: Optional[list] = None,
        style_tags: Optional[list] = None,
        channel: Optional[str] = None,
    ) -> dict:
        """发送私信消息。"""
        target = str(target or "").strip()
        if not target:
            return {"error": "缺少 target"}

        if not channel:
            opened = self.open_private_session(target)
            if "error" in opened:
                return opened
            channel = opened.get("channel")

        if not channel:
            logger.error("发送私信失败：私信 channel 不可用 (target=%s)", target[:12])
            return {"error": "私信 channel 不可用", "debug_reason": "missing_channel"}

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

        try:
            self._throttle()
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            headers = {**self.session.headers, **self.signer.oopz_headers(url_path, body_str)}
            url = self._config.base_url + url_path
            resp = self.session.post(url, headers=headers, data=body_str.encode("utf-8"))
        except Exception as e:
            logger.error("发送私信异常: %s", e)
            return {"error": str(e)}

        raw = resp.text or ""
        logger.info("发送私信 POST %s -> HTTP %d, body: %s", url_path, resp.status_code, raw[:300])

        if resp.status_code != 200:
            logger.error("发送私信失败：HTTP %s，响应: %s", resp.status_code, raw[:240])
            return {
                "error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else ""),
                "channel": channel,
                "debug_reason": "send_dm_http_error",
            }

        try:
            result = resp.json()
        except Exception:
            result = {"raw": raw}

        ok, reason = self._validate_private_send_result(result)
        if not ok:
            logger.error("发送私信未获确认: %s, 响应: %s", reason, self._short_payload(result))
            return {
                "error": f"HTTP 200 但未确认发送成功: {reason}",
                "channel": channel,
                "result": result,
                "debug_reason": "send_dm_unconfirmed",
            }

        logger.info("发送私信成功: channel=%s", str(channel)[:24])
        return {"status": True, "channel": channel, "result": result}

    # ---- 自动撤回 ----

    def _schedule_auto_recall(self, resp: requests.Response, area: str, channel: str):
        if not self._config.auto_recall_enabled:
            return
        delay = self._config.auto_recall_delay
        if delay <= 0:
            return

        try:
            result = resp.json()
            data = result.get("data", {})
            msg_id = None
            if isinstance(data, dict):
                msg_id = data.get("messageId")
            if not msg_id:
                msg_id = result.get("messageId")
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
            result = self.recall_message(message_id, area=area, channel=channel)
            if "error" in result:
                logger.warning("自动撤回失败: %s (msgId=%s...)", result["error"], message_id[:16])
            else:
                logger.info("自动撤回成功: %s...", message_id[:16])
        except Exception as e:
            logger.error("自动撤回异常: %s", e)

    # ---- 批量 ----

    def send_multiple(self, messages: list[str], interval: float = 1.0) -> list[dict]:
        """批量发送消息。"""
        results = []
        for i, msg in enumerate(messages, 1):
            try:
                resp = self.send_to_default(msg)
                results.append({"message": msg, "status_code": resp.status_code, "success": resp.status_code == 200})
                if i < len(messages):
                    time.sleep(interval)
            except Exception as e:
                results.append({"message": msg, "status_code": None, "success": False, "error": str(e)})
        return results
