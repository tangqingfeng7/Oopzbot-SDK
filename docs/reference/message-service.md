# Message Service

入口：`client.messages` 或 `bot.messages`。

## `open_private_session(target)`

打开或创建与指定用户的私信会话。

```python
session = await client.messages.open_private_session(target="用户 UID")
print(session.session_id)
```

| 参数 | 说明 |
| --- | --- |
| `target` | 目标用户 UID，不能为空。 |

返回：`PrivateSession`。

## `send_message(*texts, area, channel, ...)`

发送频道消息。

```python
result = await client.messages.send_message(
    "hello",
    area="域 ID",
    channel="频道 ID",
)
```

常用参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `*texts` | `str | Segment` | 文本或 Segment 列表。 |
| `area` | `str` | 域 ID，必填。 |
| `channel` | `str` | 频道 ID，必填。 |
| `attachments` | `list | None` | 手动附件列表；不能与 Segment 方式混用。 |
| `mention_list` | `list | None` | 手动 mention 列表。 |
| `is_mention_all` | `bool` | 是否艾特全体。 |
| `style_tags` | `list | None` | 样式标签；例如 `IMPORTANT`。 |
| `reference_message_id` | `str | None` | 被回复消息 ID。 |
| `auto_recall` | `bool | None` | 单条消息自动撤回覆盖。 |
| `animated` | `bool` | 附件动画标记。 |
| `display_name` | `str` | 展示名。 |
| `duration` | `int` | 媒体时长。 |
| `version` | `"v1" | "v2"` | 发送接口版本，默认 `v2`。 |

返回：`MessageSendResult`。

## `send_private_message(*texts, target, channel=None, ...)`

发送私信。

```python
await client.messages.send_private_message("你好", target="用户 UID")
```

| 参数 | 说明 |
| --- | --- |
| `target` | 目标用户 UID，必填。 |
| `channel` | 私信会话 ID；不传时自动调用 `open_private_session()`。 |

其余消息参数与 `send_message()` 基本一致。返回 `MessageSendResult`。

## `recall_message(message_id, area, channel, timestamp=None, target="")`

撤回频道消息。

```python
await client.messages.recall_message(message_id, area=area, channel=channel)
```

| 参数 | 说明 |
| --- | --- |
| `message_id` | Oopz 消息 ID。 |
| `area` | 域 ID。 |
| `channel` | 频道 ID。 |
| `timestamp` | 可选时间戳。 |
| `target` | 可选目标。 |

返回：`OperationResult`。

## `recall_private_message(message_id, channel, target, timestamp=None)`

撤回私信消息。私信撤回需要私信会话 `channel` 与 `target`。

返回：`OperationResult`。

## `get_channel_messages(channel, area, ...)`

获取频道历史消息。适合初始化缓存或调试消息解析。具体分页参数以当前 SDK 函数签名为准。

## `top_message(message_id, channel, area, top_message=True)`

置顶或取消置顶频道消息。

```python
await client.messages.top_message(message_id, channel=channel, area=area, top_message=True)
await client.messages.top_message(message_id, channel=channel, area=area, top_message=False)
```

返回：`OperationResult`。

## Segment 发送建议

使用 `Image.from_file()` 时 SDK 会：

1. 读取图片宽高。
2. 上传本地图片。
3. 生成 Oopz 图片占位文本 `![IMAGEw{width}h{height}]({file_key})`。
4. 生成附件列表。

```python
from oopz_sdk.models.segment import Text, Image

await bot.messages.send_message(
    Text("图片：\n"),
    Image.from_file("./a.png"),
    area=area,
    channel=channel,
)
```
