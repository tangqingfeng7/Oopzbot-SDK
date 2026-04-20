from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional, Any

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzRateLimitError
from oopz_sdk.response import is_success_payload
from oopz_sdk.models.segment import Image, Segment, Text
from oopz_sdk.services import BaseService
from oopz_sdk.transport.http import HttpTransport
from oopz_sdk.utils.image import get_image_info
from oopz_sdk.utils.message_builder import build_segments, normalize_message_parts
from oopz_sdk.utils.payload import safe_json

logger = logging.getLogger("oopz_sdk.services.message")


class Message(BaseService):
    def __init__(
        self,
        config_or_bot,
        config: OopzConfig,
        transport: HttpTransport,
        signer: Signer,
    ):
        if config is None:
            bot = None
            config = config_or_bot
        else:
            bot = config_or_bot
        super().__init__(config, transport, signer, bot=bot)

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
            payload=payload
        )

    @staticmethod
    def _build_operation_result(
        payload: dict, *, message: str
    ) -> models.OperationResult:
        return models.OperationResult(
            ok=True,
            message=str(payload.get("message") or message),
            payload=payload
        )

    @staticmethod
    def segments_require_attachments(segments: list[Segment]) -> bool:
        return any(isinstance(seg, Image) for seg in segments)

    async def _prepare_message_content(
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
            resolved_segments = await self._resolve_segments(segments)
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


    async def _send_built_message(
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
        resp = await self._post(url_path, body)
        if resp.status_code != 200:
            self._raise_api_error(resp, "send message failed")

        result = safe_json(resp)
        if result is None:
            raise OopzApiError(
                "send message failed: response is not JSON",
                status_code=resp.status_code,
            )

        if not is_success_payload(result):
            self._raise_api_error(resp, "send message failed")

        send_result = self._build_send_result(
            result,
            area=area,
            channel=channel,
            target=target,
            client_message_id=client_message_id,
            timestamp=timestamp,
        )

        if auto_recall and send_result.message_id:
            await self._schedule_auto_recall(send_result.message_id, area, channel)

        return send_result

    async def open_private_session(self, target: str) -> models.PrivateSessionResult:
        """
        打开或创建与指定用户的私信会话。 todo 代码需要重构
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
            resp = await self._request("PATCH", url_path, body=body, params={"target": target})
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

        result = safe_json(resp)
        if result is None:
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload={"error": f"non-json response: {raw[:200]}"},
                response=resp,
            )

        if not is_success_payload(result):
            message = self._error_message(result, "打开私信会话失败")
            return models.PrivateSessionResult(
                channel="",
                target=target,
                payload=self._error_payload(
                    message,
                    payload=result,
                    default=message,
                ),
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

    async def send_message(
        self,
        *texts: str | Segment,
        area: str,
        channel: str,
        attachments: list = None,
        mention_list: list = None,
        is_mention_all: bool = False,
        style_tags: list = None,
        reference_message_id: str = None,
        auto_recall = False,
        animated: bool = False,
        display_name: str = "",
        duration: int = 0,
        version: str = "v2",
    ) -> models.MessageSendResult:
        """
        频道消息发送。
        """
        built_text, built_attachments = await self._prepare_message_content(
            *texts,
            attachments=attachments,
        )

        default_style = ["IMPORTANT"] if self._config.use_announcement_style else []
        final_style_tags = style_tags if style_tags is not None else default_style

        body, client_message_id, timestamp = self._build_message_payload(
            text=built_text,
            area=area,
            channel=channel,
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

        return await self._send_built_message(
            url_path=url_path,
            body=body,
            area=area,
            channel=channel,
            target="",
            client_message_id=client_message_id,
            timestamp=timestamp,
            auto_recall=auto_recall,
        )

    async def send_private_message(
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
            opened = await self.open_private_session(resolved_target)
            if not opened.channel:
                raise OopzApiError(
                    f"Failed to open private session for target={resolved_target[:12]}",
                    response=opened.payload,
                )
            resolved_channel = opened.channel

        built_text, built_attachments = await self._prepare_message_content(
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

        return await self._send_built_message(
            url_path=url_path,
            body=body,
            area="",
            channel=resolved_channel,
            target=resolved_target,
            client_message_id=client_message_id,
            timestamp=timestamp,
            auto_recall=False,
        )

    async def send_to_default(self, text: str, **kwargs) -> models.MessageSendResult:
        raise ValueError(
            "send_to_default 已移除默认上下文行为，请改用 send_message(..., area=..., channel=...)"
        )

    async def _schedule_auto_recall(self, message_id: str, area: str, channel: str) -> None:
        if not self._config.auto_recall_enabled:
            return
        delay = self._config.auto_recall_delay
        if delay <= 0:
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._do_auto_recall(message_id, area, channel, delay))
            logger.debug("scheduled auto recall in %ds for %s...", delay, message_id[:16])
        except Exception as exc:
            logger.debug("failed to schedule auto recall: %s", exc)
            raise RuntimeError(
                "auto recall scheduling requires a running event loop"
            ) from exc

    async def _do_auto_recall(
        self, message_id: str, area: str, channel: str, delay: int
    ) -> None:
        try:
            await asyncio.sleep(delay)
            result = await self.recall_message(message_id, area=area, channel=channel)
            if not result.ok:
                logger.warning("auto recall failed: %s (msgId=%s...)", result.message, message_id[:16])
                logger.warning(
                    "auto recall failed: %s (msgId=%s...)",
                    result.message,
                    message_id[:16],
                )
            else:
                logger.info("auto recall success: %s...", message_id[:16])
        except Exception as e:
            logger.error("auto recall exception: %s", e)

    # todo 感觉属于高级实现, 超出了sdk的范围
    async def send_multiple(
        self,
        messages: list[str],
        *,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        interval: float = 1.0,
    ) -> list[models.OperationResult]:
        resolved_area = self._resolve_area(area)
        resolved_channel = self._resolve_channel(channel)
        results: list[models.OperationResult] = []
        for index, message in enumerate(messages, 1):
            try:
                resp = await self.send_message(
                    message,
                    area=resolved_area,
                    channel=resolved_channel,
                )
                results.append(
                    models.OperationResult(
                        ok=True,
                        message=f"sent {message}",
                        payload={"message": message, "messageId": resp.message_id},
                    )
                )
                if index < len(messages):
                    await asyncio.sleep(interval)
            except Exception as exc:
                results.append(
                    models.OperationResult(
                        ok=False,
                        message=str(exc),
                        payload={"message": message},
                    )
                )
        return results

    async def recall_message(
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
            resp = await self._request("POST", url_path, body=body, params=dict(body))
        except Exception as e:
            logger.error("recall request error: %s", e)
            return models.OperationResult(ok=False, message=str(e), payload=body)

        raw_text = resp.text or ""
        logger.info("recall POST %s -> HTTP %d", url_path, resp.status_code)

        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}" + (f" | {raw_text[:200]}" if raw_text else "")
            return models.OperationResult(ok=False, message=err, payload=body)

        result = safe_json(resp)
        if result is None:
            return models.OperationResult(
                ok=False,
                message=f"响应非 JSON: {raw_text[:200]}",
                payload=body,
            )

        if is_success_payload(result):
            return self._build_operation_result(result, message="撤回成功")

        err = result.get("message") or result.get("error") or str(result)
        return models.OperationResult(ok=False, message=str(err), payload=result)

    async def recall_private_message(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        timestamp: Optional[str] = None,
        target: str = "",
    ) -> models.OperationResult:
        raise NotImplementedError("暂不支持撤回私信消息")


    async def get_channel_messages(
        self,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        size: int = 50,
        *,
        as_model: bool = False,
    ) -> list | dict:
        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        url_path = "/im/session/v2/messageBefore"
        params = {"area": area, "channel": channel, "size": str(size)}

        def _error_response(
            message: str,
            *,
            debug_reason: str,
            payload: object | None = None,
            response=None,
            preview: str = "",
        ) -> dict:
            error_payload = self._error_payload(
                message,
                payload=payload if isinstance(payload, dict) else None,
                default=message,
            )
            error_payload["debug_reason"] = debug_reason
            error_payload["area"] = area
            error_payload["channel"] = channel
            error_payload["size"] = size
            if response is not None and getattr(response, "status_code", None) is not None:
                error_payload.setdefault("status_code", response.status_code)
            if preview:
                error_payload["preview"] = preview
            if payload is not None and not isinstance(payload, dict):
                error_payload["payload"] = payload
            return error_payload

        def _raise_channel_messages_error(
            message: str,
            *,
            debug_reason: str,
            payload: object | None = None,
            response=None,
            preview: str = "",
        ) -> None:
            error_payload = _error_response(
                message,
                debug_reason=debug_reason,
                payload=payload,
                response=response,
                preview=preview,
            )
            status_code = getattr(response, "status_code", None)
            raise OopzApiError(
                str(error_payload.get("error") or message),
                status_code=status_code,
                response=error_payload,
            )

        try:
            resp = await self._get(url_path, params=params)
            if resp.status_code != 200:
                preview = (resp.text or "")[:200]
                logger.error("failed to get channel messages: HTTP %d", resp.status_code)
                error_payload = _error_response(
                    f"HTTP {resp.status_code}",
                    debug_reason="get_channel_messages_http_error",
                    response=resp,
                    preview=preview,
                )
                if as_model:
                    _raise_channel_messages_error(
                        f"HTTP {resp.status_code}",
                        debug_reason="get_channel_messages_http_error",
                        response=resp,
                        preview=preview,
                    )
                return error_payload

            try:
                result = resp.json()
            except ValueError as exc:
                preview = (resp.text or "")[:200]
                logger.error("failed to get channel messages: non-json response: %s", exc)
                if as_model:
                    _raise_channel_messages_error(
                        "channel messages响应非 JSON",
                        debug_reason="get_channel_messages_non_json",
                        response=resp,
                        preview=preview,
                    )
                return _error_response(
                    "channel messages响应非 JSON",
                    debug_reason="get_channel_messages_non_json",
                    response=resp,
                    preview=preview,
                )
            if not isinstance(result, dict):
                error_payload = {
                    "error": "channel messages响应格式异常",
                    "debug_reason": "get_channel_messages_malformed_root",
                    "area": area,
                    "channel": channel,
                    "size": size,
                    "payload": result,
                }
                if as_model:
                    raise OopzApiError(
                        "channel messages响应格式异常",
                        status_code=resp.status_code,
                        response=error_payload,
                    )
                return error_payload
            if not result.get("status"):
                message = str(
                    result.get("message") or result.get("error") or "failed to get channel messages"
                )
                logger.error(
                    "failed to get channel messages: %s",
                    message,
                )
                if as_model:
                    _raise_channel_messages_error(
                        message,
                        debug_reason="get_channel_messages_failed_status",
                        payload=result,
                        response=resp,
                    )
                return _error_response(
                    message,
                    debug_reason="get_channel_messages_failed_status",
                    payload=result,
                    response=resp,
                )

            data = result.get("data")
            if not isinstance(data, dict):
                if as_model:
                    _raise_channel_messages_error(
                        "channel messages响应格式异常",
                        debug_reason="get_channel_messages_malformed_data",
                        payload=result,
                        response=resp,
                    )
                return _error_response(
                    "channel messages响应格式异常",
                    debug_reason="get_channel_messages_malformed_data",
                    payload=result,
                    response=resp,
                )

            raw_list = data.get("messages")
            if not isinstance(raw_list, list):
                if as_model:
                    _raise_channel_messages_error(
                        "channel messages响应格式异常",
                        debug_reason="get_channel_messages_malformed_messages",
                        payload={"messages": raw_list},
                        response=resp,
                    )
                return _error_response(
                    "channel messages响应格式异常",
                    debug_reason="get_channel_messages_malformed_messages",
                    payload={"messages": raw_list},
                    response=resp,
                )

            invalid_messages_payload = self._invalid_dict_item_payload(
                raw_list,
                "channel messages响应格式异常",
                list_key="messages",
                payload={"messages": raw_list},
            )
            if invalid_messages_payload:
                if as_model:
                    _raise_channel_messages_error(
                        "channel messages响应格式异常",
                        debug_reason="get_channel_messages_invalid_item",
                        payload=invalid_messages_payload,
                        response=resp,
                    )
                return _error_response(
                    "channel messages响应格式异常",
                    debug_reason="get_channel_messages_invalid_item",
                    payload=invalid_messages_payload,
                    response=resp,
                )
            messages = []

            for m in raw_list:
                mid = m.get("messageId") or m.get("id")
                if mid is not None:
                    m = {**m, "messageId": str(mid)}
                messages.append(m)

            logger.info("get_channel_messages: %d", len(messages))
            if as_model:
                return [
                    models.Message.from_dict(message)
                    for message in messages
                    if isinstance(message, dict)
                ]
            return messages

        except OopzApiError:
            raise
        except Exception as exc:
            logger.error("get channel messages exception: %s", exc)
            error_payload = _error_response(
                str(exc),
                debug_reason="get_channel_messages_exception",
            )
            if as_model:
                raise OopzApiError(
                    str(error_payload.get("error") or exc),
                    response=error_payload,
                ) from exc
            return error_payload

    async def _upload_local_image_segment(self, seg: Image) -> Image:
        source_path = seg.source_path
        if not source_path:
            raise ValueError("Image 缺少文件路径")

        width = seg.width
        height = seg.height
        file_size = seg.file_size
        if width <= 0 or height <= 0 or file_size <= 0:
            width, height, file_size = get_image_info(source_path)

        ext = os.path.splitext(source_path)[1] or ".jpg"

        media_service = self._require_service("media")

        upload = await media_service.upload_file(
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

    async def _resolve_segments(self, segments: list[Segment]) -> list[Segment]:
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
                    resolved.append(await self._upload_local_image_segment(seg))
                    continue

                raise ValueError("ImageSegment is neither uploaded nor backed by a local file")

            raise TypeError(f"Unsupported segment type: {type(seg)!r}")

        return resolved

    async def find_message_timestamp(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Optional[str]:
        messages = await self.get_channel_messages(area=area, channel=channel)
        if isinstance(messages, dict) and messages.get("error"):
            raise OopzApiError(
                str(messages.get("error") or "failed to get channel messages"),
                response=messages,
            )
        if not isinstance(messages, list):
            error_payload = {
                "error": "channel messages响应格式异常",
                "message_id": message_id,
                "result_type": type(messages).__name__,
            }
            raise OopzApiError("channel messages响应格式异常", response=error_payload)
        for message in messages:
            if isinstance(message, dict) and message.get("messageId") == message_id:
                return message.get("timestamp")
        return None
