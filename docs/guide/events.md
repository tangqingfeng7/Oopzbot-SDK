# 事件系统

事件系统由三部分组成：

1. `OopzWSClient` 接收原始 WebSocket 消息。
2. `EventParser` 将原始 JSON 转换为结构化事件模型。
3. `EventDispatcher` 根据 `name` 调用注册的 handler。

## 事件回调签名

推荐签名：

```python
async def handler(event, ctx):
    ...
```

其中：

- `event` 是具体事件模型，例如 `MessageEvent`、`MessageDeleteEvent`、`ChannelUpdateEvent`。
- `ctx` 是 `EventContext`，包含 `ctx.bot`、`ctx.config`、`ctx.event`。

## 注册事件

```python
@bot.on_message
async def on_message(event, ctx):
    ...

@bot.on_private_message
async def on_private_message(event, ctx):
    ...

@bot.on_recall
async def on_recall(event, ctx):
    ...

@bot.on("role.change")
async def on_role_change(event, ctx):
    ...
```

## 内置快捷装饰器

| 装饰器 | 事件名 | 说明 |
| --- | --- | --- |
| `@bot.on_ready` | `ready` | WebSocket 已打开并完成 SDK 内部 ready 分发。 |
| `@bot.on_message` | `message` | 频道消息。 |
| `@bot.on_message_edit` | `message.edit` | 频道消息编辑。 |
| `@bot.on_private_message` | `message.private` | 私信消息。 |
| `@bot.on_private_message_edit` | `message.private.edit` | 私信消息编辑。 |
| `@bot.on_recall` | `recall` | 频道消息撤回。 |
| `@bot.on_private_recall` | `recall.private` | 私信消息撤回。 |
| `@bot.on_error` | `error` | handler 或底层连接错误。 |
| `@bot.on_close` | `close` | WebSocket 关闭。 |
| `@bot.on_reconnect` | `reconnect` | WebSocket 重连。 |
| `@bot.on_raw_event` | `raw_event` | 所有已解析事件的原始分发。 |

其他事件使用 `@bot.on("事件名")` 注册。

## Oopz event code 到 SDK event name 映射

| Oopz event code | SDK event name | 模型 | 说明 |
| --- | --- | --- | --- |
| `1` | `server_id` | `ServerIdEvent` | 服务端分配连接 ID。 |
| `253` | `auth` | `AuthEvent` | 鉴权响应。 |
| `254` | `heartbeat` | `HeartbeatEvent` | 心跳事件。通常不需要业务处理。 |
| `9` | `message` | `MessageEvent` | 频道消息。 |
| `7` | `message.private` | `MessageEvent` | 私信消息。 |
| `57` | `message.edit` | `MessageEvent` | 频道消息编辑。 |
| `56` | `message.private.edit` | `MessageEvent` | 私信消息编辑。 |
| `8` | `recall` | `MessageDeleteEvent` | 频道消息撤回。 |
| `6` | `recall.private` | `MessageDeleteEvent` | 私信消息撤回。 |
| `11` | `moderation.voice_ban` | `AreaDisableEvent` | 频道禁麦/语音限制事件。 |
| `12` | `moderation.text_ban` | `AreaDisableEvent` | 频道禁言/文字限制事件。 |
| `18` | `channel.update` | `ChannelUpdateEvent` | 频道设置变化。 |
| `25` | `channel.create` | `ChannelCreateEvent` | 创建频道。 |
| `13` | `channel.delete` | `ChannelDeleteEvent` | 删除频道。 |
| `20` | `voice.enter` | `VoiceChannelPresenceEvent` | 用户进入语音频道。 |
| `19` | `voice.leave` | `VoiceChannelPresenceEvent` | 用户离开语音频道。 |
| `26` | `user.update` | `UserUpdateEvent` | 用户资料变化。 |
| `27` | `user.login_state` | `UserLoginStateEvent` | 用户登录/登出状态变化。 |
| `28` | `area.update` | `AreaUpdateEvent` | 域信息变化。 |
| `52` | `role.change` | `RoleChangedEvent` | 身份组变化。 |
| 其他 | `event_{code}` | `UnknownEvent` | 未建模事件兜底。 |

## 消息事件结构

```python
@bot.on_message
async def on_message(event, ctx):
    message = event.message
    print(message.area, message.channel, message.message_id)
    print(message.sender_id, message.content)
```

`MessageEvent` 字段：

| 字段 | 说明 |
| --- | --- |
| `name` | 事件名，例如 `message`。 |
| `event_type` | 原始事件编号。 |
| `raw` | 原始 WebSocket payload。 |
| `message` | 解析后的 `Message` 模型。 |
| `is_private` | 是否私信事件。 |

## 未知事件

未知事件不会直接丢弃，而是转换为 `UnknownEvent`：

```python
@bot.on_raw_event
async def raw(event, ctx):
    if event.name.startswith("event_"):
        print(event.body)
```

这可以帮助后续补充新的事件模型。
