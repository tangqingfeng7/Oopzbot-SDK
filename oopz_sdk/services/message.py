from __future__ import annotations

import asyncio
import logging
from typing import Optional, Any, List


from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.models.segment import Image, Segment
from oopz_sdk.services import BaseService
from oopz_sdk.utils.image import get_image_info, guess_image_ext, get_image_info_from_bytes, guess_image_ext_from_bytes, \
    read_image_bytes
from oopz_sdk.models import build_segments, normalize_message_parts
from oopz_sdk.utils.reaction_emoji import normalize_reaction_emoji

logger = logging.getLogger(__name__)


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
        # todo 已知问题: mentionList没有处理, 但是不影响使用
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
            raise ValueError("target is required for open_private_session()")

        url_path = "/client/v1/chat/v1/to"
        resp = await self._request_data("PATCH", url_path, params={"target": target})
        return models.PrivateSession.from_api(resp)

    async def send_message(
            self,
            *texts: str | Segment,
            area: str,
            channel: str,
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
        频道消息发送。
        """
        if area.strip() == "":
            raise ValueError("area is required for send_message()")
        if channel.strip() == "":
            raise ValueError("channel is required for send_message()")

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

        return models.MessageSendResult.from_api(resp)

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

    async def _resolve_segments(self, segments: list[Segment]) -> list[Segment]:
        resolved: list[Segment] = []

        for seg in segments:
            # 目前仅 Image 需要特殊处理，其他类型直接原样添加到 resolved 列表中
            if isinstance(seg, Image):
                if seg.is_uploaded:
                    resolved.append(seg)
                    continue

                if seg.has_file:
                    resolved.append(await self._upload_image_segment(seg))
                    continue

                raise ValueError("ImageSegment is neither uploaded nor backed by a local file")
            resolved.append(seg)
        return resolved

    async def recall_message(
            self,
            message_id: str,
            area: str,
            channel: str,
            timestamp: Optional[str] = None,
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
    ) -> List[models.Message]:
        if area.strip() == "":
            raise ValueError("area is required for get_channel_messages")
        if channel.strip() == "":
            raise ValueError("channel is required for get_channel_messages")
        if size <= 0:
            raise ValueError("size must be positive")

        url_path = "/im/session/v2/messageBefore"
        params = {"area": area, "channel": channel, "size": str(size)}

        data = await self._request_data("GET", url_path, params=params)

        if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
            raise OopzApiError(
                "response format error: expected dict with 'messages' list",
                payload=data,
            )
        return [models.Message.from_api(message) for message in data["messages"]]

    async def _upload_image_segment(self, seg: Image) -> Image:
        if seg.file is None:
            raise ValueError("Image segment has no file for upload")

        payload, filename = await asyncio.to_thread(read_image_bytes, seg.file)

        width = seg.width
        height = seg.height
        file_size = seg.file_size

        if width <= 0 or height <= 0 or file_size <= 0:
            width, height, file_size = await asyncio.to_thread(
                get_image_info_from_bytes,
                payload,
            )

        ext = guess_image_ext_from_bytes(payload, filename)

        upload_result = await self._bot.media.upload_bytes(
            payload,
            file_type="IMAGE",
            ext=ext,
            animated=seg.animated,
            display_name=seg.display_name or filename,
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

    async def top_message(self,
                          message_id: str,
                          area: str,
                          channel: str,
                          top_message: bool = True
                          ) -> models.OperationResult:
        """置顶或取消置顶消息。"""
        if message_id.strip() == "":
            raise ValueError("message_id is required for top_message")
        if area.strip() == "":
            raise ValueError("area is required for top_message")
        if channel.strip() == "":
            raise ValueError("channel is required for top_message")
        url_path = "/im/session/v1/messageTop"

        data = await self._request_data("POST", url_path, body={
            "messageId": message_id,
            "type": "TOP" if top_message else "CANCEL_TOP",
            "area": area,
            "channel": channel
        })
        return models.OperationResult.from_api(data)

    async def add_channel_reaction(self, message_id: str, area: str, channel: str, emoji: str) -> models.OperationResult:
        """
        给频道消息添加表情反应。
        """
        if area.strip() == "":
            raise ValueError("area is required for add_reaction")
        if channel.strip() == "":
            raise ValueError("channel is required for add_reaction")
        if emoji.strip() == "":
            raise ValueError("emoji is required for add_reaction")
        if message_id.strip() == "":
            raise ValueError("message_id is required for add_reaction")

        result = await self._request_data("POST", "/im/session/v1/gimReaction", body={
            "anchor": "",
            "area": area,
            "channel": channel,
            "emoji": normalize_reaction_emoji(emoji),
            "messageId": message_id,
            "target": "",
            "type": "REPLY"
        })
        return models.OperationResult.from_api(result)

    async def add_private_reaction(self, message_id: str, channel: str, target: str, emoji: str, area="") -> models.OperationResult:
        """
        给私信消息添加表情反应。
        """
        if target.strip() == "":
            raise ValueError("target is required for add_reaction")
        if channel.strip() == "":
            raise ValueError("channel is required for add_reaction")
        if emoji.strip() == "":
            raise ValueError("emoji is required for add_reaction")
        if message_id.strip() == "":
            raise ValueError("message_id is required for add_reaction")

        result = await self._request_data("POST", "/im/session/v1/imReaction", body={
            "anchor": target,
            "area": area,
            "channel": channel,
            "emoji": normalize_reaction_emoji(emoji),
            "messageId": message_id,
            "target": target,
            "type": "REPLY"
        })
        return models.OperationResult.from_api(result)

    async def get_channel_reaction_persons(self, message_id: str, channel: str, emoji: str, page: int = 1,
                                           page_size: int = 4) -> list[str]:
        """
        获取该频道消息有哪些用户回应了这个emoji

        :param message_id: 消息 ID
        :param channel: 私信会话 ID
        :param emoji: 表情 支持真实 emoji, 十进制或者十六进制emoji字符
        :param page: 页码
        :param page_size: 每页大小
        """
        if message_id.strip() == "":
            raise ValueError("message_id is required for get_channel_reaction_persons")
        if channel.strip() == "":
            raise ValueError("channel is required for get_channel_reaction_persons")
        if emoji.strip() == "":
            raise ValueError("emoji is required for get_reaction_persons")
        data = await self._request_data("GET", "/im/session/v2/gimReactionPersons", params={
            "messageId": message_id,
            "channel": channel,
            "emoji": normalize_reaction_emoji(emoji),
            "page": page,
            "pageSize": page_size,
        })
        if not isinstance(data, list):
            raise OopzApiError(
                "response format error: expected list for get_channel_reaction_persons",
                payload=data,
            )
        return data

    async def get_private_reaction_persons(self, message_id: str, channel: str, emoji: str, page: int = 1,
                                           page_size: int = 4) -> list[str]:
        """
        获取该私信消息有哪些用户回应了这个emoji

        :param message_id: 消息 ID
        :param channel: 私信会话 ID
        :param emoji: 表情 支持代码和实际unicode字符
        :param page: 页码
        :param page_size: 每页大小
        """
        if message_id.strip() == "":
            raise ValueError("message_id is required for get_private_reaction_persons")
        if channel.strip() == "":
            raise ValueError("channel is required for get_private_reaction_persons")
        if emoji.strip() == "":
            raise ValueError("emoji is required for get_private_reaction_persons")
        data = await self._request_data("GET", "/im/session/v2/imReactionPersons", params={
            "messageId": message_id,
            "channel": channel,
            "emoji": normalize_reaction_emoji(emoji),
            "page": page,
            "pageSize": page_size,
        })
        if not isinstance(data, list):
            raise OopzApiError(
                "response format error: expected list for get_private_reaction_persons",
                payload=data,
            )
        return data

    async def get_channel_message_reactions(self, message_id: str) -> models.MessageEmojiItem:
        if message_id.strip() == "":
            raise ValueError("message_id is required for get_private_message_reactions")

        data = await self._request_data("POST", "/im/session/v1/gimReactions", body=[{"messageId": message_id}])
        if len(data) != 1:
            raise ValueError("Unexpected response format: expected list with one item for get_message_reactions")
        return models.MessageEmojiItem.from_api(data[0])

    async def get_channel_message_reactions_batch(self, message_ids: str) -> list[models.MessageEmojiItem]:
        if len(message_ids) < 1:
            raise ValueError("message_ids is required for get_message_reactions")
        if len(message_ids) > 50:
            raise ValueError("message_ids is too large for get_message_reactions")
        id_body = [{"messageId": message_id} for message_id in message_ids]
        data = await self._request_data("POST", "/im/session/v1/gimReactions", body=id_body)

        return [models.MessageEmojiItem.from_api(d) for d in data]

    async def get_private_message_reactions(self, message_id: str) -> models.MessageEmojiItem:
        if message_id.strip() == "":
            raise ValueError("message_id is required for get_private_message_reactions")

        data = await self._request_data("POST", "/im/session/v1/imReactions", body=[{"messageId": message_id}])
        if len(data) != 1:
            raise ValueError(
                "Unexpected response format: expected list with one item for get_private_message_reactions")
        return models.MessageEmojiItem.from_api(data[0])

    async def get_private_message_reactions_batch(self, message_ids: list[str]) -> list[models.MessageEmojiItem]:
        if len(message_ids) < 1:
            raise ValueError("message_ids is required for get_private_message_reactions")
        if len(message_ids) > 50:
            raise ValueError("message_ids is too large for get_private_message_reactions")
        id_body = [{"messageId": message_id} for message_id in message_ids]
        data = await self._request_data("POST", "/im/session/v1/imReactions", body=id_body)

        return [models.MessageEmojiItem.from_api(d) for d in data]
