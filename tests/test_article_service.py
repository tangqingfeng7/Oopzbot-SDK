from __future__ import annotations

import asyncio
import io
import json
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image as PILImage

import oopz_sdk
from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.services.article import Article
from oopz_sdk.services.channel import Channel
from oopz_sdk.state.cache import CacheStore
from oopz_sdk.testing.factories import make_config
from oopz_sdk.transport.http import HttpResponse


def _run(coro):
    return asyncio.run(coro)


class _RecordingChannel(Channel):
    def __init__(self, responses: list[Any], groups: list[models.ChannelGroupInfo] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responses = list(responses)
        self._config = SimpleNamespace(person_uid="bot-uid")
        self.cache = CacheStore(None)
        self._groups = groups if groups is not None else [
            models.ChannelGroupInfo.from_api({"id": "grp-default", "name": "默认分组", "channels": []})
        ]
        self._bot = SimpleNamespace(
            areas=SimpleNamespace(get_area_channels=self._get_area_channels),
        )

    async def _get_area_channels(self, area: str) -> list[models.ChannelGroupInfo]:
        return self._groups

    async def _request_data(self, method: str, path: str, *, params=None, body=None) -> Any:
        self.calls.append({"method": method, "path": path, "params": params, "body": body})
        return self._responses.pop(0)


class _RecordingArticle(Article):
    def __init__(
        self,
        responses: list[Any] | None = None,
        raw_responses: list[HttpResponse] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raw_calls: list[dict[str, Any]] = []
        self._responses = list(responses or [])
        self._raw_responses = list(raw_responses or [])
        self._config = SimpleNamespace(person_uid="bot-uid")
        self.cache = CacheStore(None)

    async def _request_data(self, method: str, path: str, *, params=None, body=None) -> Any:
        self.calls.append({"method": method, "path": path, "params": params, "body": body})
        return self._responses.pop(0)

    async def request_raw(self, method: str, url: str, *, params=None, data=None, headers=None, timeout=None) -> HttpResponse:
        self.raw_calls.append(
            {"method": method, "url": url, "params": params, "data": data, "headers": headers}
        )
        return self._raw_responses.pop(0)


def _make_png_bytes(width: int = 16, height: int = 12) -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (width, height), color=(12, 34, 56)).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 帖子频道：通过 Channel service 创建 / 编辑
# ---------------------------------------------------------------------------


_ARTICLE_CHANNEL_SETTING: dict[str, Any] = {
    "channel": "ch-art-1",
    "name": "旧名称",
    "type": "ARTICLE",
    "textGapSecond": 0,
    "articleGapSecond": 5,
    "commentGapSecond": 10,
    "voiceQuality": "64k",
    "voiceDelay": "LOW",
    "maxMember": 30000,
    "voiceControlEnabled": False,
    "textControlEnabled": False,
    "articleControlEnabled": True,
    "textRoles": [],
    "voiceRoles": [],
    "articleRoles": [101],
    "accessControlEnabled": False,
    "accessibleRoles": [],
    "accessibleMembers": [],
    "secret": False,
    "hasPassword": False,
    "password": "",
}


def test_create_article_channel_payload_and_response() -> None:
    channel_svc = _RecordingChannel(
        responses=[
            {
                "id": "ch-art-1",
                "name": "公告帖",
                "secret": False,
                "type": "ARTICLE",
                "settings": {"maxMember": 2147483647},
                "areaId": "area-1",
                "groupId": "grp-default",
            }
        ]
    )

    result = _run(channel_svc.create_channel("area-1", "公告帖", channel_type=models.ChannelType.ARTICLE))

    assert result.channel_id == "ch-art-1"
    assert result.area == "area-1"
    assert result.group_id == "grp-default"
    assert result.channel_type == models.ChannelType.ARTICLE
    assert result.max_member == 2147483647
    assert channel_svc.calls == [
        {
            "method": "POST",
            "path": "/client/v1/area/v1/channel/v1/create",
            "params": None,
            "body": {
                "area": "area-1",
                "group": "grp-default",
                "name": "公告帖",
                "type": "ARTICLE",
                "secret": False,
                "vender": "TR",
            },
        }
    ]


def test_update_article_channel_preserves_and_updates_article_fields() -> None:
    channel_svc = _RecordingChannel(responses=[dict(_ARTICLE_CHANNEL_SETTING), True])

    res = _run(
        channel_svc.update_channel(
            "area-1",
            "ch-art-1",
            name="新名称",
            article_gap_second=30,
            comment_gap_second=15,
            article_control_enabled=True,
            article_roles=[201, 202],
        )
    )

    assert res.ok is True
    assert channel_svc.calls[0]["path"] == "/area/v3/channel/setting/info"
    edit_body = channel_svc.calls[1]["body"]
    assert channel_svc.calls[1]["path"] == "/area/v3/channel/setting/edit"
    assert edit_body["name"] == "新名称"
    assert edit_body["articleGapSecond"] == 30
    assert edit_body["commentGapSecond"] == 15
    assert edit_body["articleControlEnabled"] is True
    assert edit_body["articleRoles"] == [201, 202]


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"article_gap_second": "10"}, TypeError),
        ({"article_gap_second": -1}, ValueError),
        ({"comment_gap_second": True}, TypeError),
        ({"comment_gap_second": -1}, ValueError),
        ({"article_control_enabled": "false"}, TypeError),
        ({"article_roles": ["101"]}, TypeError),
        ({"article_roles": [True]}, TypeError),
        ({"article_roles": 101}, TypeError),
    ],
)
def test_update_channel_rejects_invalid_article_params_before_network(
    kwargs: dict[str, Any], error: type
) -> None:
    channel_svc = _RecordingChannel(responses=[])

    with pytest.raises(error):
        _run(channel_svc.update_channel("area-1", "ch-art-1", **kwargs))
    assert channel_svc.calls == []


def test_create_channel_rejects_non_bool_secret_before_network() -> None:
    channel_svc = _RecordingChannel(responses=[])

    with pytest.raises(TypeError):
        _run(
            channel_svc.create_channel(
                "area-1", "公告帖", channel_type=models.ChannelType.ARTICLE, secret="false"  # type: ignore[arg-type]
            )
        )
    assert channel_svc.calls == []


def test_article_service_no_longer_wraps_channel_methods() -> None:
    for name in ("create_channel", "update_channel", "delete_channel"):
        assert not hasattr(Article, name)


def test_attachment_mapping_and_bare_domain_url_rejected() -> None:
    from oopz_sdk.models.article import normalize_article_resource_path

    svc = _RecordingArticle()
    with pytest.raises(TypeError):
        _run(
            svc.create_article(
                "area-1",
                "ch-1",
                "标题",
                "正文",
                attachments={"resource": "/community/a.webp"},  # type: ignore[arg-type]
            )
        )
    assert svc.calls == []

    with pytest.raises(ValueError):
        normalize_article_resource_path("https://resourcecdn.oopz.cn")
    with pytest.raises(ValueError):
        normalize_article_resource_path("https://resourcecdn.oopz.cn/")


# ---------------------------------------------------------------------------
# 分区：列表 / 新增 / 编辑 / 删除
# ---------------------------------------------------------------------------


def test_section_crud() -> None:
    svc = _RecordingArticle(
        responses=[
            {"list": [{"id": 3024, "name": "Test", "sort": 1}]},
            {"id": 3025, "name": "攻略"},
            {"id": 3025, "name": "精选攻略"},
            None,
        ]
    )

    sections = _run(svc.get_sections("area-1", "ch-1"))
    assert len(sections) == 1
    assert sections[0].section_id == 3024
    assert sections[0].name == "Test"

    created = _run(svc.create_section("area-1", "ch-1", "攻略"))
    assert created.section_id == 3025
    assert created.name == "攻略"

    edited = _run(svc.edit_section("area-1", "ch-1", 3025, "精选攻略"))
    assert edited.section_id == 3025
    assert edited.name == "精选攻略"

    deleted = _run(svc.delete_section("area-1", "ch-1", 3025))
    assert deleted.ok is True

    assert svc.calls == [
        {
            "method": "GET",
            "path": "/uni/area/article/section/v1/list",
            "params": {"areaId": "area-1", "channelId": "ch-1"},
            "body": None,
        },
        {
            "method": "POST",
            "path": "/uni/area/article/section/v1/create",
            "params": None,
            "body": {"areaId": "area-1", "channelId": "ch-1", "name": "攻略"},
        },
        {
            "method": "POST",
            "path": "/uni/area/article/section/v1/edit",
            "params": None,
            "body": {"areaId": "area-1", "channelId": "ch-1", "id": 3025, "name": "精选攻略"},
        },
        {
            "method": "POST",
            "path": "/uni/area/article/section/v1/delete",
            "params": None,
            "body": {"areaId": "area-1", "channelId": "ch-1", "id": 3025},
        },
    ]


# ---------------------------------------------------------------------------
# 帖子：发布 / 编辑 / 删除 / 列表 / 详情 / 点赞与取消点赞
# ---------------------------------------------------------------------------


def test_create_article_with_section_and_show_cover() -> None:
    svc = _RecordingArticle(
        responses=[{"articleId": "art-1", "state": "AUDITING"}]
    )

    attachment = models.ArticleAttachment(
        attachment_type="IMAGE",
        resource="https://resourcecdn.oopz.cn/community/area_article/20261124/a.webp?sign=abc",
        width=650,
        height=390,
    )
    res = _run(
        svc.create_article(
            "area-1",
            "ch-1",
            "标题",
            "正文",
            section_id=3023,
            attachments=[attachment],
            cover_index=0,
            show_cover=False,
        )
    )

    assert res.article_id == "art-1"
    assert res.state == "AUDITING"
    assert svc.calls[0] == {
        "method": "POST",
        "path": "/uni/area/article/v1/create",
        "params": None,
        "body": {
            "areaId": "area-1",
            "channelId": "ch-1",
            "sectionId": 3023,
            "title": "标题",
            "content": "正文",
            "attachments": [
                {
                    "attachmentType": "IMAGE",
                    "resource": "/community/area_article/20261124/a.webp",
                    "width": 650,
                    "height": 390,
                }
            ],
            "coverIndex": 0,
            "showCover": 0,
        },
    }


def test_edit_article_partial_update_fetches_detail_and_strips_cdn_url() -> None:
    svc = _RecordingArticle(
        responses=[
            {
                "articleId": "art-1",
                "areaId": "area-1",
                "channelId": "ch-1",
                "sectionId": 3023,
                "title": "原标题",
                "content": "原正文",
                "showCover": 1,
                "attachments": [
                    {
                        "attachmentType": "IMAGE",
                        "resource": "https://resourcecdn.oopz.cn/community/area_article/20261124/a.webp?sign=xyz",
                        "width": 650,
                        "height": 390,
                    }
                ],
            },
            {"articleId": "art-1", "state": "PUBLISHED"},
        ]
    )

    res = _run(svc.edit_article("area-1", "ch-1", "art-1", show_cover=False))

    assert res.article_id == "art-1"
    assert res.state == "PUBLISHED"
    assert len(svc.calls) == 2
    assert svc.calls[0]["path"] == "/uni/area/article/v1/detail"
    assert svc.calls[1] == {
        "method": "POST",
        "path": "/uni/area/article/v1/edit",
        "params": None,
        "body": {
            "articleId": "art-1",
            "areaId": "area-1",
            "channelId": "ch-1",
            "sectionId": 3023,
            "title": "原标题",
            "content": "原正文",
            "attachments": [
                {
                    "attachmentType": "IMAGE",
                    "resource": "/community/area_article/20261124/a.webp",
                    "width": 650,
                    "height": 390,
                }
            ],
            "coverIndex": 0,
            "showCover": 0,
        },
    }


def test_edit_article_full_update_skips_detail_fetch() -> None:
    svc = _RecordingArticle(responses=[{"articleId": "art-1", "state": "PUBLISHED"}])

    res = _run(
        svc.edit_article(
            "area-1",
            "ch-1",
            "art-1",
            title="新标题",
            content="新正文",
            section_id=0,
            attachments=[],
            cover_index=0,
            show_cover=True,
        )
    )

    assert res.state == "PUBLISHED"
    assert len(svc.calls) == 1
    assert svc.calls[0]["path"] == "/uni/area/article/v1/edit"
    assert svc.calls[0]["body"]["showCover"] == 1


def test_delete_and_like_unlike_article() -> None:
    svc = _RecordingArticle(responses=[None, None, None])

    assert _run(svc.like_article("area-1", "ch-1", "art-1")).ok is True
    assert _run(svc.unlike_article("area-1", "ch-1", "art-1")).ok is True
    assert _run(svc.delete_article("area-1", "ch-1", "art-1")).ok is True

    assert svc.calls == [
        {
            "method": "POST",
            "path": "/uni/area/article/v1/like",
            "params": None,
            "body": {"area": "area-1", "articleId": "art-1", "channel": "ch-1", "liked": True},
        },
        {
            "method": "POST",
            "path": "/uni/area/article/v1/like",
            "params": None,
            "body": {"area": "area-1", "articleId": "art-1", "channel": "ch-1", "liked": False},
        },
        {
            "method": "POST",
            "path": "/uni/area/article/v1/delete",
            "params": None,
            "body": {"areaId": "area-1", "channelId": "ch-1", "articleId": "art-1"},
        },
    ]


# ---------------------------------------------------------------------------
# 评论：评论 / 带图评论 / 回复评论 / 删除评论 / 点赞与取消点赞评论 / 列表
# ---------------------------------------------------------------------------


def test_comment_create_reply_delete_like_and_list() -> None:
    svc = _RecordingArticle(
        responses=[
            {"commentId": "cmt-1", "ipAddress": "广西"},
            {"commentId": "cmt-2", "ipAddress": "广西"},
            {"commentId": "cmt-3", "ipAddress": "广西"},
            None,
            None,
            None,
            {
                "commentCount": 1,
                "pageSize": 30,
                "list": [
                    {
                        "commentId": "cmt-1",
                        "articleId": "art-1",
                        "uid": "u-1",
                        "content": "hello",
                        "imageList": None,
                        "mentionList": [],
                        "isArticleAuthor": True,
                        "liked": False,
                    }
                ],
                "nextCursor": 0,
            },
        ]
    )

    c1 = _run(svc.create_comment("area-1", "ch-1", "art-1", "hello"))
    assert c1.comment_id == "cmt-1"

    c2 = _run(
        svc.create_comment(
            "area-1",
            "ch-1",
            "art-1",
            image_list=["/community/area_article/20261124/img.webp"],
        )
    )
    assert c2.comment_id == "cmt-2"

    c3 = _run(svc.reply_comment("area-1", "ch-1", "art-1", "cmt-1", "reply text"))
    assert c3.comment_id == "cmt-3"

    assert _run(svc.like_comment("area-1", "ch-1", "art-1", "cmt-1")).ok is True
    assert _run(svc.unlike_comment("area-1", "ch-1", "art-1", "cmt-1")).ok is True
    assert _run(svc.delete_comment("area-1", "ch-1", "art-1", "cmt-3")).ok is True

    page = _run(svc.get_comments("area-1", "ch-1", "art-1"))
    assert page.comment_count == 1
    assert page.items[0].image_list == []
    assert page.items[0].is_article_author is True

    assert svc.calls[2]["body"] == {
        "area": "area-1",
        "channel": "ch-1",
        "articleId": "art-1",
        "content": "reply text",
        "imageList": [],
        "mentionList": [],
        "parentId": "cmt-1",
        "replyId": "cmt-1",
    }
    assert svc.calls[3] == {
        "method": "POST",
        "path": "/uni/area/article/comment/v1/like",
        "params": {
            "area": "area-1",
            "channel": "ch-1",
            "articleId": "art-1",
            "commentId": "cmt-1",
            "liked": "true",
        },
        "body": {
            "area": "area-1",
            "channel": "ch-1",
            "articleId": "art-1",
            "commentId": "cmt-1",
            "liked": True,
        },
    }
    assert svc.calls[4]["params"]["liked"] == "false"
    assert svc.calls[4]["body"]["liked"] is False
    assert svc.calls[5] == {
        "method": "POST",
        "path": "/uni/area/article/comment/v1/delete",
        "params": None,
        "body": {
            "area": "area-1",
            "channel": "ch-1",
            "articleId": "art-1",
            "commentId": "cmt-3",
        },
    }


def test_create_comment_rejects_empty_content_and_images() -> None:
    svc = _RecordingArticle()
    with pytest.raises(ValueError):
        _run(svc.create_comment("area-1", "ch-1", "art-1", "   "))


# ---------------------------------------------------------------------------
# 图片上传预签名 + COS PUT
# ---------------------------------------------------------------------------


def test_upload_image_with_operations_sets_pic_operations_header() -> None:
    svc = _RecordingArticle(
        responses=[
            {
                "expireSecond": 180,
                "url": "https://cos.example/community/area_article/20261124/demo.webp?sig=1",
                "path": "/community/area_article/20261124/demo.webp",
                "hostUrl": "https://resourcecdn.oopz.cn/community/area_article/20261124/demo.webp",
                "auth": "cos-auth-token",
            }
        ],
        raw_responses=[HttpResponse(status_code=200, text="", content=b"", headers={})],
    )

    png_bytes = _make_png_bytes(16, 12)
    att = _run(
        svc.upload_image(
            "area-1",
            "ch-1",
            png_bytes,
            media_type="WEBP",
            operations="imageMogr2/cut/16x12x0x0",
        )
    )

    assert att.attachment_type == "IMAGE"
    assert att.resource == "/community/area_article/20261124/demo.webp"
    assert att.width == 16
    assert att.height == 12
    assert len(svc.raw_calls) == 1
    headers = svc.raw_calls[0]["headers"]
    assert headers["Authorization"] == "cos-auth-token"
    assert headers["Content-Type"] == "image/webp"
    assert json.loads(headers["Pic-Operations"]) == {
        "is_pic_info": 1,
        "rules": [{"fileid": "demo.webp", "rule": "imageMogr2/cut/16x12x0x0"}],
    }


def test_upload_image_raises_on_non_200_cos_response() -> None:
    svc = _RecordingArticle(
        responses=[
            {
                "url": "https://cos.example/upload",
                "path": "/community/area_article/20261124/demo.png",
                "auth": "tok",
            }
        ],
        raw_responses=[HttpResponse(status_code=403, text="AccessDenied", content=b"AccessDenied", headers={})],
    )

    with pytest.raises(OopzApiError):
        _run(svc.upload_image("area-1", "ch-1", _make_png_bytes()))


# ---------------------------------------------------------------------------
# REST / Bot 挂载与顶层导出
# ---------------------------------------------------------------------------


def test_article_service_mounted_on_rest_and_bot() -> None:
    cfg = make_config()
    rest = oopz_sdk.OopzRESTClient(cfg)
    bot = oopz_sdk.OopzBot(cfg)

    assert isinstance(rest.articles, oopz_sdk.Article)
    assert isinstance(bot.articles, oopz_sdk.Article)
    assert bot.articles is bot.rest.articles
    assert hasattr(models, "ArticleInfo")
    assert hasattr(models, "ArticleSection")
    assert hasattr(models, "ArticleComment")


def test_channel_create_and_update_events_parse_article_fields() -> None:
    from oopz_sdk.models.event import ChannelCreateEvent, ChannelUpdateEvent

    create_ev = ChannelCreateEvent.model_validate(
        {
            "event": 25,
            "area": "area-1",
            "channel": "ch-art-1",
            "type": "ARTICLE",
            "name": "攻略区",
            "articleControlEnabled": "true",
            "articleRoles": [101, 102],
            "articleGapSecond": "15",
            "commentGapSecond": 5,
        }
    )
    assert create_ev.channel_type == "ARTICLE"
    assert create_ev.article_control_enabled is True
    assert create_ev.article_roles == [101, 102]
    assert create_ev.article_gap_second == 15
    assert create_ev.comment_gap_second == 5

    update_ev = ChannelUpdateEvent.model_validate(
        {
            "event": 18,
            "area": "area-1",
            "channel": "ch-art-1",
            "type": "ARTICLE",
            "name": "精华区",
            "articleControlEnabled": False,
            "articleRoles": None,
            "articleGapSecond": 30,
            "commentGapSecond": 10,
        }
    )
    assert update_ev.channel_type == "ARTICLE"
    assert update_ev.article_control_enabled is False
    assert update_ev.article_roles == []
    assert update_ev.article_gap_second == 30
    assert update_ev.comment_gap_second == 10


def test_article_models_accept_python_snake_case_kwargs() -> None:
    att = models.ArticleAttachment(
        attachment_type="SHORT_VIDEO",
        resource="/community/area_article/v.mp4",
        cover="/community/area_article/c.webp",
        width=1440,
        height=1080,
        duration=60,
        size=1024,
    )
    assert att.attachment_type == "SHORT_VIDEO"
    assert att.to_request_dict()["attachmentType"] == "SHORT_VIDEO"
    assert att.to_request_dict()["duration"] == 60

    sec = models.ArticleSection(section_id=42, name="分区", sort=2)
    assert sec.section_id == 42

    info = models.ArticleInfo(
        article_id="art-9",
        area_id="area-9",
        channel_id="ch-9",
        section_id=42,
        show_cover=False,
        is_top=True,
    )
    assert info.article_id == "art-9"
    assert info.section_id == 42
    assert info.show_cover is False
    assert info.is_top is True

    page = models.ArticleListPage(items=[info], next_cursor=999, page_size=10)
    assert len(page.items) == 1
    assert page.next_cursor == 999
    assert page.page_size == 10

    cmt = models.ArticleComment(comment_id="c-9", parent_id="p-9", reply_id="r-9", is_article_author=True)
    assert cmt.comment_id == "c-9"
    assert cmt.parent_id == "p-9"
    assert cmt.is_article_author is True


def test_edit_article_preserves_cover_index_and_validates_before_network() -> None:
    svc = _RecordingArticle(
        responses=[
            {
                "articleId": "art-1",
                "title": "原标题",
                "content": "原正文",
                "sectionId": 10,
                "showCover": 1,
                "cover": {
                    "resource": "https://resourcecdn.oopz.cn/community/area_article/b.webp?sign=1",
                    "width": 650,
                    "height": 390,
                },
                "attachments": [
                    {"attachmentType": "IMAGE", "resource": "https://resourcecdn.oopz.cn/community/area_article/a.webp?sign=1", "width": 650, "height": 390},
                    {"attachmentType": "IMAGE", "resource": "https://resourcecdn.oopz.cn/community/area_article/b.webp?sign=2", "width": 650, "height": 390},
                ],
            },
            {"articleId": "art-1", "state": "PUBLISHED"},
        ]
    )

    _run(svc.edit_article("area-1", "ch-1", "art-1", title="改标题"))
    assert svc.calls[1]["body"]["coverIndex"] == 1

    # 无效参数在触发任何网络请求前直接拦截
    svc_bad = _RecordingArticle()
    with pytest.raises(ValueError):
        _run(svc_bad.edit_article("area-1", "ch-1", "art-1", section_id=-1))
    with pytest.raises(TypeError):
        _run(svc_bad.create_article("area-1", "ch-1", "标题", "正文", section_id=True))
    with pytest.raises(TypeError):
        _run(svc_bad.create_article("area-1", "ch-1", "标题", None))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _run(svc_bad.create_article("area-1", "ch-1", "标题", "正文", show_cover="false"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _run(svc_bad.create_article("area-1", "ch-1", "标题", "正文", show_cover=2))
    with pytest.raises(ValueError):
        _run(
            svc_bad.create_article(
                "area-1",
                "ch-1",
                "标题",
                "正文",
                attachments=[models.ArticleAttachment(resource="/community/a.webp")],
                cover_index=1,
            )
        )
    with pytest.raises(TypeError):
        _run(svc_bad.create_comment("area-1", "ch-1", "art-1", image_list="/community/x.webp"))
    with pytest.raises(ValueError):
        _run(svc_bad.create_comment("area-1", "ch-1", "art-1", "hi", parent_id="p1"))
    with pytest.raises(TypeError):
        _run(svc_bad.like_article("area-1", "ch-1", "art-1", liked="true"))  # type: ignore[arg-type]
    assert svc_bad.calls == []


def test_edit_article_full_fields_without_cover_index_skips_detail_fetch() -> None:
    svc = _RecordingArticle(responses=[{"articleId": "art-1", "state": "PUBLISHED"}])
    _run(
        svc.edit_article(
            "area-1",
            "ch-1",
            "art-1",
            title="新标题",
            content="新正文",
            section_id=0,
            attachments=[],
            show_cover=False,
        )
    )
    assert len(svc.calls) == 1
    assert svc.calls[0]["path"] == "/uni/area/article/v1/edit"
    assert svc.calls[0]["body"]["coverIndex"] == 0
    assert svc.calls[0]["body"]["showCover"] == 0


def test_article_models_and_sections_fail_fast_on_invalid_payloads() -> None:
    from pydantic import ValidationError

    # 关键 ID 缺失或为空直接报错，不静默返回空对象
    with pytest.raises(ValidationError):
        models.ArticleSection.from_api({"name": "no-id"})
    with pytest.raises(ValidationError):
        models.ArticleSection.from_api({"id": "not-an-int", "name": "bad"})
    with pytest.raises(ValidationError):
        models.ArticleSection.from_api({"id": True, "name": "bool-id"})
    with pytest.raises(OopzApiError):
        models.ArticlePublishResult.from_api({"articleId": ""})
    with pytest.raises(OopzApiError):
        models.ArticleCommentCreateResult.from_api({"commentId": "  "})
    with pytest.raises(OopzApiError):
        models.ArticlePresignResult.from_api({"url": "", "path": "/a"})

    # 错类型不静默吞掉转默认空值
    with pytest.raises(ValidationError):
        models.ArticleListPage.from_api({"list": "not-a-list"})
    with pytest.raises(ValidationError):
        models.ArticleInfo.from_api({"articleId": "a1", "cover": 123})
    with pytest.raises(ValidationError):
        models.ArticleInfo.from_api({"articleId": "a1", "attachments": "bad"})

    # get_sections 缺少 list 键时直接报错
    svc = _RecordingArticle(responses=[{}])
    with pytest.raises(OopzApiError):
        _run(svc.get_sections("area-1", "ch-1"))


def test_cover_index_without_attachments_must_be_zero() -> None:
    svc = _RecordingArticle()

    with pytest.raises(ValueError):
        _run(svc.create_article("area-1", "ch-1", "标题", "正文", cover_index=1))
    with pytest.raises(ValueError):
        _run(
            svc.edit_article(
                "area-1",
                "ch-1",
                "art-1",
                title="标题",
                content="正文",
                section_id=0,
                attachments=[],
                cover_index=2,
                show_cover=True,
            )
        )
    assert svc.calls == []


def test_edit_article_rejects_cover_index_out_of_range_of_original_attachments() -> None:
    svc = _RecordingArticle(
        responses=[
            {
                "articleId": "art-1",
                "title": "原标题",
                "content": "原正文",
                "attachments": [
                    {"attachmentType": "IMAGE", "resource": "/community/area_article/a.webp", "width": 1, "height": 1}
                ],
            }
        ]
    )

    with pytest.raises(ValueError):
        _run(svc.edit_article("area-1", "ch-1", "art-1", cover_index=1))
    assert [call["path"] for call in svc.calls] == ["/uni/area/article/v1/detail"]


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"image_list": ["/community/area_article/a.webp", "  "]}, ValueError),
        ({"mention_list": [""]}, ValueError),
        ({"mention_list": [123]}, TypeError),
    ],
)
def test_create_comment_rejects_invalid_list_items(kwargs: dict[str, Any], error: type) -> None:
    svc = _RecordingArticle()

    with pytest.raises(error):
        _run(svc.create_comment("area-1", "ch-1", "art-1", "hi", **kwargs))
    assert svc.calls == []


@pytest.mark.parametrize(
    ("media_type", "file_ext", "expected_type", "expected_content_type"),
    [
        (None, "png", "PNG", "image/png"),
        ("webp", "png", "WEBP", "image/webp"),
        ("JPG", "png", "JPG", "image/jpeg"),
    ],
)
def test_upload_image_sets_content_type_from_media_type(
    media_type: str | None, file_ext: str, expected_type: str, expected_content_type: str
) -> None:
    svc = _RecordingArticle(
        responses=[{"url": "https://cos.example/upload", "path": f"/community/area_article/x.{file_ext}", "auth": "tok"}],
        raw_responses=[HttpResponse(status_code=200, text="", content=b"", headers={})],
    )

    _run(svc.upload_image("area-1", "ch-1", _make_png_bytes(), media_type=media_type))

    assert svc.calls[0]["body"]["mediaType"] == expected_type
    assert svc.raw_calls[0]["headers"]["Content-Type"] == expected_content_type


def test_upload_image_rejects_non_image_media_type_before_network() -> None:
    svc = _RecordingArticle()

    with pytest.raises(ValueError):
        _run(svc.upload_image("area-1", "ch-1", _make_png_bytes(), media_type="MP4"))
    assert svc.calls == []
    assert svc.raw_calls == []


def test_show_cover_type_and_value_errors() -> None:
    svc = _RecordingArticle()

    with pytest.raises(TypeError):
        _run(svc.create_article("area-1", "ch-1", "标题", "正文", show_cover="1"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _run(svc.create_article("area-1", "ch-1", "标题", "正文", show_cover=-1))
    assert svc.calls == []
