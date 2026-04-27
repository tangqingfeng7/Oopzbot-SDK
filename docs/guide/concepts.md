# 核心概念

本页解释 SDK 中最常见、最容易混淆的对象。第一次使用建议先读这一页。

## OopzConfig

`OopzConfig` 保存 SDK 运行所需的配置，包括凭证、API 地址、WebSocket 地址、代理、重试、心跳、语音和自动撤回等。

```python
from oopz_sdk import OopzConfig

config = OopzConfig(
    device_id="设备 ID",
    person_uid="账号 UID",
    jwt_token="JWT Token",
    private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
)
```

所有入口都需要它。

## OopzBot

`OopzBot` 是机器人开发的推荐入口。它会自动组合：

- REST API client
- WebSocket client
- 事件解析器
- 事件分发器
- `ctx.reply()` / `ctx.send()` 等上下文能力

日常写机器人时优先使用它：

```python
from oopz_sdk import OopzBot

bot = OopzBot(config)


@bot.on_message
async def on_message(event, ctx):
    await ctx.reply("收到")
```

## OopzRESTClient

`OopzRESTClient` 只用于bot推送场景，例如脚本主动发送消息、上传文件、获取用户信息。只使用Client 时是无法获取消息推送的。

```python
from oopz_sdk import OopzRESTClient

async with OopzRESTClient(config) as client:
    me = await client.members.get_person_info()
```

如果你需要长期监听消息，应该使用 `OopzBot`，而不是只用 `OopzRESTClient`。

## area

`area` 是 Oopz 的域 ID，可以理解为一个服务器 / 空间。

发送频道消息时通常必须传入 `area`：

```python
await bot.messages.send_message("hello", area="域 ID", channel="频道 ID")
```

## channel

`channel` 是频道 ID。频道属于某个 `area`。

频道消息需要同时知道：

```text
area + channel
```

## private channel

私信会话也有 `channel`，但它不是普通频道 ID，而是私信会话 ID。

私信发送可以只传 `target`，SDK 会自动打开或创建私信会话：

```python
await bot.messages.send_private_message("你好", target="目标用户 UID")
```

## Event

WebSocket 收到的原始事件会被解析成[事件模型](../reference/events.md)，例如：

- `MessageEvent`
- `MessageDeleteEvent`
- `ChannelUpdateEvent`
- `VoiceChannelPresenceEvent`
- `UnknownEvent`


```python
async def handler(event, ctx):
    ...
```

可以使用 `ctx.event` 访问当前事件，可以使用事件封装的属性来获取事件数据来进行开发。具体请参考[事件系统](../guide/events.md)。

## EventContext

`ctx` 是事件上下文，包含当前事件和 bot 引用。

常用方法：

| 方法               | 说明                                       |
|------------------|------------------------------------------|
| `ctx.reply(...)` | 回复当前消息。频道消息会自动带上 `reference_message_id`。 |
| `ctx.send(...)`  | 在当前上下文所在频道或私信中发送消息。                      |
| `ctx.recall()`   | 撤回当前频道消息。                                |
| `ctx.bot`        | 访问完整 `OopzBot` 实例。                       |

示例：

```python
@bot.on_message
async def on_message(event, ctx):
    await ctx.reply("收到")
```

## Service

`OopzBot` 和 `OopzRESTClient` 都会挂载 service：

| 属性           | 说明                          |
|--------------|-----------------------------|
| `messages`   | 频道消息、私信、撤回、置顶、历史消息。         |
| `media`      | 上传文件。                       |
| `areas`      | 域信息、域成员、域频道。                |
| `channels`   | 频道创建、修改、删除、设置。              |
| `person`     | 用户资料、好友、好友请求。               |
| `moderation` | 禁言、解禁、踢人、黑名单。               |
| `voice`      | 语音频道和推流能力，仅 `OopzBot` 默认挂载。 |

