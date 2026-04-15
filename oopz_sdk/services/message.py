from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Optional

import requests

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzRateLimitError
from oopz_sdk import models
from oopz_sdk.services import BaseService
from oopz_sdk.transport.http import HttpTransport

logger = logging.getLogger("oopz_sdk.services.message")


class Message(BaseService):
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

    def recall_message(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        timestamp: Optional[str] = None,
        target: str = "",
    ) -> dict:
        """撤回指定消息（需要管理员权限）。"""
        area = area or self._config.default_area
        channel = channel or self._config.default_channel
        timestamp = timestamp or self.signer.timestamp_us()
        message_id = str(message_id).strip() if message_id is not None else ""

        url_path = "/im/session/v1/recallGim"
        query = (
            f"?area={area}&channel={channel}"
            f"&messageId={message_id}&timestamp={timestamp}&target={target}"
        )
        full_path = url_path + query

        body = {
            "area": area,
            "channel": channel,
            "messageId": message_id,
            "timestamp": timestamp,
            "target": target,
        }

        try:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            headers = {**self.session.headers, **self.signer.oopz_headers(full_path, body_str)}
            url = self._config.base_url + full_path
            resp = self.session.post(url, headers=headers, data=body_str.encode("utf-8"))
        except Exception as e:
            logger.error("撤回请求异常: %s", e)
            return {"error": str(e)}

        raw_text = resp.text or ""
        logger.info("撤回 POST %s -> HTTP %d, body: %s", full_path, resp.status_code, raw_text[:300])

        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}" + (f" | {raw_text[:200]}" if raw_text else "")
            logger.error("撤回消息失败: %s", err)
            return {"error": err}

        try:
            result = resp.json()
        except Exception:
            logger.error("撤回响应非 JSON: %s", raw_text[:200])
            return {"error": f"响应非 JSON: {raw_text[:200]}"}

        if result.get("status") is True or result.get("code") in (0, "0", "success", 200):
            logger.info("撤回消息成功: %s", message_id)
            return {"status": True, "message": "撤回成功"}

        err = result.get("message") or result.get("error") or str(result)
        logger.error("撤回消息失败: %s", err)
        return {"error": err}

    def get_channel_messages(
        self,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        size: int = 50,
        *,
        as_model: bool = False,
    ) -> list:
        """获取频道最近的消息列表。"""
        area = area or self._config.default_area
        channel = channel or self._config.default_channel
        url_path = "/im/session/v2/messageBefore"
        params = {"area": area, "channel": channel, "size": str(size)}

        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                logger.error("获取频道消息失败: HTTP %d", resp.status_code)
                return []
            result = resp.json()
            if not result.get("status"):
                logger.error("获取频道消息失败: %s", result.get("message") or result.get("error"))
                return []
            raw_list = result.get("data", {}).get("messages", [])
            messages = []
            for m in raw_list:
                mid = m.get("messageId") or m.get("id")
                if mid is not None:
                    m = {**m, "messageId": str(mid)}
                messages.append(m)
            logger.info("获取频道消息: %d 条", len(messages))
            if as_model:
                return [self._to_message_model(m) for m in messages if isinstance(m, dict)]
            return messages
        except Exception as e:
            logger.error("获取频道消息异常: %s", e)
            return []

    def find_message_timestamp(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Optional[str]:
        """从频道最近消息中查找指定 messageId 的 timestamp。"""
        messages = self.get_channel_messages(area=area, channel=channel)
        for msg in messages:
            if msg.get("messageId") == message_id:
                return msg.get("timestamp")
        return None

    # todo
    @staticmethod
    def _to_attachment_model(payload: dict) -> models.Attachment:
        return models.Attachment(
            file_key=str(payload.get("fileKey") or payload.get("file_key") or ""),
            url=str(payload.get("url") or ""),
            attachment_type=str(payload.get("attachmentType") or payload.get("attachment_type") or ""),
            display_name=str(payload.get("displayName") or payload.get("display_name") or ""),
            file_size=int(payload.get("fileSize") or payload.get("file_size") or 0),
            width=int(payload.get("width") or 0),
            height=int(payload.get("height") or 0),
            duration=int(payload.get("duration") or 0),
            animated=bool(payload.get("animated") is True),
            hash=str(payload.get("hash") or ""),
        )

    @classmethod
    def _to_message_model(cls, payload: dict) -> models.Message:
        attachments = payload.get("attachments") or []
        return models.Message(
            area=str(payload.get("area") or ""),
            channel=str(payload.get("channel") or ""),
            target=str(payload.get("target") or ""),
            text=str(payload.get("text") or payload.get("content") or ""),
            client_message_id=str(payload.get("clientMessageId") or payload.get("client_message_id") or ""),
            timestamp=str(payload.get("timestamp") or ""),
            mention_list=list(payload.get("mentionList") or payload.get("mention_list") or []),
            style_tags=list(payload.get("styleTags") or payload.get("style_tags") or []),
            attachments=[
                cls._to_attachment_model(a) for a in attachments if isinstance(a, dict)
            ],
        )
