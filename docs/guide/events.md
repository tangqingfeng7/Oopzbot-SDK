# 事件系统

事件系统由三部分组成：

1. `OopzWSClient` 接收原始 WebSocket 消息。
2. `EventParser` 将原始 JSON 转换为结构化事件模型。
3. `EventDispatcher` 根据 `name` 调用注册的 handler。

## 事件回调函数

事件回调函数是用于注册事件处理逻辑的异步函数。当特定事件发生时，SDK 会调用对应的回调函数，并传入事件数据和上下文。

事件回调函数通常接受两个参数：

```python
async def handler(event: Event, ctx: EventContext):
    ...
```

其中：

- `event` 是具体事件模型，例如 `MessageEvent`、`MessageDeleteEvent`、`ChannelUpdateEvent`。
- `ctx` 是 `EventContext`，包含 `ctx.bot`、`ctx.config`、`ctx.event`。

消息事件的回调和其他Event不同，消息事件的回调传递的是解析后的 `Message` 模型。

```python
async def handler(message: Message, ctx: EventContext):
    ...
```

## 注册事件

```python
# 当接受到频道消息时调用
@bot.on_message
async def on_message(message: Message, ctx: EventContext):
    ...


# 当接受到私信消息时调用
@bot.on_private_message
async def on_private_message(event, ctx):
    ...


# 当频道消息被撤回时调用
@bot.on_recall
async def on_recall(event, ctx):
    ...


# 当用户身份组发生变化时调用
@bot.on("role.change")
async def on_role_change(event, ctx):
    ...
```

## 内置快捷装饰器

| 装饰器                            | 事件名                    | 说明                                |
|--------------------------------|------------------------|-----------------------------------|
| `@bot.on_ready`                | `ready`                | WebSocket 已打开并完成 SDK 内部 ready 分发。 |
| `@bot.on_message`              | `message`              | 频道消息。                             |
| `@bot.on_message_edit`         | `message.edit`         | 频道消息编辑。                           |
| `@bot.on_private_message`      | `message.private`      | 私信消息。                             |
| `@bot.on_private_message_edit` | `message.private.edit` | 私信消息编辑。                           |
| `@bot.on_recall`               | `recall`               | 频道消息撤回。                           |
| `@bot.on_private_recall`       | `recall.private`       | 私信消息撤回。                           |
| `@bot.on_error`                | `error`                | handler 或底层连接错误。                  |
| `@bot.on_close`                | `close`                | WebSocket 关闭。                     |
| `@bot.on_reconnect`            | `reconnect`            | WebSocket 重连。                     |
| `@bot.on_raw_event`            | `raw_event`            | 所有事件的原始分发。                        |

其他事件使用 `@bot.on("事件名")` 注册。

## Oopz 原生 event code 到 SDK event name 映射

还在不断完善中，欢迎提交 PR 进行补充：

| Oopz event code | SDK event name         | 模型                          | 说明          |
|-----------------|------------------------|-----------------------------|-------------|
| `1`             | `server_id`            | `ServerIdEvent`             | 服务端连接流程     |
| `6`             | `recall.private`       | `MessageDeleteEvent`        | 私信消息撤回      |
| `7`             | `message.private`      | `MessageEvent`              | 私信消息        |
| `8`             | `recall`               | `MessageDeleteEvent`        | 频道消息撤回      |
| `9`             | `message`              | `MessageEvent`              | 频道消息        |
| `11`            | `moderation.voice_ban` | `AreaDisableEvent`          | 频道禁麦/语音限制事件 |
| `12`            | `moderation.text_ban`  | `AreaDisableEvent`          | 频道禁言/文字限制事件 |
| `13`            | `channel.delete`       | `ChannelDeleteEvent`        | 删除频道        |
| `18`            | `channel.update`       | `ChannelUpdateEvent`        | 频道设置变化      |
| `19`            | `voice.leave`          | `VoiceChannelPresenceEvent` | 用户离开语音频道    |
| `20`            | `voice.enter`          | `VoiceChannelPresenceEvent` | 用户进入语音频道    |
| `25`            | `channel.create`       | `ChannelCreateEvent`        | 创建频道        |
| `26`            | `user.update`          | `UserUpdateEvent`           | 用户资料变化      |
| `27`            | `user.login_state`     | `UserLoginStateEvent`       | 用户登录/登出状态变化 |
| `28`            | `area.update`          | `AreaUpdateEvent`           | 域信息变化       |
| `52`            | `role.change`          | `RoleChangedEvent`          | 身份组变化       |
| `56`            | `message.private.edit` | `MessageEvent`              | 私信消息编辑      |
| `57`            | `message.edit`         | `MessageEvent`              | 频道消息编辑      |
| `253`           | `auth`                 | `AuthEvent`                 | 鉴权响应        |
| `254`           | `heartbeat`            | `HeartbeatEvent`            | 心跳事件        |
| 其他              | `event_{code}`         | `UnknownEvent`              | 未建模事件兜底     |

## 未知事件

未知事件不会直接丢弃，而是转换为 `UnknownEvent`：

```python
@bot.on_raw_event
async def raw(event, ctx):
    if event.name.startswith("event_"):
        print(event.body)
```

这可以帮助后续补充新的事件模型。
