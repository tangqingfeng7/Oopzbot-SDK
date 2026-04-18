from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzRateLimitError
from oopz_sdk.models.segment import Image, Segment, Text
from oopz_sdk.services import BaseService
from oopz_sdk.transport.http import HttpTransport
from oopz_sdk.utils.image import get_image_info
from oopz_sdk.utils.message_builder import build_segments, normalize_message_parts

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
    def _build_operation_result(
        payload: dict, *, response, message: str
    ) -> models.OperationResult:
        return models.OperationResult(
            ok=True,
            message=str(payload.get("message") or message),
            payload=payload,
            response=response,
        )

    @staticmethod
    def segments_require_attachments(segments: list[Segment]) -> bool:
        return any(isinstance(seg, Image) for seg in segments)

    def send_message(
        self,
        *texts: str | Segment,
        text: str | None = None,
        area: Optional[str] = None,
        channel: Optional[str] = None,
        auto_recall: Optional[bool] = None,
        **kwargs,
    ) -> models.MessageSendResult:
        message_parts = list(texts)
        if text is not None:
            if message_parts:
                raise TypeError(
                    "Use either positional message parts or the legacy text= argument, not both"
                )
            message_parts.append(text)

        attachments = kwargs.get("attachments", [])
        if attachments is None:
            attachments = []

        has_segment_parts = any(not isinstance(part, str) for part in message_parts)
        if has_segment_parts and attachments:
            raise ValueError(
                "Manual attachments cannot be used together with Segment-style message parts"
            )

        if has_segment_parts:
            segments = normalize_message_parts(message_parts)
            resolved_segments = self.resolve_segments(segments)
            text, attachments = build_segments(resolved_segments)
        else:
            text = "".join(str(part) for part in message_parts)

        area = self._resolve_area(area)
        channel = self._resolve_channel(channel)
        default_style = ["IMPORTANT"] if self._config.use_announcement_style else []
        target = str(kwargs.get("target", ""))
        client_message_id = self.signer.client_message_id()
        timestamp = self.signer.timestamp_us()

        body = {
            "area": area,
            "channel": channel,
            "target": target,
            "clientMessageId": client_message_id,
            "timestamp": timestamp,
            "isMentionAll": kwargs.get("isMentionAll", False),
            "mentionList": kwargs.get("mentionList", []),
            "styleTags": kwargs.get("styleTags", default_style),
            "referenceMessageId": kwargs.get("referenceMessageId", None),
            "animated": kwargs.get("animated", False),
            "displayName": kwargs.get("displayName", ""),
            "duration": kwargs.get("duration", 0),
            "text": text,
            "attachments": attachments,
        }

        url_path = "/im/session/v1/sendGimMessage"
        logger.info("send message %s%s", text[:80], "..." if len(text) > 80 else "")

        try:
            resp = self._post(url_path, body)
            logger.info("response status %d", resp.status_code)
            if resp.text:
                logger.debug("response body: %s", resp.text[:200])
            if resp.status_code != 200:
                self._raise_api_error(resp, "failed to send message")
            result = self._safe_json(resp)
            if result is None:
                raise OopzApiError(
                    "failed to send message: response is not JSON",
                    status_code=resp.status_code,
                )
            if not result.get("status") and result.get("code") not in (
                0,
                "0",
                200,
                "200",
                "success",
            ):
                self._raise_api_error(resp, "failed to send message")
            send_result = self._build_send_result(
                result,
                response=resp,
                area=area,
                channel=channel,
                target=target,
                client_message_id=client_message_id,
                timestamp=timestamp,
            )
            if auto_recall is not False and send_result.message_id:
                self._schedule_auto_recall(send_result.message_id, area, channel)
            return send_result
        except Exception as exc:
            logger.error("send failed: %s", exc)
            raise

    def send_to_default(self, text: str, **kwargs) -> models.MessageSendResult:
        return self.send_message(text, **kwargs)

    def _schedule_auto_recall(self, message_id: str, area: str, channel: str) -> None:
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
            logger.debug("scheduled auto recall in %ds for %s...", delay, message_id[:16])
        except Exception as exc:
            logger.debug("failed to schedule auto recall: %s", exc)

    def _do_auto_recall(self, message_id: str, area: str, channel: str) -> None:
        try:
            result = self.recall_message(message_id, area=area, channel=channel)
            if not result.ok:
                logger.warning(
                    "auto recall failed: %s (msgId=%s...)",
                    result.message,
                    message_id[:16],
                )
            else:
                logger.info("auto recall succeeded: %s...", message_id[:16])
        except Exception as exc:
            logger.error("auto recall exception: %s", exc)

    def send_multiple(
        self, messages: list[str], interval: float = 1.0
    ) -> list[models.OperationResult]:
        results: list[models.OperationResult] = []
        for index, message in enumerate(messages, 1):
            try:
                resp = self.send_to_default(message)
                results.append(
                    models.OperationResult(
                        ok=True,
                        message=f"sent {message}",
                        payload={"message": message, "messageId": resp.message_id},
                    )
                )
                if index < len(messages):
                    time.sleep(interval)
            except Exception as exc:
                results.append(
                    models.OperationResult(
                        ok=False,
                        message=str(exc),
                        payload={"message": message},
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
            resp = self._request("POST", url_path, body=body, params=dict(body))
        except Exception as exc:
            logger.error("recall request exception: %s", exc)
            return models.OperationResult(ok=False, message=str(exc), payload=body)

        raw_text = resp.text or ""
        logger.info(
            "recall POST %s -> HTTP %d, body: %s",
            full_path,
            resp.status_code,
            raw_text[:300],
        )

        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}" + (
                f" | {raw_text[:200]}" if raw_text else ""
            )
            logger.error("recall failed: %s", err)
            return models.OperationResult(
                ok=False,
                message=err,
                payload=body,
                response=resp,
            )

        try:
            result = resp.json()
        except Exception:
            logger.error("recall response is not JSON: %s", raw_text[:200])
            return models.OperationResult(
                ok=False,
                message=f"response is not JSON: {raw_text[:200]}",
                payload=body,
                response=resp,
            )

        if result.get("status") is True or result.get("code") in (0, "0", "success", 200):
            logger.info("recall succeeded: %s", message_id)
            return self._build_operation_result(
                result,
                response=resp,
                message="recall succeeded",
            )

        err = result.get("message") or result.get("error") or str(result)
        logger.error("recall failed: %s", err)
        return models.OperationResult(
            ok=False,
            message=str(err),
            payload=result,
            response=resp,
        )

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
                logger.error("failed to get channel messages: HTTP %d", resp.status_code)
                return []
            result = resp.json()
            if not result.get("status"):
                logger.error(
                    "failed to get channel messages: %s",
                    result.get("message") or result.get("error"),
                )
                return []
            raw_list = result.get("data", {}).get("messages", [])
            messages = []
            for message in raw_list:
                mid = message.get("messageId") or message.get("id")
                if mid is not None:
                    message = {**message, "messageId": str(mid)}
                messages.append(message)
            logger.info("loaded channel messages: %d", len(messages))
            if as_model:
                return [
                    models.Message.from_dict(message)
                    for message in messages
                    if isinstance(message, dict)
                ]
            return messages
        except Exception as exc:
            logger.error("get channel messages exception: %s", exc)
            return []

    def resolve_segments(self, segments: list[Segment]) -> list[Segment]:
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

                raise ValueError(
                    "ImageSegment is neither uploaded nor backed by a local file"
                )

            raise TypeError(f"Unsupported segment type: {type(seg)!r}")

        return resolved

    def find_message_timestamp(
        self,
        message_id: str,
        area: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Optional[str]:
        messages = self.get_channel_messages(area=area, channel=channel)
        for message in messages:
            if message.get("messageId") == message_id:
                return message.get("timestamp")
        return None

    def _upload_local_image_segment(self, seg: Image) -> Image:
        source_path = seg.source_path
        if not source_path:
            raise ValueError("Image missing file path")

        width = seg.width
        height = seg.height
        file_size = seg.file_size
        if width <= 0 or height <= 0 or file_size <= 0:
            width, height, file_size = get_image_info(source_path)

        ext = os.path.splitext(source_path)[1] or ".jpg"
        uploader = getattr(self._bot, "media", None)
        if uploader is None:
            from oopz_sdk.services.media import Media

            uploader = Media(
                self._config,
                transport=self.transport,
                signer=self.signer,
            )

        try:
            upload = uploader.upload_file(
                source_path,
                file_type="IMAGE",
                ext=ext,
            )
        except OopzApiError:
            logger.error("failed to upload image: %s", source_path)
            raise

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
