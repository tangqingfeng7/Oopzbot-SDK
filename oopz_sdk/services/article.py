from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Mapping, Sequence
from typing import Any

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.models.article import normalize_article_resource_path
from oopz_sdk.utils.image import (
    ImageInput,
    get_image_info_from_bytes,
    guess_image_ext_from_bytes,
    read_image_bytes,
)

from . import BaseService

logger = logging.getLogger(__name__)

_EXT_TO_MEDIA_TYPE: dict[str, str] = {
    ".webp": "WEBP",
    ".png": "PNG",
    ".jpg": "JPG",
    ".jpeg": "JPG",
    ".gif": "GIF",
    ".bmp": "BMP",
    ".mp4": "MP4",
}


def _require_non_empty_str(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str, got {type(value).__name__}")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} cannot be empty")
    return text


def _require_str(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str, got {type(value).__name__}")
    return value


def _require_int(value: int, field_name: str, *, min_value: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be int, got {type(value).__name__}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{field_name} must be >= {min_value}")
    return value


def _require_show_cover(value: bool | int) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int) and value in (0, 1):
        return value
    raise ValueError(f"show_cover must be bool or 0/1, got {value!r}")


def _require_str_sequence(value: Sequence[str] | None, field_name: str) -> Sequence[str]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a sequence of strings, not {type(value).__name__}")
    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"{field_name} items must be str, got {type(item).__name__}")
    return value


def _serialize_attachments(
    attachments: Sequence[models.ArticleAttachment | Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    if attachments is None:
        return []
    if isinstance(attachments, (str, bytes, bytearray)):
        raise TypeError(f"attachments must be a sequence, not {type(attachments).__name__}")
    result: list[dict[str, Any]] = []
    for item in attachments:
        if isinstance(item, models.ArticleAttachment):
            result.append(item.to_request_dict())
        elif isinstance(item, Mapping):
            result.append(models.ArticleAttachment.from_api(item).to_request_dict())
        else:
            raise TypeError(
                f"attachments item must be ArticleAttachment or Mapping, got {type(item).__name__}"
            )
    return result


class Article(BaseService):
    """帖子频道能力：频道管理、分区、发帖、编辑、删除、点赞、评论与回复。"""

    # ------------------------------------------------------------------
    # 帖子频道（委托给 Channel service）
    # ------------------------------------------------------------------

    async def create_channel(
        self,
        area: str,
        name: str,
        group_id: str = "",
        *,
        secret: bool = False,
    ) -> models.CreateChannelResult:
        """创建帖子频道。"""
        return await self._bot.channels.create_channel(
            area=area,
            name=name,
            group_id=group_id,
            channel_type=models.ChannelType.ARTICLE,
            secret=secret,
        )

    async def update_channel(
        self,
        area: str,
        channel_id: str,
        *,
        name: str | None = None,
        article_gap_second: int | None = None,
        comment_gap_second: int | None = None,
        text_gap_second: int | None = None,
        article_control_enabled: bool | None = None,
        text_control_enabled: bool | None = None,
        access_control_enabled: bool | None = None,
        secret: bool | None = None,
        has_password: bool | None = None,
        password: str | None = None,
        article_roles: list[int] | None = None,
        text_roles: list[int] | None = None,
        accessible_roles: list[int] | None = None,
        accessible_members: list[str] | None = None,
    ) -> models.OperationResult:
        """编辑帖子频道设置。"""
        return await self._bot.channels.update_channel(
            area=area,
            channel_id=channel_id,
            name=name,
            article_gap_second=article_gap_second,
            comment_gap_second=comment_gap_second,
            text_gap_second=text_gap_second,
            article_control_enabled=article_control_enabled,
            text_control_enabled=text_control_enabled,
            access_control_enabled=access_control_enabled,
            secret=secret,
            has_password=has_password,
            password=password,
            article_roles=article_roles,
            text_roles=text_roles,
            accessible_roles=accessible_roles,
            accessible_members=accessible_members,
        )

    async def delete_channel(self, area: str, channel: str) -> models.OperationResult:
        """删除帖子频道。"""
        return await self._bot.channels.delete_channel(area=area, channel=channel)

    # ------------------------------------------------------------------
    # 帖子频道分区（Section）
    # ------------------------------------------------------------------

    async def get_sections(self, area: str, channel: str) -> list[models.ArticleSection]:
        """获取帖子频道分区列表。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")

        data = await self._request_data(
            "GET",
            "/uni/area/article/section/v1/list",
            params={"areaId": area, "channelId": channel},
        )
        if not isinstance(data, Mapping) or "list" not in data:
            raise OopzApiError(
                "invalid article section list payload: missing list", payload=data
            )

        raw_list = data["list"]
        if raw_list is None:
            return []
        if not isinstance(raw_list, list):
            raise OopzApiError(
                "invalid article section list payload: list must be a list", payload=data
            )
        return [models.ArticleSection.from_api(item) for item in raw_list]

    async def create_section(
        self,
        area: str,
        channel: str,
        name: str,
    ) -> models.ArticleSection:
        """新增帖子频道分区。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        name = _require_non_empty_str(name, "name")

        data = await self._request_data(
            "POST",
            "/uni/area/article/section/v1/create",
            body={"areaId": area, "channelId": channel, "name": name},
        )
        return models.ArticleSection.from_api(data)

    async def edit_section(
        self,
        area: str,
        channel: str,
        section_id: int,
        name: str,
    ) -> models.ArticleSection:
        """编辑帖子频道分区名称。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        section_id = _require_int(section_id, "section_id", min_value=1)
        name = _require_non_empty_str(name, "name")

        data = await self._request_data(
            "POST",
            "/uni/area/article/section/v1/edit",
            body={
                "areaId": area,
                "channelId": channel,
                "id": section_id,
                "name": name,
            },
        )
        return models.ArticleSection.from_api(data)

    async def delete_section(
        self,
        area: str,
        channel: str,
        section_id: int,
    ) -> models.OperationResult:
        """删除帖子频道分区。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        section_id = _require_int(section_id, "section_id", min_value=1)

        data = await self._request_data(
            "POST",
            "/uni/area/article/section/v1/delete",
            body={
                "areaId": area,
                "channelId": channel,
                "id": section_id,
            },
        )
        return models.OperationResult.from_api(data)

    # ------------------------------------------------------------------
    # 媒体预签名与图片上传
    # ------------------------------------------------------------------

    async def get_upload_presign(
        self,
        area: str,
        channel: str,
        *,
        media_type: str = "WEBP",
        operations: str | None = None,
    ) -> models.ArticlePresignResult:
        """获取帖子/评论媒体上传预签名地址。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        normalized_media_type = _require_non_empty_str(media_type, "media_type").upper()

        payload: dict[str, str] = {
            "areaId": area,
            "channelId": channel,
            "mediaType": normalized_media_type,
        }
        if operations is not None:
            op_text = _require_non_empty_str(operations, "operations")
            payload["operations"] = op_text

        data = await self._request_data(
            "POST",
            "/uni/area/article/v1/presign",
            params=payload,
            body=payload,
        )
        return models.ArticlePresignResult.from_api(data)

    async def upload_image(
        self,
        area: str,
        channel: str,
        file: ImageInput,
        *,
        media_type: str | None = None,
        operations: str | None = None,
    ) -> models.ArticleAttachment:
        """上传帖子/评论图片到 COS，返回可直接传给发帖或评论接口的附件对象。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        op_text = _require_non_empty_str(operations, "operations") if operations is not None else None

        payload, filename = await asyncio.to_thread(read_image_bytes, file)
        if not payload:
            raise ValueError("upload image payload is empty")

        width, height, file_size = await asyncio.to_thread(get_image_info_from_bytes, payload)
        if media_type is None:
            ext = await asyncio.to_thread(guess_image_ext_from_bytes, payload, filename)
            resolved_media_type = _EXT_TO_MEDIA_TYPE.get(ext.lower())
            if resolved_media_type is None:
                raise ValueError(f"unsupported image extension: {ext!r}")
        else:
            resolved_media_type = _require_non_empty_str(media_type, "media_type").upper()

        presign = await self.get_upload_presign(
            area=area,
            channel=channel,
            media_type=resolved_media_type,
            operations=op_text,
        )

        headers: dict[str, str] = {}
        if presign.auth:
            headers["Authorization"] = presign.auth
        if op_text is not None:
            file_id = os.path.basename(presign.path.lstrip("/"))
            headers["Pic-Operations"] = json.dumps(
                {
                    "is_pic_info": 1,
                    "rules": [{"fileid": file_id, "rule": op_text}],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )

        resp = await self.request_raw("PUT", presign.url, data=payload, headers=headers)
        if resp.status_code not in (200, 201):
            raise OopzApiError(
                f"帖子图片上传失败: {resp.text}",
                status_code=resp.status_code,
            )

        return models.ArticleAttachment(
            attachment_type="IMAGE",
            resource=presign.path,
            width=width,
            height=height,
            size=file_size,
        )

    # ------------------------------------------------------------------
    # 帖子 CRUD 与点赞
    # ------------------------------------------------------------------

    async def get_articles(
        self,
        area: str,
        channel: str,
        *,
        section_id: int = 0,
        cursor: int = 0,
        cursor_state: str = "",
    ) -> models.ArticleListPage:
        """获取帖子列表。`section_id=0` 表示全部，`-1` 表示我的，正整数为指定分区 ID。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        section_id = _require_int(section_id, "section_id", min_value=-1)
        cursor = _require_int(cursor, "cursor", min_value=0)
        cursor_state = _require_str(cursor_state, "cursor_state").strip()

        params: dict[str, Any] = {
            "areaId": area,
            "channelId": channel,
            "sectionId": section_id,
            "cursor": cursor,
        }
        if cursor_state:
            params["cursorState"] = cursor_state

        data = await self._request_data("GET", "/uni/area/article/v1/list", params=params)
        return models.ArticleListPage.from_api(data)

    async def get_article_detail(
        self,
        area: str,
        channel: str,
        article_id: str,
    ) -> models.ArticleInfo:
        """获取帖子详情。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")

        data = await self._request_data(
            "GET",
            "/uni/area/article/v1/detail",
            params={"areaId": area, "channelId": channel, "articleId": article_id},
        )
        return models.ArticleInfo.from_api(data)

    async def create_article(
        self,
        area: str,
        channel: str,
        title: str,
        content: str,
        *,
        section_id: int = 0,
        attachments: Sequence[models.ArticleAttachment | Mapping[str, Any]] | None = None,
        cover_index: int = 0,
        show_cover: bool | int = True,
    ) -> models.ArticlePublishResult:
        """发布帖子。

        参数
        ----
        section_id : int
            发布到的分区 ID，`0` 表示不指定分区（仅在“全部”中显示）。
        show_cover : bool | int
            是否在帖子详情内显示封面（`True`/`1` 显示，`False`/`0` 不显示）。
        """
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        title = _require_non_empty_str(title, "title")
        content = _require_str(content, "content")
        section_id = _require_int(section_id, "section_id", min_value=0)
        cover_index = _require_int(cover_index, "cover_index", min_value=0)
        show_cover_int = _require_show_cover(show_cover)
        serialized_attachments = _serialize_attachments(attachments)
        if serialized_attachments and cover_index >= len(serialized_attachments):
            raise ValueError("cover_index out of range for attachments")

        body: dict[str, Any] = {
            "areaId": area,
            "channelId": channel,
            "sectionId": section_id,
            "title": title,
            "content": content,
            "attachments": serialized_attachments,
            "coverIndex": cover_index,
            "showCover": show_cover_int,
        }
        data = await self._request_data("POST", "/uni/area/article/v1/create", body=body)
        return models.ArticlePublishResult.from_api(data)

    async def edit_article(
        self,
        area: str,
        channel: str,
        article_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        section_id: int | None = None,
        attachments: Sequence[models.ArticleAttachment | Mapping[str, Any]] | None = None,
        cover_index: int | None = None,
        show_cover: bool | int | None = None,
    ) -> models.ArticlePublishResult:
        """编辑帖子。未传入的字段会自动拉取原帖子详情保持不变。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")

        if title is not None:
            title = _require_non_empty_str(title, "title")
        if content is not None:
            content = _require_str(content, "content")
        if section_id is not None:
            section_id = _require_int(section_id, "section_id", min_value=0)
        if cover_index is not None:
            cover_index = _require_int(cover_index, "cover_index", min_value=0)
        show_cover_int = _require_show_cover(show_cover) if show_cover is not None else None
        serialized_explicit_attachments = (
            _serialize_attachments(attachments) if attachments is not None else None
        )

        # 只有确实有未提供的字段需要从原帖回填时才发 GET /detail；
        # 当 attachments 已显式替换且 cover_index 未传时默认取 0，无需拉旧封面。
        need_detail = any(
            value is None for value in (title, content, section_id, attachments, show_cover)
        )
        detail: models.ArticleInfo | None = None
        if need_detail:
            detail = await self.get_article_detail(area, channel, article_id)

        final_title = title if title is not None else _require_non_empty_str(
            detail.title if detail is not None else "", "title"
        )
        final_content = content if content is not None else (detail.content if detail is not None else "")
        final_section_id = (
            section_id if section_id is not None else (detail.section_id if detail is not None else 0)
        )
        final_attachments = (
            serialized_explicit_attachments
            if serialized_explicit_attachments is not None
            else _serialize_attachments(detail.attachments if detail is not None else [])
        )

        if cover_index is not None:
            final_cover_index = cover_index
        elif attachments is None and detail is not None and detail.cover and detail.cover.resource:
            final_cover_index = 0
            cover_path = normalize_article_resource_path(detail.cover.resource)
            for idx, att in enumerate(final_attachments):
                if att.get("resource") == cover_path:
                    final_cover_index = idx
                    break
        else:
            final_cover_index = 0

        if final_attachments and final_cover_index >= len(final_attachments):
            raise ValueError("cover_index out of range for attachments")

        final_show_cover = (
            show_cover_int
            if show_cover_int is not None
            else (1 if (detail.show_cover if detail is not None else True) else 0)
        )

        body: dict[str, Any] = {
            "articleId": article_id,
            "areaId": area,
            "channelId": channel,
            "sectionId": final_section_id,
            "title": final_title,
            "content": final_content,
            "attachments": final_attachments,
            "coverIndex": final_cover_index,
            "showCover": final_show_cover,
        }
        data = await self._request_data("POST", "/uni/area/article/v1/edit", body=body)
        return models.ArticlePublishResult.from_api(data)

    async def delete_article(
        self,
        area: str,
        channel: str,
        article_id: str,
    ) -> models.OperationResult:
        """删除帖子。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")

        data = await self._request_data(
            "POST",
            "/uni/area/article/v1/delete",
            body={
                "areaId": area,
                "channelId": channel,
                "articleId": article_id,
            },
        )
        return models.OperationResult.from_api(data)

    async def like_article(
        self,
        area: str,
        channel: str,
        article_id: str,
        *,
        liked: bool = True,
    ) -> models.OperationResult:
        """点赞或取消点赞帖子。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")
        if not isinstance(liked, bool):
            raise TypeError(f"liked must be bool, got {type(liked).__name__}")

        data = await self._request_data(
            "POST",
            "/uni/area/article/v1/like",
            body={
                "area": area,
                "articleId": article_id,
                "channel": channel,
                "liked": liked,
            },
        )
        return models.OperationResult.from_api(data)

    async def unlike_article(
        self,
        area: str,
        channel: str,
        article_id: str,
    ) -> models.OperationResult:
        """取消点赞帖子。"""
        return await self.like_article(area, channel, article_id, liked=False)

    async def get_article_likes(
        self,
        area: str,
        channel: str,
        article_id: str,
        *,
        cursor: int = 0,
        page_size: int = 20,
    ) -> models.ArticleLikeListPage:
        """获取帖子点赞用户列表。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")
        cursor = _require_int(cursor, "cursor", min_value=0)
        page_size = _require_int(page_size, "page_size", min_value=1)

        data = await self._request_data(
            "GET",
            "/uni/area/article/v1/likeList",
            params={
                "area": area,
                "channel": channel,
                "articleId": article_id,
                "cursor": cursor,
                "pageSize": page_size,
            },
        )
        return models.ArticleLikeListPage.from_api(data)

    # ------------------------------------------------------------------
    # 帖子评论：列表、评论、回复、删除、点赞
    # ------------------------------------------------------------------

    async def get_comments(
        self,
        area: str,
        channel: str,
        article_id: str,
        *,
        cursor: int = 0,
        page_size: int = 30,
    ) -> models.ArticleCommentListPage:
        """获取帖子评论列表。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")
        cursor = _require_int(cursor, "cursor", min_value=0)
        page_size = _require_int(page_size, "page_size", min_value=1)

        data = await self._request_data(
            "GET",
            "/uni/area/article/comment/v1/list",
            params={
                "area": area,
                "channel": channel,
                "articleId": article_id,
                "cursor": cursor,
                "pageSize": page_size,
            },
        )
        return models.ArticleCommentListPage.from_api(data)

    async def create_comment(
        self,
        area: str,
        channel: str,
        article_id: str,
        content: str = "",
        *,
        image_list: Sequence[str] | None = None,
        mention_list: Sequence[str] | None = None,
        parent_id: str = "",
        reply_id: str = "",
    ) -> models.ArticleCommentCreateResult:
        """发表帖子评论（传入 `parent_id` 与 `reply_id` 时即为回复评论）。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")
        text = _require_str(content, "content")
        normalized_parent_id = _require_str(parent_id, "parent_id").strip()
        normalized_reply_id = _require_str(reply_id, "reply_id").strip()
        if bool(normalized_parent_id) != bool(normalized_reply_id):
            raise ValueError("parent_id and reply_id must be provided together")

        normalized_images = [
            normalize_article_resource_path(item)
            for item in _require_str_sequence(image_list, "image_list")
            if item.strip()
        ]
        normalized_mentions = [
            item.strip()
            for item in _require_str_sequence(mention_list, "mention_list")
            if item.strip()
        ]

        if not text.strip() and not normalized_images:
            raise ValueError("content or image_list is required for create_comment")

        body: dict[str, Any] = {
            "area": area,
            "channel": channel,
            "articleId": article_id,
            "content": text,
            "imageList": normalized_images,
            "mentionList": normalized_mentions,
            "parentId": normalized_parent_id,
            "replyId": normalized_reply_id,
        }
        data = await self._request_data("POST", "/uni/area/article/comment/v1/create", body=body)
        return models.ArticleCommentCreateResult.from_api(data)

    async def reply_comment(
        self,
        area: str,
        channel: str,
        article_id: str,
        parent_id: str,
        content: str = "",
        *,
        reply_id: str | None = None,
        image_list: Sequence[str] | None = None,
        mention_list: Sequence[str] | None = None,
    ) -> models.ArticleCommentCreateResult:
        """回复指定帖子评论。`reply_id` 未传时默认与 `parent_id` 相同。"""
        normalized_parent_id = _require_non_empty_str(parent_id, "parent_id")
        normalized_reply_id = (
            _require_non_empty_str(reply_id, "reply_id")
            if reply_id is not None
            else normalized_parent_id
        )
        return await self.create_comment(
            area=area,
            channel=channel,
            article_id=article_id,
            content=content,
            image_list=image_list,
            mention_list=mention_list,
            parent_id=normalized_parent_id,
            reply_id=normalized_reply_id,
        )

    async def delete_comment(
        self,
        area: str,
        channel: str,
        article_id: str,
        comment_id: str,
    ) -> models.OperationResult:
        """删除帖子评论。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")
        comment_id = _require_non_empty_str(comment_id, "comment_id")

        data = await self._request_data(
            "POST",
            "/uni/area/article/comment/v1/delete",
            body={
                "area": area,
                "channel": channel,
                "articleId": article_id,
                "commentId": comment_id,
            },
        )
        return models.OperationResult.from_api(data)

    async def like_comment(
        self,
        area: str,
        channel: str,
        article_id: str,
        comment_id: str,
        *,
        liked: bool = True,
    ) -> models.OperationResult:
        """点赞或取消点赞帖子评论。"""
        area = _require_non_empty_str(area, "area")
        channel = _require_non_empty_str(channel, "channel")
        article_id = _require_non_empty_str(article_id, "article_id")
        comment_id = _require_non_empty_str(comment_id, "comment_id")
        if not isinstance(liked, bool):
            raise TypeError(f"liked must be bool, got {type(liked).__name__}")

        params = {
            "area": area,
            "channel": channel,
            "articleId": article_id,
            "commentId": comment_id,
            "liked": "true" if liked else "false",
        }
        body = {
            "area": area,
            "channel": channel,
            "articleId": article_id,
            "commentId": comment_id,
            "liked": liked,
        }
        data = await self._request_data(
            "POST",
            "/uni/area/article/comment/v1/like",
            params=params,
            body=body,
        )
        return models.OperationResult.from_api(data)

    async def unlike_comment(
        self,
        area: str,
        channel: str,
        article_id: str,
        comment_id: str,
    ) -> models.OperationResult:
        """取消点赞帖子评论。"""
        return await self.like_comment(area, channel, article_id, comment_id, liked=False)
