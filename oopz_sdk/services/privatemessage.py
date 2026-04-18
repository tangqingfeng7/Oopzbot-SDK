from __future__ import annotations

import json
import logging
import re
from typing import Optional

from oopz_sdk import models

from .message import Message

logger = logging.getLogger("oopz_sdk.services.private")


class PrivateMessage(Message):
    """Private chat capabilities."""

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
                if PrivateMessage._looks_like_private_channel(value):
                    return value.strip()
            for key in (
                "data", "result", "session", "chat", "conversation",
                "conversationInfo", "chatInfo", "currentSession", "imSession",
            ):
                nested = payload.get(key)
                found = PrivateMessage._extract_private_channel(nested)
                if found:
                    return found
            sessions = payload.get("sessions") or payload.get("list")
            if isinstance(sessions, list):
                for item in sessions:
                    found = PrivateMessage._extract_private_channel(item)
                    if found:
                        return found
            found = PrivateMessage._find_private_channel_candidate(payload)
            if found:
                return found
        elif isinstance(payload, list):
            for item in payload:
                found = PrivateMessage._extract_private_channel(item)
                if found:
                    return found
        return None

    @staticmethod
    def _extract_channel_id(payload: object) -> Optional[str]:
        return PrivateMessage._extract_private_channel(payload)

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

    async def open_private_session(self, target: str) -> models.PrivateSessionResult:
        """打开或创建与指定用户的私信会话。"""
        target = str(target or "").strip()
        if not target:
            return models.PrivateSessionResult(channel="", target=target, payload={"error": "缺少 target"})

        url_path = "/client/v1/chat/v1/to"
        query = f"?target={target}"
        full_path = url_path + query
        body = {"target": target}

        try:
            resp = await self._await_if_needed(
                self._request("PATCH", url_path, body=body, params={"target": target})
            )
        except Exception as e:
            logger.error("打开私信会话异常: %s", e)
            return models.PrivateSessionResult(channel="", target=target, payload={"error": str(e)})

        raw = resp.text or ""
        logger.info("打开私信会话 PATCH %s -> HTTP %d, body: %s", full_path, resp.status_code, raw[:300])

        if resp.status_code != 200:
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={"error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")},
                response=resp,
            )

        try:
            result = resp.json()
        except Exception:
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={"error": f"响应非 JSON: {raw[:200]}"},
                response=resp,
            )

        channel = self._extract_private_channel(result)
        if not channel:
            logger.error("打开私信会话成功但未提取到 channel，响应: %s", self._short_payload(result))
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={
                    "error": "未能从响应中提取私信 channel",
                    "raw": result,
                    "debug_reason": "open_session_missing_channel",
                },
                response=resp,
            )
        return models.PrivateSessionResult(channel=channel, target=target, payload=result, response=resp)

    async def send_private_message(
        self,
        target: str,
        text: str,
        *,
        attachments: Optional[list] = None,
        style_tags: Optional[list] = None,
        channel: Optional[str] = None,
    ) -> models.MessageSendResult:
        """发送私信消息。"""
        target = str(target or "").strip()
        if not target:
            return models.MessageSendResult(
                message_id="",
                area="",
                channel=str(channel or ""),
                target=target,
                payload={"error": "缺少 target"},
            )

        if not channel:
            opened = await self.open_private_session(target)
            if not opened.channel:
                return models.MessageSendResult(
                    message_id="",
                    area="",
                    channel="",
                    target=target,
                    payload=opened.payload,
                    response=opened.response,
                )
            channel = opened.channel

        if not channel:
            logger.error("发送私信失败：私信 channel 不可用 (target=%s)", target[:12])
            return models.MessageSendResult(
                message_id="",
                area="",
                channel="",
                target=target,
                payload={"error": "私信 channel 不可用", "debug_reason": "missing_channel"},
            )

        client_message_id = self.signer.client_message_id()
        timestamp = self.signer.timestamp_us()
        body = {
            "message": {
                "area": "",
                "channel": channel,
                "target": target,
                "clientMessageId": client_message_id,
                "timestamp": timestamp,
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
            resp = await self._await_if_needed(self._post(url_path, body))
        except Exception as e:
            logger.error("发送私信异常: %s", e)
            return models.MessageSendResult(
                message_id="",
                area="",
                channel=channel,
                target=target,
                client_message_id=client_message_id,
                timestamp=timestamp,
                payload={"error": str(e)},
            )

        raw = resp.text or ""
        logger.info("发送私信 POST %s -> HTTP %d, body: %s", url_path, resp.status_code, raw[:300])

        if resp.status_code != 200:
            logger.error("发送私信失败：HTTP %s，响应: %s", resp.status_code, raw[:240])
            return models.MessageSendResult(
                message_id="",
                area="",
                channel=channel,
                target=target,
                client_message_id=client_message_id,
                timestamp=timestamp,
                payload={
                    "error": f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else ""),
                    "debug_reason": "send_dm_http_error",
                },
                response=resp,
            )

        try:
            result = resp.json()
        except Exception:
            result = {"raw": raw}

        ok, reason = self._validate_private_send_result(result)
        if not ok:
            logger.error("发送私信未获确认: %s, 响应: %s", reason, self._short_payload(result))
            return models.MessageSendResult(
                message_id="",
                area="",
                channel=channel,
                target=target,
                client_message_id=client_message_id,
                timestamp=timestamp,
                payload={
                    "error": f"HTTP 200 但未确认发送成功: {reason}",
                    "result": result,
                    "debug_reason": "send_dm_unconfirmed",
                },
                response=resp,
            )

        logger.info("发送私信成功: channel=%s", str(channel)[:24])
        return self._build_send_result(
            result,
            response=resp,
            area="",
            channel=channel,
            target=target,
            client_message_id=client_message_id,
            timestamp=timestamp,
        )
