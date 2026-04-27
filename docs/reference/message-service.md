# Message Service

`Message Service` 用于发送频道消息、发送私信、打开私信会话、撤回消息、获取频道历史消息和置顶消息。

入口：

```python
client.messages
bot.messages
```

---

## `open_private_session(target)`

打开或创建与指定用户的私信会话。

```python
session = await client.messages.open_private_session(target="用户 UID")
print(session.session_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `target` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`PrivateSession`。

    对应模型：`oopz_sdk.models.PrivateSession`

    | 字段 | 类型 | 默认值 | API 字段 | 说明 |
    | --- | --- | --- | --- | --- |
    | `uid` | `str` | `""` | `uid` | 对方用户 UID。 |
    | `last_time` | `str` | `""` | `lastTime` | 会话最后更新时间。 |
    | `mute` | `bool` | `False` | `mute` | 当前私信会话是否静音。 |
    | `session_id` | `str` | `""` | `sessionId` | 私信会话 ID。发送私信或撤回私信时会用到。 |

---

## `send_message(*texts, area, channel, ...)`

发送频道消息。

```python
result = await client.messages.send_message(
    "hello",
    area="域 ID",
    channel="频道 ID",
)

print(result.message_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `*texts` | `str | Segment` | 是 | - | 文本或 Segment 列表。多个参数会被合并为一条消息 |
    | `area` | `str` | 是 | - | 域 ID，不能为空 |
    | `channel` | `str` | 是 | - | 频道 ID，不能为空 |
    | `attachments` | `list | None` | 否 | `None` | 手动附件列表；不能与 Segment 方式混用 |
    | `mention_list` | `list | None` | 否 | `None` | 手动 mention 列表 |
    | `is_mention_all` | `bool` | 否 | `False` | 是否at全体 |
    | `style_tags` | `list | None` | 否 | `None` | 样式标签，例如 `IMPORTANT` |
    | `reference_message_id` | `str | None` | 否 | `None` | 被回复消息 ID |
    | `auto_recall` | `bool | None` | 否 | `None` | 单条消息自动撤回 |
    | `animated` | `bool` | 否 | `False` |  |
    | `display_name` | `str` | 否 | `""` | 展示名 |
    | `duration` | `int` | 否 | `0` | 媒体时长 |
    | `version` | `"v1" | "v2"` | 否 | `"v2"` | 发送接口版本 |

=== "返回值"

    返回：`MessageSendResult`。

    对应模型：`oopz_sdk.models.MessageSendResult`

    | 字段 | 类型 | 默认值 | API 字段 | 说明 |
    | --- | --- | --- | --- | --- |
    | `message_id` | `str` | 无 | `messageId` | Oopz 消息 ID。撤回、置顶、回复时通常会用到。 |
    | `timestamp` | `str` | `""` | `timestamp` | 消息时间戳。 |

=== "Segment 示例"

    ```python
    from oopz_sdk.models.segment import Text, Image

    result = await bot.messages.send_message(
        Text("图片：\n"),
        Image("./a.png"),
        area=area,
        channel=channel,
    )

    print(result.message_id)
    ```

=== "说明"

    `send_message()` 会先把 `str` 或 `Segment` 统一处理成 Oopz 消息内容。

    如果传入的是普通字符串：

    ```python
    await bot.messages.send_message(
        "hello",
        area=area,
        channel=channel,
    )
    ```

    SDK 会直接发送文本消息。

    如果传入的是 `Image` 这类 Segment，SDK 会先上传本地文件，再生成 Oopz 需要的图片占位文本和附件信息。

---

## `send_private_message(*texts, target, channel=None, ...)`

发送私信。

如果没有传入 `channel`，SDK 会先调用 `open_private_session(target)` 打开或创建私信会话，然后再发送消息。

```python
result = await client.messages.send_private_message(
    "你好",
    target="用户 UID",
)

print(result.message_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `*texts` | `str | Segment` | 是 | - | 文本或 Segment 列表。 |
    | `target` | `str` | 是 | - | 目标用户 UID，不能为空。 |
    | `channel` | `str | None` | 否 | `None` | 私信会话 ID；不传时自动调用 `open_private_session()`。 |
    | `attachments` | `list | None` | 否 | `None` | 手动附件列表；不能与 Segment 方式混用。 |
    | `mention_list` | `list | None` | 否 | `None` | 手动 mention 列表。 |
    | `is_mention_all` | `bool` | 否 | `False` | 是否at全体。 |
    | `style_tags` | `list | None` | 否 | `None` | 样式标签。 |
    | `reference_message_id` | `str \| None` | 否 | `None` | 被回复消息 ID。 |
    | `auto_recall` | `bool | None` | 否 | `None` | 单条消息自动撤回覆盖。 |
    | `animated` | `bool` | 否 | `False` | 附件动画标记。 |
    | `display_name` | `str` | 否 | `""` | 展示名。 |
    | `duration` | `int` | 否 | `0` | 媒体时长。 |
    | `version` | `"v1" | "v2"` | 否 | `"v2"` | 发送接口版本。 |

=== "返回值"

    返回：`MessageSendResult`。

    对应模型：`oopz_sdk.models.MessageSendResult`

    | 字段 | 类型 | 默认值 | API 字段 | 说明 |
    | --- | --- | --- | --- | --- |
    | `message_id` | `str` | 无 | `messageId` | Oopz 消息 ID。 |
    | `timestamp` | `str` | `""` | `timestamp` | 消息时间戳。 |

=== "指定私信会话"

    如果你已经通过 `open_private_session()` 获取过私信会话 ID，可以直接传入 `channel`。

    ```python
    session = await client.messages.open_private_session(target="用户 UID")

    result = await client.messages.send_private_message(
        "你好",
        target="用户 UID",
        channel=session.session_id,
    )
    ```

---

##  `recall_message(message_id, area, channel, timestamp=None, target="")`

撤回频道消息。

```python
result = await client.messages.recall_message(
    message_id,
    area=area,
    channel=channel,
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `message_id` | `str` | 是 | - | Oopz 消息 ID，不能为空。 |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `channel` | `str` | 是 | - | 频道 ID，不能为空。 |
    | `timestamp` | `str | int | float | None` | 否 | `None` | 可选时间戳；不传时 SDK 自动生成当前微秒时间戳。 |
    | `target` | `str` | 否 | `""` | 可选目标。频道消息此处应留空。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

=== "说明"

    频道消息撤回需要同时知道：

    - `message_id`
    - `area`
    - `channel`

---

## `recall_private_message(message_id, channel, target, timestamp=None)`

撤回私信消息。

私信撤回需要私信会话 `channel` 与目标用户 `target`。

```python
result = await client.messages.recall_private_message(
    message_id,
    channel="私信会话 ID",
    target="用户 UID",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `message_id` | `str` | 是 | - | Oopz 消息 ID，不能为空。 |
    | `channel` | `str` | 是 | - | 私信会话 ID，不能为空。 |
    | `target` | `str` | 是 | - | 目标用户 UID，不能为空。(See `open_private_session()`) |
    | `timestamp` | `str | int | float | None` | 否 | `None` | 可选时间戳；不传时 SDK 自动生成当前微秒时间戳。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## `get_channel_messages(channel, area, ...)`

获取频道历史消息。

```python
messages = await client.messages.get_channel_messages(
    channel=channel,
    area=area,
)

for message in messages:
    print(message.message_id, message.text)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `channel` | `str` | 是 | 频道 ID，不能为空。 |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `...` | - | 否 | 具体分页参数以当前 SDK 函数签名为准。 |

=== "返回值"

    返回：`list[Message]`。

    对应模型：`oopz_sdk.models.Message`

    | 字段 | 类型 | 默认值 | API 字段 | 说明 |
    | --- | --- | --- | --- | --- |
    | `target` | `str` | `""` | `target` | 目标用户或目标对象。 |
    | `area` | `str` | `""` | `area` | 域 ID。 |
    | `area_page` | `str` | `""` | `areaPage` | 域分页或页面信息。 |
    | `area_count` | `int` | `0` | `areaCount` | 域相关计数。 |
    | `channel` | `str` | `""` | `channel` | 频道 ID。 |
    | `message_type` | `str` | `""` | `type` | 消息类型，例如文本、图片等。 |
    | `client_message_id` | `str` | `""` | `clientMessageId` | 客户端消息 ID。 |
    | `message_id` | `str` | `""` | `messageId` | Oopz 消息 ID。 |
    | `timestamp` | `str` | `""` | `timestamp` | 消息时间戳。 |
    | `sender_id` | `str` | `""` | `person` | 发送者 UID。 |
    | `content` | `str` | `""` | `content` | 原始消息内容。 |
    | `text` | `str` | `""` | `text` | 文本内容。 |
    | `edit_time` | `int` | `0` | `editTime` | 编辑时间。 |
    | `top_time` | `str` | `""` | `topTime` | 置顶时间。 |
    | `duration` | `int` | `0` | `duration` | 媒体时长。 |
    | `display_name` | `str` | `""` | `displayName` | 展示名。 |
    | `preview_image` | `MediaInfo | None` | `None` | `previewImage` | 预览图信息。 |
    | `raw_video` | `MediaInfo | None` | `None` | `rawVideo` | 原始视频信息。 |
    | `cards` | `Any` | `None` | `cards` | 卡片数据。 |
    | `mention_list` | `list[MentionInfo]` | `[]` | `mentionList` | at列表。 |
    | `is_mention_all` | `bool` | `False` | `isMentionAll` | 是否at全体。 |
    | `sender_is_bot` | `bool` | `False` | `senderIsBot` | 发送者是否为机器人。 |
    | `sender_bot_type` | `str` | `""` | `senderBotType` | 发送者机器人类型。 |
    | `style_tags` | `list[Any]` | `[]` | `styleTags` | 样式标签。 |
    | `reference_message` | `Any` | `None` | `referenceMessage` | 被引用消息对象。 |
    | `reference_message_id` | `str` | `""` | `referenceMessageId` | 被引用消息 ID。 |
    | `attachments` | `list[Attachment]` | `[]` | `attachments` | 附件列表。 |

=== "说明"

    `get_channel_messages()` 会把接口返回的消息项转换成 `Message` 模型。

    如果你只是想监听实时消息，通常不需要主动调用这个方法。监听消息可以使用：

    ```python
    @bot.on_message
    async def handle_message(message, ctx):
        print(message.text)
    ```

---

## `top_message(message_id, channel, area, top_message=True)`

置顶或取消置顶频道消息。

```python
await client.messages.top_message(
    message_id,
    channel=channel,
    area=area,
    top_message=True,
)

await client.messages.top_message(
    message_id,
    channel=channel,
    area=area,
    top_message=False,
)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `message_id` | `str` | 是 | - | Oopz 消息 ID，不能为空。 |
    | `channel` | `str` | 是 | - | 频道 ID，不能为空。 |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `top_message` | `bool` | 否 | `True` | `True` 表示置顶，`False` 表示取消置顶。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## Segment 发送建议

使用 `Image` 时 SDK 会：

1. 读取图片宽高。
2. 上传本地图片。
3. 生成 Oopz 图片占位文本 `![IMAGEw{width}h{height}]({file_key})`。
4. 生成附件列表。
5. 与send_message()的其他文本参数合并成完整消息内容。

=== "示例"

    ```python
    from oopz_sdk.models.segment import Text, Image

    await bot.messages.send_message(
        Text("图片：\n"),
        Image("./a.png"),
        area=area,
        channel=channel,
    )
    ```

=== "为什么推荐 Segment"

    Segment 方式更适合 SDK 用户，因为它可以隐藏底层 Oopz 消息格式。

    例如图片消息底层需要同时处理：

    - 图片占位文本
    - 附件列表
    - 图片宽高
    - 文件上传结果

    使用 `Image` 时，这些步骤会由 SDK 自动完成。

=== "注意事项"

    同时使用Segment 和手动 `attachments`是不被允许的，因为这会导致消息内容和附件列表不一致，SDK 无法正确处理。

    例如下面这种写法应该避免：

    ```python
    await bot.messages.send_message(
        Image.from_file("./a.png"),
        attachments=[...],
        area=area,
        channel=channel,
    )
    ```

    因为 SDK 无法明确判断附件应该来自 Segment 还是手动参数。