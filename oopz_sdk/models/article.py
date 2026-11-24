from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlparse

from pydantic import Field, field_validator

from oopz_sdk.exceptions import OopzApiError

from .base import BaseModel


def normalize_article_resource_path(value: str) -> str:
    """将带域名的签名资源 URL 归一为帖子接口提交所需的相对资源路径。"""
    if not isinstance(value, str):
        raise TypeError(f"resource path must be str, got {type(value).__name__}")
    text = value.strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        parsed = urlparse(text)
        return parsed.path or text
    return text


def _ensure_mapping(data: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise OopzApiError(f"invalid {label} payload: expected dict", payload=data)
    return data


def _reject_bool_int(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("bool is not a valid int")
    return value


class ArticleSection(BaseModel):
    """帖子频道分区信息。"""

    section_id: int = Field(alias="id")
    name: str = ""
    sort: int = 0

    @field_validator("section_id", "sort", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleSection":
        return cls.model_validate(_ensure_mapping(data, "article section"))


class ArticlePresignResult(BaseModel):
    """帖子/评论媒体上传预签名结果。"""

    expire_second: int = Field(default=180, alias="expireSecond")
    url: str
    path: str
    host_url: str = Field(default="", alias="hostUrl")
    auth: str = ""

    @field_validator("expire_second", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticlePresignResult":
        result = cls.model_validate(_ensure_mapping(data, "article presign"))
        if not result.url.strip() or not result.path.strip():
            raise OopzApiError(
                "invalid article presign payload: url and path cannot be empty",
                payload=data,
            )
        return result


class ArticleAttachment(BaseModel):
    """帖子附件（图片 / 短视频）。"""

    attachment_type: str = Field(default="IMAGE", alias="attachmentType")
    resource: str
    cover: str = ""
    width: int = 0
    height: int = 0
    duration: int = 0
    size: int = 0

    @field_validator("attachment_type")
    @classmethod
    def _normalize_attachment_type(cls, value: str) -> str:
        text = value.strip().upper()
        if not text:
            raise ValueError("attachment_type cannot be empty")
        return text

    @field_validator("width", "height", "duration", "size", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleAttachment":
        return cls.model_validate(_ensure_mapping(data, "article attachment"))

    def to_request_dict(self) -> dict[str, Any]:
        resource_path = normalize_article_resource_path(self.resource)
        if not resource_path:
            raise ValueError("attachment resource cannot be empty")
        payload: dict[str, Any] = {
            "attachmentType": self.attachment_type,
            "resource": resource_path,
            "width": self.width,
            "height": self.height,
        }
        cover_path = normalize_article_resource_path(self.cover)
        if cover_path:
            payload["cover"] = cover_path
        if self.duration > 0 or self.attachment_type == "SHORT_VIDEO":
            payload["duration"] = self.duration
        if self.size > 0:
            payload["size"] = self.size
        return payload


class ArticleCover(BaseModel):
    """帖子封面信息。"""

    resource: str = ""
    width: int = 0
    height: int = 0

    @field_validator("width", "height", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleCover":
        return cls.model_validate(_ensure_mapping(data, "article cover"))


class ArticlePublishResult(BaseModel):
    """发布或编辑帖子接口的返回。"""

    article_id: str = Field(alias="articleId")
    state: str = ""

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticlePublishResult":
        result = cls.model_validate(_ensure_mapping(data, "article publish"))
        if not result.article_id.strip():
            raise OopzApiError(
                "invalid article publish payload: articleId cannot be empty",
                payload=data,
            )
        return result


class ArticleInfo(BaseModel):
    """帖子详情 / 帖子列表项模型。"""

    article_id: str = Field(alias="articleId")
    area_id: str = Field(default="", alias="areaId")
    channel_id: str = Field(default="", alias="channelId")
    section_id: int = Field(default=0, alias="sectionId")
    title: str = ""
    summary: str = ""
    content: str = ""
    cover: ArticleCover | None = None
    author_uid: str = Field(default="", alias="authorUid")
    like_count: int = Field(default=0, alias="likeCount")
    liked: bool = False
    comment_count: int = Field(default=0, alias="commentCount")
    watch_count: int = Field(default=0, alias="watchCount")
    is_top: bool = Field(default=False, alias="isTop")
    action_type: int = Field(default=0, alias="actionType")
    state: str = ""
    publish_time: int = Field(default=0, alias="publishTime")
    created_at: int = Field(default=0, alias="createdAt")
    updated_at: int = Field(default=0, alias="updatedAt")
    show_cover: bool = Field(default=True, alias="showCover")
    attachments: list[ArticleAttachment] = Field(default_factory=list)
    ip_address: str = Field(default="", alias="ipAddress")

    @field_validator(
        "section_id",
        "like_count",
        "comment_count",
        "watch_count",
        "action_type",
        "publish_time",
        "created_at",
        "updated_at",
        mode="before",
    )
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleInfo":
        return cls.model_validate(_ensure_mapping(data, "article"))


class ArticleListPage(BaseModel):
    """帖子列表分页结果。"""

    items: list[ArticleInfo] = Field(default_factory=list, alias="list")
    next_cursor: int = Field(default=0, alias="nextCursor")
    next_cursor_state: str = Field(default="", alias="nextCursorState")
    page_size: int = Field(default=20, alias="pageSize")

    @field_validator("next_cursor", "page_size", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleListPage":
        return cls.model_validate(_ensure_mapping(data, "article list"))


class ArticleLikeUser(BaseModel):
    """帖子点赞用户信息。"""

    uid: str
    liked_at: int = Field(default=0, alias="likedAt")

    @field_validator("liked_at", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleLikeUser":
        return cls.model_validate(_ensure_mapping(data, "article like user"))


class ArticleLikeListPage(BaseModel):
    """帖子点赞列表分页结果。"""

    article_id: str = Field(default="", alias="articleId")
    like_count: int = Field(default=0, alias="likeCount")
    page_size: int = Field(default=20, alias="pageSize")
    items: list[ArticleLikeUser] = Field(default_factory=list, alias="list")
    next_cursor: int = Field(default=0, alias="nextCursor")

    @field_validator("like_count", "page_size", "next_cursor", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleLikeListPage":
        return cls.model_validate(_ensure_mapping(data, "article like list"))


class ArticleCommentImage(BaseModel):
    """评论图片项。"""

    url: str = ""
    type: str = "IMAGE"
    width: int = 0
    height: int = 0

    @field_validator("width", "height", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleCommentImage":
        return cls.model_validate(_ensure_mapping(data, "article comment image"))


class ArticleComment(BaseModel):
    """帖子评论模型。"""

    comment_id: str = Field(alias="commentId")
    article_id: str = Field(default="", alias="articleId")
    uid: str = ""
    content: str = ""
    image_list: list[ArticleCommentImage] = Field(default_factory=list, alias="imageList")
    mention_list: list[str] = Field(default_factory=list, alias="mentionList")
    parent_id: str = Field(default="", alias="parentId")
    reply_id: str = Field(default="", alias="replyId")
    reply_to_uid: str = Field(default="", alias="replyToUid")
    reply_deleted: bool = Field(default=False, alias="replyDeleted")
    like_count: int = Field(default=0, alias="likeCount")
    child_count: int = Field(default=0, alias="childCount")
    liked: bool = False
    is_article_author: bool = Field(default=False, alias="isArticleAuthor")
    ip_address: str = Field(default="", alias="ipAddress")
    created_at: int = Field(default=0, alias="createdAt")
    sub_cursor: int = Field(default=0, alias="subCursor")

    @field_validator("like_count", "child_count", "created_at", "sub_cursor", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleComment":
        return cls.model_validate(_ensure_mapping(data, "article comment"))


class ArticleCommentCreateResult(BaseModel):
    """发表/回复帖子评论的返回。"""

    comment_id: str = Field(alias="commentId")
    ip_address: str = Field(default="", alias="ipAddress")

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleCommentCreateResult":
        result = cls.model_validate(_ensure_mapping(data, "article comment create"))
        if not result.comment_id.strip():
            raise OopzApiError(
                "invalid article comment create payload: commentId cannot be empty",
                payload=data,
            )
        return result


class ArticleCommentListPage(BaseModel):
    """帖子评论列表分页结果。"""

    comment_count: int = Field(default=0, alias="commentCount")
    page_size: int = Field(default=30, alias="pageSize")
    items: list[ArticleComment] = Field(default_factory=list, alias="list")
    next_cursor: int = Field(default=0, alias="nextCursor")

    @field_validator("comment_count", "page_size", "next_cursor", mode="before")
    @classmethod
    def _validate_int_not_bool(cls, value: Any) -> Any:
        return _reject_bool_int(value)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ArticleCommentListPage":
        return cls.model_validate(_ensure_mapping(data, "article comment list"))
