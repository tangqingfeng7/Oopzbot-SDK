# Article Service

`Article Service` 挂载在 `client.articles` / `bot.articles`，用于管理帖子频道、分区、媒体上传、帖子 CRUD、帖子点赞，以及帖子评论、回复、点赞与删除。

---

## 帖子频道管理

以下三个方法内部委托给 [Channel Service](channel-service.md)，也可直接通过 `client.channels` 调用。

### `create_channel(area, name, group_id="", *, secret=False)`

创建帖子频道（`ChannelType.ARTICLE`）。不传 `group_id` 时自动使用该域下的第一个频道分组。

```python
ch = await client.articles.create_channel(
    area="域 ID",
    name="攻略交流区",
)

print(ch.channel_id)
print(ch.channel_type)  # ChannelType.ARTICLE
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `name` | `str` | 是 | - | 频道名称，不能为空。 |
    | `group_id` | `str` | 否 | `""` | 频道分组 ID；不传时自动取第一个分组。 |
    | `secret` | `bool` | 否 | `False` | 是否创建为私密帖子频道。 |

=== "返回值"

    返回：`CreateChannelResult`（`oopz_sdk.models.CreateChannelResult`），字段定义见 [Channel Service](channel-service.md)。

---

### `update_channel(area, channel_id, **kwargs)`

修改帖子频道设置。SDK 会先拉取原频道配置，仅覆盖你传入的字段。

```python
result = await client.articles.update_channel(
    area="域 ID",
    channel_id="帖子频道 ID",
    name="精华攻略",
    article_gap_second=10,
    comment_gap_second=5,
    article_control_enabled=True,
    article_roles=[26480728],
)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `channel_id` | `str` | 是 | - | 帖子频道 ID，不能为空。 |
    | `name` | `str \| None` | 否 | `None` | 频道名称。 |
    | `article_gap_second` | `int \| None` | 否 | `None` | 发帖间隔秒数。 |
    | `comment_gap_second` | `int \| None` | 否 | `None` | 评论间隔秒数。 |
    | `text_gap_second` | `int \| None` | 否 | `None` | 文字消息间隔秒数。 |
    | `article_control_enabled` | `bool \| None` | 否 | `None` | 是否启用发帖身份组控制。 |
    | `article_roles` | `list[int] \| None` | 否 | `None` | 允许发帖的身份组 ID 列表。 |
    | `text_control_enabled` | `bool \| None` | 否 | `None` | 是否启用文字控制。 |
    | `text_roles` | `list[int] \| None` | 否 | `None` | 文字控制身份组 ID 列表。 |
    | `access_control_enabled` | `bool \| None` | 否 | `None` | 是否启用访问控制。 |
    | `secret` | `bool \| None` | 否 | `None` | 是否设为私密频道。 |
    | `has_password` | `bool \| None` | 否 | `None` | 是否启用密码。 |
    | `password` | `str \| None` | 否 | `None` | 频道密码（需同时传 `has_password=True`）。 |
    | `accessible_roles` | `list[int] \| None` | 否 | `None` | 可访问身份组 ID 列表（仅私密频道）。 |
    | `accessible_members` | `list[str] \| None` | 否 | `None` | 可访问成员 UID 列表（仅私密频道）。 |

=== "返回值"

    返回：`OperationResult`（`oopz_sdk.models.OperationResult`）。

---

### `delete_channel(area, channel)`

删除帖子频道。

```python
result = await client.articles.delete_channel(
    area="域 ID",
    channel="帖子频道 ID",
)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `channel` | `str` | 是 | 帖子频道 ID，不能为空。 |

=== "返回值"

    返回：`OperationResult`（`oopz_sdk.models.OperationResult`）。

---

## 分区管理

### `get_sections(area, channel)`

获取帖子频道下的全部分区列表。

```python
sections = await client.articles.get_sections(area="域 ID", channel="帖子频道 ID")
for sec in sections:
    print(sec.section_id, sec.name, sec.sort)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID。 |
    | `channel` | `str` | 是 | 帖子频道 ID。 |

=== "返回值"

    返回：`list[ArticleSection]`（`oopz_sdk.models.ArticleSection`）。

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `section_id` | `int` | `0` | 分区 ID。 |
    | `name` | `str` | `""` | 分区名称。 |
    | `sort` | `int` | `0` | 排序序号。 |

---

### `create_section(area, channel, name)`

在帖子频道中新增分区。

```python
sec = await client.articles.create_section(
    area="域 ID",
    channel="帖子频道 ID",
    name="新手指南",
)
print(sec.section_id, sec.name)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID。 |
    | `channel` | `str` | 是 | 帖子频道 ID。 |
    | `name` | `str` | 是 | 分区名称，不能为空。 |

=== "返回值"

    返回：`ArticleSection`（`oopz_sdk.models.ArticleSection`）。

---

### `edit_section(area, channel, section_id, name)`

修改分区名称。

```python
sec = await client.articles.edit_section(
    area="域 ID",
    channel="帖子频道 ID",
    section_id=3024,
    name="进阶攻略",
)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID。 |
    | `channel` | `str` | 是 | 帖子频道 ID。 |
    | `section_id` | `int` | 是 | 分区 ID，必须为正整数。 |
    | `name` | `str` | 是 | 新分区名称，不能为空。 |

=== "返回值"

    返回：`ArticleSection`（`oopz_sdk.models.ArticleSection`）。

---

### `delete_section(area, channel, section_id)`

删除分区。

```python
result = await client.articles.delete_section(
    area="域 ID",
    channel="帖子频道 ID",
    section_id=3024,
)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID。 |
    | `channel` | `str` | 是 | 帖子频道 ID。 |
    | `section_id` | `int` | 是 | 分区 ID，必须为正整数。 |

=== "返回值"

    返回：`OperationResult`（`oopz_sdk.models.OperationResult`）。

---

## 媒体预签名与图片上传

### `get_upload_presign(area, channel, *, media_type="WEBP", operations=None)`

获取帖子/评论媒体上传到 COS 所需的预签名地址与资源路径。

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `media_type` | `str` | 否 | `"WEBP"` | 媒体类型，例如 `"WEBP"`、`"PNG"`、`"JPG"`、`"MP4"`。 |
    | `operations` | `str \| None` | 否 | `None` | 可选腾讯云数据万象图片裁剪规则（如 `"imageMogr2/cut/635x379x17x0"`）。 |

=== "返回值"

    返回：`ArticlePresignResult`（`oopz_sdk.models.ArticlePresignResult`）。

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `expire_second` | `int` | `180` | 预签名有效秒数。 |
    | `url` | `str` | `""` | COS `PUT` 上传地址。 |
    | `path` | `str` | `""` | 提交给发帖/评论接口的相对资源路径。 |
    | `host_url` | `str` | `""` | 带 CDN 域名的访问 URL。 |
    | `auth` | `str` | `""` | COS `Authorization` 签名头。 |

---

### `upload_image(area, channel, file, *, media_type=None, operations=None)`

一步完成预签名与图片上传，返回可直接用于 `create_article` / `edit_article` / `create_comment` 的 `ArticleAttachment`。

```python
att = await client.articles.upload_image(
    area="域 ID",
    channel="帖子频道 ID",
    file="cover.png",
)
print(att.resource, att.width, att.height)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `file` | `ImageInput` | 是 | - | 本地路径、`Path`、`bytes`、base64 / data URL 或 file-like 对象。 |
    | `media_type` | `str \| None` | 否 | `None` | 媒体类型；不传时按文件内容自动推断。 |
    | `operations` | `str \| None` | 否 | `None` | 可选图片裁剪规则；传入时会自动附带 `Pic-Operations` 请求头。 |

=== "返回值"

    返回：`ArticleAttachment`（`oopz_sdk.models.ArticleAttachment`）。

---

## 帖子管理

### `get_articles(area, channel, *, section_id=0, cursor=0, cursor_state="")`

获取帖子列表。

```python
page = await client.articles.get_articles(
    area="域 ID",
    channel="帖子频道 ID",
    section_id=0,
)
for item in page.items:
    print(item.article_id, item.title, item.state)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `section_id` | `int` | 否 | `0` | `0` 表示全部，`-1` 表示“我的”，正整数表示具体分区 ID。 |
    | `cursor` | `int` | 否 | `0` | 分页游标，首页传 `0`。 |
    | `cursor_state` | `str` | 否 | `""` | 翻页状态游标（例如 `"PUBLISHED"`），一般取上一页返回的 `next_cursor_state`。 |

=== "返回值"

    返回：`ArticleListPage`（`oopz_sdk.models.ArticleListPage`）。

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `items` | `list[ArticleInfo]` | `[]` | 当前页帖子列表。 |
    | `next_cursor` | `int` | `0` | 下一页游标。 |
    | `next_cursor_state` | `str` | `""` | 下一页状态游标。 |
    | `page_size` | `int` | `20` | 每页大小。 |

---

### `get_article_detail(area, channel, article_id)`

获取单篇帖子详情。

```python
detail = await client.articles.get_article_detail(
    area="域 ID",
    channel="帖子频道 ID",
    article_id="帖子 ID",
)
print(detail.title, detail.section_id, detail.show_cover)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID。 |
    | `channel` | `str` | 是 | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | 帖子 ID。 |

=== "返回值"

    返回：`ArticleInfo`（`oopz_sdk.models.ArticleInfo`）。

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `article_id` | `str` | `""` | 帖子 ID。 |
    | `area_id` | `str` | `""` | 所属域 ID。 |
    | `channel_id` | `str` | `""` | 所属帖子频道 ID。 |
    | `section_id` | `int` | `0` | 所属分区 ID，`0` 表示无分区。 |
    | `title` | `str` | `""` | 帖子标题。 |
    | `summary` | `str` | `""` | 摘要。 |
    | `content` | `str` | `""` | 正文内容（可含图片/视频 Markdown 占位语法）。 |
    | `cover` | `ArticleCover \| None` | `None` | 封面信息。 |
    | `author_uid` | `str` | `""` | 作者 UID。 |
    | `like_count` | `int` | `0` | 点赞数。 |
    | `liked` | `bool` | `False` | 当前账号是否已点赞。 |
    | `comment_count` | `int` | `0` | 评论数。 |
    | `watch_count` | `int` | `0` | 浏览数。 |
    | `is_top` | `bool` | `False` | 是否置顶。 |
    | `state` | `str` | `""` | 帖子状态（如 `"AUDITING"`、`"PUBLISHED"`）。 |
    | `show_cover` | `bool` | `True` | 是否在帖子详情内显示封面。 |
    | `attachments` | `list[ArticleAttachment]` | `[]` | 附件列表。 |
    | `ip_address` | `str` | `""` | IP 属地。 |
    | `publish_time` / `created_at` / `updated_at` | `int` | `0` | 毫秒级时间戳。 |

---

### `create_article(area, channel, title, content, *, section_id=0, attachments=None, cover_index=0, show_cover=True)`

发布帖子。支持指定发布到的分区（`section_id`）以及是否在帖子内显示封面（`show_cover`）。

```python
img = await client.articles.upload_image(area, channel, "cover.png")
post = await client.articles.create_article(
    area=area,
    channel=channel,
    title="版本更新公告",
    content="正文内容...",
    section_id=3024,
    attachments=[img],
    cover_index=0,
    show_cover=False,  # 帖子内不显示封面
)
print(post.article_id, post.state)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `title` | `str` | 是 | - | 帖子标题，不能为空。 |
    | `content` | `str` | 是 | - | 帖子正文。 |
    | `section_id` | `int` | 否 | `0` | 发布到的分区 ID，`0` 表示不指定分区。 |
    | `attachments` | `Sequence[ArticleAttachment \| Mapping] \| None` | 否 | `None` | 附件列表（通过 `upload_image` 获取）。 |
    | `cover_index` | `int` | 否 | `0` | 作为封面的附件索引。 |
    | `show_cover` | `bool \| int` | 否 | `True` | 是否在帖子详情内显示封面（`True`/`1` 显示，`False`/`0` 不显示）。 |

=== "返回值"

    返回：`ArticlePublishResult`（`oopz_sdk.models.ArticlePublishResult`）。

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `article_id` | `str` | `""` | 新发布帖子的 ID。 |
    | `state` | `str` | `""` | 审核/发布状态（通常刚发布为 `"AUDITING"`，审核通过后为 `"PUBLISHED"`）。 |

---

### `edit_article(area, channel, article_id, *, title=None, content=None, section_id=None, attachments=None, cover_index=None, show_cover=None)`

编辑帖子。支持局部更新：如果有未传入的字段，SDK 会先调用 `get_article_detail` 拉取原帖内容保持不变，并自动将原附件的签名 CDN URL 归一为接口所需的相对资源路径；若所有字段均已显式传入，则直接提交修改。

```python
result = await client.articles.edit_article(
    area=area,
    channel=channel,
    article_id=post.article_id,
    title="修改后的标题",
    show_cover=True,
)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | - | 帖子 ID。 |
    | `title` | `str \| None` | 否 | `None` | 新标题；不传保留原值。 |
    | `content` | `str \| None` | 否 | `None` | 新正文；不传保留原值。 |
    | `section_id` | `int \| None` | 否 | `None` | 新分区 ID；不传保留原值。 |
    | `attachments` | `Sequence[ArticleAttachment \| Mapping] \| None` | 否 | `None` | 新附件列表；不传保留原附件。 |
    | `cover_index` | `int \| None` | 否 | `None` | 封面附件索引，默认 `0`。 |
    | `show_cover` | `bool \| int \| None` | 否 | `None` | 帖子内是否显示封面；不传保留原值。 |

=== "返回值"

    返回：`ArticlePublishResult`（`oopz_sdk.models.ArticlePublishResult`）。

---

### `delete_article(area, channel, article_id)`

删除帖子。

```python
result = await client.articles.delete_article(area, channel, article_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID。 |
    | `channel` | `str` | 是 | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | 帖子 ID。 |

=== "返回值"

    返回：`OperationResult`（`oopz_sdk.models.OperationResult`）。

---

### `like_article(area, channel, article_id, *, liked=True)` / `unlike_article(area, channel, article_id)`

点赞或取消点赞帖子。

```python
await client.articles.like_article(area, channel, article_id)
await client.articles.unlike_article(area, channel, article_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | - | 帖子 ID。 |
    | `liked` | `bool` | 否 | `True` | `True` 点赞，`False` 取消点赞（`unlike_article` 固定为 `False`）。 |

=== "返回值"

    返回：`OperationResult`（`oopz_sdk.models.OperationResult`）。

---

### `get_article_likes(area, channel, article_id, *, cursor=0, page_size=20)`

获取帖子点赞用户列表。

```python
likes = await client.articles.get_article_likes(area, channel, article_id)
print(likes.like_count, [u.uid for u in likes.items])
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | - | 帖子 ID。 |
    | `cursor` | `int` | 否 | `0` | 分页游标。 |
    | `page_size` | `int` | 否 | `20` | 每页数量。 |

=== "返回值"

    返回：`ArticleLikeListPage`（`oopz_sdk.models.ArticleLikeListPage`）。

---

## 评论管理

### `get_comments(area, channel, article_id, *, cursor=0, page_size=30)`

获取帖子评论列表。

```python
page = await client.articles.get_comments(area, channel, article_id)
for comment in page.items:
    print(comment.comment_id, comment.uid, comment.content)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | - | 帖子 ID。 |
    | `cursor` | `int` | 否 | `0` | 分页游标。 |
    | `page_size` | `int` | 否 | `30` | 每页数量。 |

=== "返回值"

    返回：`ArticleCommentListPage`（`oopz_sdk.models.ArticleCommentListPage`）。

---

### `create_comment(area, channel, article_id, content="", *, image_list=None, mention_list=None, parent_id="", reply_id="")`

发表帖子评论（支持纯文字、纯图片或图文评论；传入 `parent_id`/`reply_id` 时为回复评论）。

```python
# 文字评论
c1 = await client.articles.create_comment(area, channel, article_id, "写得不错！")

# 带图评论
img = await client.articles.upload_image(area, channel, "comment.png")
c2 = await client.articles.create_comment(area, channel, article_id, image_list=[img.resource])
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | - | 帖子 ID。 |
    | `content` | `str` | 否 | `""` | 评论文本；`content` 与 `image_list` 不能同时为空。 |
    | `image_list` | `Sequence[str] \| None` | 否 | `None` | 图片资源路径列表（如 `att.resource`）。 |
    | `mention_list` | `Sequence[str] \| None` | 否 | `None` | 被 @ 的用户 UID 列表。 |
    | `parent_id` | `str` | 否 | `""` | 父评论（一级评论）ID。 |
    | `reply_id` | `str` | 否 | `""` | 被回复的目标评论 ID。 |

=== "返回值"

    返回：`ArticleCommentCreateResult`（`oopz_sdk.models.ArticleCommentCreateResult`）。

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `comment_id` | `str` | `""` | 新评论 ID。 |
    | `ip_address` | `str` | `""` | IP 属地。 |

---

### `reply_comment(area, channel, article_id, parent_id, content="", *, reply_id=None, image_list=None, mention_list=None)`

回复指定评论的便捷方法。未传 `reply_id` 时默认与 `parent_id` 相同（回复一级评论）；回复楼中楼子评论时可传入具体的 `reply_id`。

```python
reply = await client.articles.reply_comment(
    area=area,
    channel=channel,
    article_id=article_id,
    parent_id=c1.comment_id,
    content="同意楼上",
)
```

=== "返回值"

    返回：`ArticleCommentCreateResult`（`oopz_sdk.models.ArticleCommentCreateResult`）。

---

### `delete_comment(area, channel, article_id, comment_id)`

删除帖子评论。

```python
result = await client.articles.delete_comment(area, channel, article_id, comment_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID。 |
    | `channel` | `str` | 是 | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | 帖子 ID。 |
    | `comment_id` | `str` | 是 | 评论 ID。 |

=== "返回值"

    返回：`OperationResult`（`oopz_sdk.models.OperationResult`）。

---

### `like_comment(area, channel, article_id, comment_id, *, liked=True)` / `unlike_comment(area, channel, article_id, comment_id)`

点赞或取消点赞评论。

```python
await client.articles.like_comment(area, channel, article_id, comment_id)
await client.articles.unlike_comment(area, channel, article_id, comment_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID。 |
    | `channel` | `str` | 是 | - | 帖子频道 ID。 |
    | `article_id` | `str` | 是 | - | 帖子 ID。 |
    | `comment_id` | `str` | 是 | - | 评论 ID。 |
    | `liked` | `bool` | 否 | `True` | `True` 点赞，`False` 取消点赞（`unlike_comment` 固定为 `False`）。 |

=== "返回值"

    返回：`OperationResult`（`oopz_sdk.models.OperationResult`）。

---

## 完整示例

```python
async with OopzRESTClient(config) as client:
    await client.start()

    # 1. 创建并配置帖子频道与分区
    ch = await client.articles.create_channel(area, "活动专区")
    await client.articles.update_channel(area, ch.channel_id, article_gap_second=10)
    sec = await client.articles.create_section(area, ch.channel_id, "官方公告")

    # 2. 上传封面并发布帖子（不显示帖内封面）
    cover = await client.articles.upload_image(area, ch.channel_id, "banner.webp")
    post = await client.articles.create_article(
        area,
        ch.channel_id,
        "新活动上线",
        "活动详情内容...",
        section_id=sec.section_id,
        attachments=[cover],
        show_cover=False,
    )

    # 3. 局部编辑帖子、点赞与评论
    await client.articles.edit_article(area, ch.channel_id, post.article_id, show_cover=True)
    await client.articles.like_article(area, ch.channel_id, post.article_id)
    c1 = await client.articles.create_comment(area, ch.channel_id, post.article_id, "支持！")
    c2 = await client.articles.reply_comment(area, ch.channel_id, post.article_id, c1.comment_id, "谢谢参与")

    # 4. 清理
    await client.articles.delete_comment(area, ch.channel_id, post.article_id, c2.comment_id)
    await client.articles.delete_article(area, ch.channel_id, post.article_id)
    await client.articles.delete_section(area, ch.channel_id, sec.section_id)
    await client.articles.delete_channel(area, ch.channel_id)
```
