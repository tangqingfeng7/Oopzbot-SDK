from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional, Any, List

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.models.segment import Image, Segment, Text
from oopz_sdk.services import BaseService
from oopz_sdk.utils.image import get_image_info
from oopz_sdk.utils.message_builder import build_segments, normalize_message_parts

logger = logging.getLogger("oopz_sdk.services.message")


class Message(BaseService):
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
            text: str,
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
            "text": text,
            "content": text,
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

    async def open_private_session(self, target: str) -> models.PrivateSession:
        """
        打开或创建与指定用户的私信会话。
        """
        target = target.strip()
        if not target:
            raise ValueError("target is required for send_private_message()")

        url_path = "/client/v1/chat/v1/to"
        resp = await self._request_data("PATCH", url_path, params={"target": target})
        return models.PrivateSession.from_api(resp)

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
            auto_recall=False,
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

        resp = await self._request_data("POST", url_path, body=body)

        model = models.MessageSendResult.from_api(resp)

        if auto_recall and model.message_id:
            await self._schedule_auto_recall(model.message_id, area, channel)
        return model

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
        target = target.strip()
        if not target:
            raise ValueError("target is required for send_private_message()")

        if not channel:
            session = await self.open_private_session(target)
            if not session.session_id:
                raise OopzApiError(f"Failed to open private session for target={target}")
            channel = session.session_id
        built_text, built_attachments = await self._prepare_message_content(
            *texts,
            attachments=attachments,
        )

        body, client_message_id, timestamp = self._build_message_payload(
            area="",
            text=built_text,
            channel=channel,
            target=target,
            attachments=built_attachments,
            mention_list=mention_list,
            is_mention_all=is_mention_all,
            style_tags=style_tags or [],
            reference_message_id=reference_message_id,
            animated=animated,
            display_name=display_name,
            duration=duration,
            version=version,
        )

        url_path = "/im/session/v2/sendImMessage" if version == "v2" else "/im/session/v1/sendImMessage"

        resp = await self._request_data("POST", url_path, body=body)

        model = models.MessageSendResult.from_api(resp)
        return model

    async def _schedule_auto_recall(self, message_id: str, area: str, channel: str) -> None:
        if not self._config.auto_recall_enabled:
            return
        delay = self._config.auto_recall_delay
        if delay <= 0:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._do_auto_recall(message_id, area, channel, delay))
        except Exception as exc:
            logger.error("failed to schedule auto recall: %s", exc)

    async def _do_auto_recall(
            self, message_id: str, area: str, channel: str, delay: int
    ) -> None:
        try:
            await asyncio.sleep(delay)
            result = await self.recall_message(message_id, area=area, channel=channel)
            if not result.ok:
                logger.warning("auto recall failed: %s, area: %s, channel: %s", message_id, area, channel)
        except Exception as e:
            logger.error("auto recall exception: %s", e)

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

    async def recall_message(
            self,
            message_id: str,
            area: str,
            channel: str,
            timestamp: str = None,
            target: str = "",
    ) -> models.OperationResult:
        if message_id.strip() == "":
            raise ValueError("message_id is required for recall_message")
        if area.strip() == "":
            raise ValueError("area is required for recall_message")
        if channel.strip() == "":
            raise ValueError("channel is required for recall_message")
        timestamp = timestamp or self.signer.timestamp_us()

        url_path = "/im/session/v1/recallGim"
        body = {
            "area": area,
            "channel": channel,
            "messageId": message_id,
            "timestamp": timestamp,
            "target": target,
        }
        resp = await self._request_data("POST", url_path, body=body)
        return models.OperationResult.from_api(resp)

    async def recall_private_message(
            self,
            message_id: str,
            channel: str,
            target: str,
            area: Optional[str] = None,
            timestamp: Optional[str] = None,
    ) -> models.OperationResult:
        if message_id.strip() == "":
            raise ValueError("message_id is required for recall_private_message")
        if channel.strip() == "":
            raise ValueError("channel is required for recall_private_message")
        if target.strip() == "":
            raise ValueError("target is required for recall_private_message")
        timestamp = timestamp or self.signer.timestamp_us()
        url_path = "/im/session/v1/recallIm"
        body = {
            "area": area,
            "channel": channel,
            "messageId": message_id,
            "timestamp": timestamp,
            "target": target,
        }
        resp = await self._request_data("POST", url_path, body=body)
        return models.OperationResult.from_api(resp)

    async def get_channel_messages(
            self,
            area: str,
            channel: str,
            size: int = 50
    ) -> List[Message]:
        url_path = "/im/session/v2/messageBefore"
        params = {"area": area, "channel": channel, "size": str(size)}

        data = await self._request_data("GET", url_path, params=params)

        if not isinstance(data, dict) and data.get("message", None) is None:
            raise OopzApiError(
                "response format error: expected dict with 'messages' list",
                response=data,
            )
        messages = data.get("messages")
        return [models.Message.from_api(message) for message in messages]

    async def _upload_local_image_segment(self, seg: Image) -> Image:
        source_path = seg.source_path
        if not source_path:
            raise ValueError("Image segment has no source_path for upload")

        width = seg.width
        height = seg.height
        file_size = seg.file_size
        if width <= 0 or height <= 0 or file_size <= 0:
            width, height, file_size = get_image_info(source_path)

        ext = os.path.splitext(source_path)[1] or ".jpg"

        upload_result = await self._bot.media.upload_file(
            source_path,
            file_type="IMAGE",
            ext=ext,
        )

        return Image.from_uploaded(
            file_key=upload_result.file_key,
            url=upload_result.url,
            width=width,
            height=height,
            file_size=file_size,
            hash="",
            animated=upload_result.animated,
            display_name=upload_result.display_name,
            preview_file_key=getattr(upload_result, "preview_file_key", ""),
        )
