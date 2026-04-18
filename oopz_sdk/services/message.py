from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional, Any

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzRateLimitError
from oopz_sdk import models
from oopz_sdk.models.segment import Image, Segment, Text
from oopz_sdk.services import BaseService
from oopz_sdk.transport.http import HttpTransport
from oopz_sdk.utils.image import get_image_info
from oopz_sdk.utils.message_builder import normalize_message_parts, build_segments

logger = logging.getLogger("oopz_sdk.services.message")


class Message(BaseService):
    def __init__(
        self,
        config_or_bot,
        config: OopzConfig | None = None,
        transport: HttpTransport | None = None,
        signer: Signer | None = None,
    ):
        if config is None:
            bot = None
            config = config_or_bot
        else:
            bot = config_or_bot

        resolved_signer = signer or Signer(config)
        resolved_transport = transport or HttpTransport(config, resolved_signer)
        super().__init__(config, resolved_transport, resolved_signer, bot=bot)

    @classmethod
    def _raise_api_error(cls, response, default_message: str) -> None:
        payload = cls._safe_json(response)
        message = default_message

        if response.status_code == 429:
            try:
                retry_after = int(response.headers.get("Retry-After", "0") or "0")
            except Exception:
                retry_after = 0

            if payload:
                message = str(payload.get("message") or payload.get("error") or message)
            elif response.text:
                message = f"{message}: {response.text[:200]}"

            raise OopzRateLimitError(
                message=message,
                retry_after=retry_after,
                response=payload,
            )

        if payload:
            message = str(payload.get("message") or payload.get("error") or message)
        elif response.text:
            message = f"{message}: {response.text[:200]}"

        raise OopzApiError(message, status_code=response.status_code, response=payload)

    @staticmethod
    def _extract_message_id(payload: dict) -> str:
        data = payload.get("data", {})
        if isinstance(data, dict):
            value = data.get("messageId") or data.get("id")
            if value is not None:
                return str(value)
        value = payload.get("messageId") or payload.get("id")
        return str(value or "")

    @staticmethod
    def _extract_message_field(payload: dict, *names: str) -> str:
        data = payload.get("data", {})
        for source in (data if isinstance(data, dict) else {}, payload):
            if not isinstance(source, dict):
                continue
            for name in names:
                value = source.get(name)
                if value not in (None, ""):
                    return str(value)
        return ""

    @classmethod
    def _build_send_result(
        cls,
        payload: dict,
        *,
        response,
        area: str,
        channel: str,
        target: str,
        client_message_id: str,
        timestamp: str,
    ) -> models.MessageSendResult:
        return models.MessageSendResult(
            message_id=cls._extract_message_id(payload),
            area=area,
            channel=channel,
            target=target,
            client_message_id=client_message_id,
            timestamp=timestamp,
            payload=payload,
            response=response,
        )

    @staticmethod
    def _build_operation_result(payload: dict, *, response, message: str) -> models.OperationResult:
        return models.OperationResult(
            ok=True,
            message=str(payload.get("message") or message),
            payload=payload,
            response=response,
        )

    @staticmethod
    def segments_require_attachments(segments: list[Segment]) -> bool:
        return any(isinstance(seg, Image) for seg in segments)

    def _prepare_message_content(
        self,
        *parts: str | Segment,
        attachments: Optional[list] = None,
    ) -> tuple[str, list]:
        """
        统一处理文本 / Segment / 附件输入，输出最终 text 和 attachments。
        """
        message_parts = list(parts)
        manual_attachments = attachments or []

        has_segment_parts = any(not isinstance(part, str) for part in message_parts)
        if has_segment_parts and manual_attachments:
            raise ValueError("Manual attachments cannot be used together with Segment-style message parts")

        if has_segment_parts:
            segments = normalize_message_parts(message_parts)
            resolved_segments = self._resolve_segments(segments)
            built_text, built_attachments = build_segments(resolved_segments)
            return built_text, built_attachments

        built_text = "".join(str(part) for part in message_parts)
        return built_text, manual_attachments

    def _build_message_payload(
        self,
        *,
        text:str,
        area: str,
        channel: str,
        target: str,
        attachments: Optional[list] = None,
        mention_list: Optional[list] = None,
        is_mention_all: bool = False,
        style_tags: Optional[list] = None,
        reference_message_id: Optional[str] = None,
        animated: bool = False,
        display_name: str = "",
        duration: int = 0,
        version: str = "v2",
    ) -> tuple[dict[str, Any], str, str]:
        client_message_id = self.signer.client_message_id()
        timestamp = self.signer.timestamp_us()

        message_payload: dict[str, Any] = {
            "area": area,
            "channel": channel,
            "target": target,
            "text":text,
            "content":text,
            "clientMessageId": client_message_id,
            "timestamp": timestamp,
            "isMentionAll": is_mention_all,
            "mentionList": mention_list or [],
            "styleTags": style_tags or [],
            "referenceMessageId": reference_message_id,
            "animated": animated,
            "displayName": display_name,
            "duration": duration,
            "attachments": attachments or [],
        }

        if version == "v2":
            return {"message": message_payload}, client_message_id, timestamp
        if version == "v1":
            return message_payload, client_message_id, timestamp
        raise ValueError(f"Unsupported message body version: {version}")


    def _send_built_message(
        self,
        *,
        url_path: str,
        body: dict[str, Any],
        area: str,
        channel: str,
        target: str,
        client_message_id: str,
        timestamp: str,
        auto_recall: bool = False,
    ) -> models.MessageSendResult:
        logger.info(
            "send request path=%s channel=%s target=%s",
            url_path,
            channel[:24],
            target[:12],
        )

        resp = self._post(url_path, body)
        logger.info("response status: %d", resp.status_code)

        if resp.text:
            logger.debug("response body: %s", resp.text[:200])

        if resp.status_code != 200:
            self._raise_api_error(resp, "send message failed")

        result = self._safe_json(resp)
        if result is None:
            raise OopzApiError(
                "send message failed: response is not JSON",
                status_code=resp.status_code,
            )

        if not result.get("status") and result.get("code") not in (0, "0", 200, "200", "success"):
            self._raise_api_error(resp, "send message failed")

        send_result = self._build_send_result(
            result,
            response=resp,
            area=area,
            channel=channel,
            target=target,
            client_message_id=client_message_id,
            timestamp=timestamp,
        )

        if auto_recall and send_result.message_id:
            self._schedule_auto_recall(send_result.message_id, area, channel)

        return send_result

    def open_private_session(self, target: str) -> models.PrivateSessionResult:
        """
        打开或创建与指定用户的私信会话。
        """
        target = str(target or "").strip()
        if not target:
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={"error": "missing target"},
            )

        url_path = "/client/v1/chat/v1/to"
        body = {"target": target}

        try:
            resp = self._request("PATCH", url_path, body=body, params={"target": target})
        except Exception as e:
            logger.error("open_private_session failed: %s", e)
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={"error": str(e)},
            )

        raw = resp.text or ""
        logger.info("open private session PATCH %s -> HTTP %d", url_path, resp.status_code)

        if resp.status_code != 200:
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={"error": f"HTTP {resp.status_code} | {raw[:200]}"},
                response=resp,
            )

        result = self._safe_json(resp)
        if result is None:
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={"error": f"non-json response: {raw[:200]}"},
                response=resp,
            )

        channel = self._extract_message_field(
            result,
            "channel",
            "chatChannel",
            "sessionChannel",
            "channelId",
            "chatChannelId",
            "sessionId",
            "imChannel",
            "conversationId",
            "id",
        )

        if not channel:
            data = result.get("data", {})
            if isinstance(data, dict):
                channel = (
                    str(data.get("channel") or "")
                    or str(data.get("channelId") or "")
                    or str(data.get("sessionId") or "")
                    or str(data.get("conversationId") or "")
                )

        if not channel:
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={"error": "cannot extract private channel", "raw": result},
                response=resp,
            )

        return models.PrivateSessionResult(
            channel=channel,
            target=target,
            payload=result,
            response=resp,
        )

    def send_message(
        self,
        *texts: str | Segment,
        area: str = "",
        channel: str = "",
        attachments: Optional[list] = None,
        mention_list: Optional[list] = None,
        is_mention_all: bool = False,
        style_tags: Optional[list] = None,
        reference_message_id: Optional[str] = None,
        auto_recall: Optional[bool] = None,
        animated: bool = False,
        display_name: str = "",
        duration: int = 0,
        version: str = "v2",
    ) -> models.MessageSendResult:
        """
        频道消息发送。
        """
        built_text, built_attachments = self._prepare_message_content(
            *texts,
            attachments=attachments,
        )

        resolved_area = self._resolve_area(area)
        resolved_channel = self._resolve_channel(channel)

        default_style = ["IMPORTANT"] if self._config.use_announcement_style else []
        final_style_tags = style_tags if style_tags is not None else default_style

        body, client_message_id, timestamp = self._build_message_payload(
            text=built_text,
            area=resolved_area,
            channel=resolved_channel,
            target="",
            attachments=built_attachments,
            mention_list=mention_list,
            is_mention_all=is_mention_all,
            style_tags=final_style_tags,
            reference_message_id=reference_message_id,
            animated=animated,
            display_name=display_name,
            duration=duration,
            version=version
        )

        url_path = "/im/session/v2/sendGimMessage" if version == "v2" else "/im/session/v1/sendGimMessage"

        logger.info(
            "send_message channel=%s text=%s",
            resolved_channel[:24],
            built_text[:80] + ("..." if len(built_text) > 80 else ""),
        )

        return self._send_built_message(
            url_path=url_path,
            body=body,
            area=resolved_area,
            channel=resolved_channel,
            target="",
            client_message_id=client_message_id,
            timestamp=timestamp,
            auto_recall=(auto_recall is not False),
        )

    def send_private_message(
        self,
        *texts: str | Segment,
        target: str,
        channel: Optional[str] = None,
        attachments: Optional[list] = None,
        mention_list: Optional[list] = None,
        is_mention_all: bool = False,
        style_tags: Optional[list] = None,
        reference_message_id: Optional[str] = None,
        animated: bool = False,
        display_name: str = "",
        duration: int = 0,
        version: str = "v2",
    ) -> models.MessageSendResult:
        """
        私信发送：
        - 负责打开/创建私信会话
        - 然后发送到 /im/session/v2/sendImMessage
        """
        resolved_target = str(target or "").strip()
        if not resolved_target:
            raise ValueError("send_private_message requires target")

        resolved_channel = str(channel or "").strip()
        if not resolved_channel:
            opened = self.open_private_session(resolved_target)
            if not opened.channel:
                raise OopzApiError(
                    f"Failed to open private session for target={resolved_target[:12]}",
                    response=opened.payload,
                )
            resolved_channel = opened.channel

        built_text, built_attachments = self._prepare_message_content(
            *texts,
            attachments=attachments,
        )

        body, client_message_id, timestamp = self._build_message_payload(
            area="",
            text=built_text,
            channel=resolved_channel,
            target=resolved_target,
            attachments=built_attachments,
            mention_list=mention_list,
            is_mention_all=is_mention_all,
            style_tags=style_tags or [],
            reference_message_id=reference_message_id,
            animated=animated,
            display_name=display_name,
            duration=duration,
        )

        url_path = "/im/session/v2/sendImMessage" if version == "v2" else "/im/session/v1/sendImMessage"

        logger.info(
            "send_private_message channel=%s target=%s text=%s",
            resolved_channel[:24],
            resolved_target[:12],
            built_text[:80] + ("..." if len(built_text) > 80 else ""),
        )

        return self._send_built_message(
            url_path=url_path,
            body=body,
            area="",
            channel=resolved_channel,
            target=resolved_target,
            client_message_id=client_message_id,
            timestamp=timestamp,
            auto_recall=False,
        )

    def send_to_default(self, text: str, **kwargs) -> models.MessageSendResult:
        """发送到默认频道。"""
        return self.send_message(text, **kwargs)

    def _schedule_auto_recall(self, message_id: str, area: str, channel: str):
        if not self._config.auto_recall_enabled:
            return
        delay = self._config.auto_recall_delay
        if delay <= 0:
            return

        try:
            timer = threading.Timer(
                delay,
                self._do_auto_recall,
                args=[message_id, area, channel],
            )
            timer.daemon = True
            timer.start()
            logger.debug("scheduled auto recall in %ds: %s...", delay, message_id[:16])
        except Exception as e:
            logger.debug("schedule auto recall failed: %s", e)

    def _do_auto_recall(self, message_id: str, area: str, channel: str):
        try:
            result = self.recall_message(message_id, area=area, channel=channel)
            if not result.ok:
                logger.warning("auto recall failed: %s (msgId=%s...)", result.message, message_id[:16])
            else:
                logger.info("auto recall success: %s...", message_id[:16])
        except Exception as e:
            logger.error("auto recall exception: %s", e)

    # todo 感觉属于高级实现, 超出了sdk的范围
    def send_multiple(self, messages: list[str], interval: float = 1.0) -> list[models.OperationResult]:
        results: list[models.OperationResult] = []
        for i, msg in enumerate(messages, 1):
            try:
                resp = self.send_to_default(msg)
                results.append(
                    models.OperationResult(
                        ok=True,
                        message=f"已发送: {msg}",
                        payload={"message": msg, "messageId": resp.message_id},
                    )
                )
                if i < len(messages):
                    time.sleep(interval)
            except Exception as e:
                results.append(
                    models.OperationResult(
                        ok=False,
                        message=str(e),
                        payload={"message": msg},
                    )
                )
        return results

    def recall_message(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        timestamp: Optional[str] = None,
        target: str = "",
    ) -> models.OperationResult:
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        timestamp = timestamp or self.signer.timestamp_us()
        message_id = str(message_id).strip() if message_id is not None else ""

        url_path = "/im/session/v1/recallGim"
        body = {
            "area": area,
            "channel": channel,
            "messageId": message_id,
            "timestamp": timestamp,
            "target": target,
        }

        try:
            resp = self._request("POST", url_path, body=body, params=dict(body))
        except Exception as e:
            logger.error("recall request error: %s", e)
            return models.OperationResult(ok=False, message=str(e), payload=body)

        raw_text = resp.text or ""
        logger.info("recall POST %s -> HTTP %d", url_path, resp.status_code)

        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}" + (f" | {raw_text[:200]}" if raw_text else "")
            return models.OperationResult(ok=False, message=err, payload=body, response=resp)

        result = self._safe_json(resp)
        if result is None:
            return models.OperationResult(
                ok=False,
                message=f"响应非 JSON: {raw_text[:200]}",
                payload=body,
                response=resp,
            )

        if result.get("status") is True or result.get("code") in (0, "0", "success", 200):
            return self._build_operation_result(result, response=resp, message="撤回成功")

        err = result.get("message") or result.get("error") or str(result)
        return models.OperationResult(ok=False, message=str(err), payload=result, response=resp)

    def recall_private_message(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        timestamp: Optional[str] = None,
        target: str = "",
    ) -> models.OperationResult:
        raise NotImplemented
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        timestamp = timestamp or self.signer.timestamp_us()
        message_id = str(message_id).strip() if message_id is not None else ""
        url_path = "/im/session/v1/recallIm" # 根据group recall猜测的接口, 没实现
        body = {
            "area": area,
            "channel": channel,
            "messageId": message_id,
            "timestamp": timestamp,
            "target": target,
        }

        try:
            resp = self._request("POST", url_path, body=body, params=dict(body))
        except Exception as e:
            logger.error("recall request error: %s", e)
            return models.OperationResult(ok=False, message=str(e), payload=body)

        raw_text = resp.text or ""
        logger.info("recall POST %s -> HTTP %d", url_path, resp.status_code)

        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}" + (f" | {raw_text[:200]}" if raw_text else "")
            return models.OperationResult(ok=False, message=err, payload=body, response=resp)

        result = self._safe_json(resp)
        if result is None:
            return models.OperationResult(
                ok=False,
                message=f"响应非 JSON: {raw_text[:200]}",
                payload=body,
                response=resp,
            )

        if result.get("status") is True or result.get("code") in (0, "0", "success", 200):
            return self._build_operation_result(result, response=resp, message="撤回成功")

        err = result.get("message") or result.get("error") or str(result)
        return models.OperationResult(ok=False, message=str(err), payload=result, response=resp)


    def get_channel_messages(
        self,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        size: int = 50,
        *,
        as_model: bool = False,
    ) -> list:
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        url_path = "/im/session/v2/messageBefore"
        params = {"area": area, "channel": channel, "size": str(size)}

        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                logger.error("get_channel_messages failed: HTTP %d", resp.status_code)
                return []

            result = self._safe_json(resp)
            if result is None or not result.get("status"):
                logger.error("get_channel_messages failed: %s", (result or {}).get("message"))
                return []

            raw_list = result.get("data", {}).get("messages", [])
            messages = []

            for m in raw_list:
                if not isinstance(m, dict):
                    continue
                mid = m.get("messageId") or m.get("id")
                if mid is not None:
                    m = {**m, "messageId": str(mid)}
                messages.append(m)

            logger.info("get_channel_messages: %d", len(messages))
            if as_model:
                return [models.Message.from_dict(m) for m in messages]
            return messages

        except Exception as e:
            logger.error("get_channel_messages exception: %s", e)
            return []

    def _upload_local_image_segment(self, seg: Image) -> Image:
        source_path = seg.source_path
        if not source_path:
            raise ValueError("Image 缺少文件路径")

        width = seg.width
        height = seg.height
        file_size = seg.file_size
        if width <= 0 or height <= 0 or file_size <= 0:
            width, height, file_size = get_image_info(source_path)

        ext = os.path.splitext(source_path)[1] or ".jpg"

        upload = self._bot.media.upload_file(
            source_path,
            file_type="IMAGE",
            ext=ext,
        )

        attachment = upload.attachment

        return Image.from_uploaded(
            file_key=attachment.file_key,
            url=attachment.url,
            width=width,
            height=height,
            file_size=file_size,
            hash=attachment.hash,
            animated=attachment.animated,
            display_name=attachment.display_name,
            preview_file_key=getattr(attachment, "preview_file_key", ""),
        )

    def _resolve_segments(self, segments: list[Segment]) -> list[Segment]:
        resolved: list[Segment] = []

        for seg in segments:
            if isinstance(seg, Text):
                resolved.append(seg)
                continue

            if isinstance(seg, Image):
                if seg.is_uploaded:
                    resolved.append(seg)
                    continue

                if seg.has_local_file:
                    resolved.append(self._upload_local_image_segment(seg))
                    continue

                raise ValueError("ImageSegment is neither uploaded nor backed by a local file")

            raise TypeError(f"Unsupported segment type: {type(seg)!r}")

        return resolved

    def find_message_timestamp(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Optional[str]:
        messages = self.get_channel_messages(area=area, channel=channel)
        for msg in messages:
            if isinstance(msg, dict) and msg.get("messageId") == message_id:
                return msg.get("timestamp")
        return None