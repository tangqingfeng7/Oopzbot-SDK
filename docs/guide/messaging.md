from oopz_sdk.utils.image import get_image_info

# 消息发送

本页适合你已经跑通 [5 分钟上手](quickstart.md)，并且想发送文本、图片、私信、回复或撤回消息。

消息能力由 `bot.messages` 或者根据会话由 `context` 提供。频道消息、私信、撤回、置顶、历史消息拉取都在 Message Service
`oopz_sdk.services.message` 中。

## 发送频道文本

bot实例中已经暴露所有service对象，我们可以使用 `bot.messages.send_message()` 发送频道消息：

`area` 和 `channel` 必填；为空会抛出 `ValueError`。

```python
import asyncio

from oopz_sdk import OopzBot, OopzConfig
from oopz_sdk.events import EventContext
from oopz_sdk.models import Message

bot = OopzBot(OopzConfig(
    device_id="你的设备 ID",
    person_uid="机器人账号 UID",
    jwt_token="登录态 JWT",
    private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
))


@bot.on_message
async def handle_message(message: Message, ctx: EventContext):
    area = message.area  # 域 ID
    channel = message.channel  # 频道 ID
    text = message.text  # 消息文本
    await bot.messages.send_message(text, area=area, channel=channel)


async def main() -> None:
    try:
        await bot.run()
    finally:
        await bot.stop()


asyncio.run(main())
```

## 在事件中回复消息

```python
@bot.on_message
async def handle_message(message: Message, ctx: EventContext):
    if message.text.strip() == "ping":
        await ctx.reply("pong")
```

`ctx.reply()` 会自动使用当前消息的：

- `area`
- `channel`
- `message_id`

因此在 handler 里通常不需要手动取 `area` 和 `channel`。

## 手动回复某条消息

```python
await client.messages.send_message(
    "收到",
    area=message.area,
    channel=message.channel,
    reference_message_id=message.message_id,
)
```

## 私信

```python
@bot.on_private_message
async def handle_message(message: Message, ctx: EventContext):
    await ctx.reply("这是私信回复")
```

当然, 你也可以直接调用 `bot.messages.send_private_message()` 发送私信：

```python
await bot.messages.send_private_message(
    "这是私信",
    target="目标  UID",
    channel="私信会话 ID",
)
```

如果不传 `channel`，SDK 会先调用 `open_private_session(target)` 打开或创建私信会话，再发送到该会话。

## Segment 消息

SDK 支持用 `Segment` 组合消息内容。常用类型：

| Segment             | 用途            |
|---------------------|---------------|
| `Text("文本")`        | 普通文本          |
| `Mention("用户 UID")` | at指定用户        |
| `MentionAll()`      | at全体          |
| `Image("a.png")`    | 本地图片，发送前会自动上传 |

示例：

```python
from oopz_sdk.models.segment import Text, Mention, Image

await bot.messages.send_message(
    Text("你好 "),
    Mention("2ce12121207111ef9d5dc6b17a3481f1"),
    Text(" 这是一张图：\n"),
    Image("./demo.png"),
    area="域 ID",
    channel="频道 ID",
)
```

当传入 Segment 时，不要同时传 `attachments=`，否则会抛出 `ValueError`。这是为了避免文本中的图片占位和附件列表不一致。

## 手动附件方式

Oopz的图片发送需要先上传图片获取 `file_key`，然后在消息文本中用 `![IMAGEw{weight}h{height}]({file_key})` 占位，最后把附件信息放到 `attachments` 参数里。

Segment 的 `Image` 已经封装了这个流程，如果你不想用 Segment，也可以手动拼装信息：

详细请查看 [Media Service 上传文件](../reference/media-service.md) 的文档。

```python
from oopz_sdk.utils.image import get_image_info

uploaded = await client.media.upload_file("./demo.png", file_type="IMAGE", ext="png")
width, height, file_size = get_image_info("./demo.png")

await client.messages.send_message(
    f"图片：![IMAGEw{weight}h{height}]({uploaded.file_key})\n",
    area="域 ID",
    channel="频道 ID",
    attachments=[{
            "file_key": uploaded.file_key,
            "url": uploaded.url,
            "display_name": "demo.png",
            "file_size": file_size,
            "animated": uploaded.animated,
            "hash": "",
            "width": width,
            "height": height,
            "preview_file_key": uploaded.preview_file_key,
    }],
)
```

## 自动撤回

全局配置：

```python
from oopz_sdk import AutoRecallConfig, OopzConfig

config = OopzConfig(
    ...,
    auto_recall=AutoRecallConfig(enabled=True, delay=30.0),
)
```

单条消息启用：

```python
await bot.messages.send_message(
    "30 秒后撤回",
    area=area,
    channel=channel,
    auto_recall=True,
)
```

当前实现中，`send_message(auto_recall=True)` 会尝试按 `config.auto_recall.delay` 延迟撤回；`auto_recall=False`
不会为本条消息安排撤回。

## 撤回频道消息

如果在事件回调里，直接调用 `ctx.recall()` 就能撤回当前消息：

```python
await asyncio.sleep(5)  # 等 5 秒
await ctx.recall()
```


```python
await bot.messages.recall_message(
    message_id="消息 ID",
    area="域 ID",
    channel="频道 ID",
)
```

## 撤回私信

```python
await bot.messages.recall_private_message(
    message_id="消息 ID",
    channel="私信会话 ID",
    target="目标 UID",
)
```