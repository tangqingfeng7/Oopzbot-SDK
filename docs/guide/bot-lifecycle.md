# Bot 生命周期

`OopzBot` 是推荐的高层入口。它统一管理：

- `OopzRESTClient`
- `OopzWSClient`
- 事件注册与分发
- `EventContext`
- `Voice` 语音服务
- 可选 OneBot v12 server / webhook / 反向 WebSocket

## 基础启动方式

```python
import asyncio
from oopz_sdk import OopzBot, OopzConfig

async def main() -> None:
    bot = OopzBot(OopzConfig(...))

    @bot.on_ready
    async def ready(event, ctx):
        print("bot ready")

    try:
        await bot.run()
    finally:
        await bot.stop()

asyncio.run(main())
```

`bot.run()` 当前等价于 `bot.start()`，会启动 REST、OneBot 适配器和 WebSocket。不要在事件处理函数里重复调用 `asyncio.run()`，所有回调都应该运行在同一个主事件循环中。

## 生命周期顺序

启动：

1. `bot.rest.start()`：初始化 HTTP transport。
2. `_start_onebot_v12_server()`：如果配置启用 OneBot v12，则启动适配器。
3. `bot.ws.start()`：连接 Oopz WebSocket。
4. WebSocket 打开后触发 `ready` 事件。

停止：

1. 停止 WebSocket。
2. 关闭语音后端。
3. 停止 OneBot v12 server。
4. 关闭 REST transport。

## 事件注册方式

```python
@bot.on_message
async def on_message(event, ctx):
    ...

@bot.on_private_message
async def on_private(event, ctx):
    ...

@bot.on("channel.update")
async def on_channel_update(event, ctx):
    ...
```

也可以在构造时传入函数：

```python
bot = OopzBot(config, on_message=handle_message, on_error=handle_error)
```

## 便捷方法

| 方法 | 说明 |
| --- | --- |
| `await bot.send(text, area, channel, **kwargs)` | 发送频道消息，内部调用 `bot.messages.send_message()`。 |
| `await bot.reply(text, area, channel, reference_message_id, **kwargs)` | 回复指定消息。 |
| `await bot.recall(message_id, area, channel, **kwargs)` | 撤回频道消息。 |

## EventContext

事件回调第二个参数通常是 `ctx`。在消息事件中可以使用：

```python
@bot.on_message
async def on_message(event, ctx):
    await ctx.reply("回复当前消息")
    await ctx.send("发送到当前频道")
    await ctx.recall()
```

| 方法 | 说明 |
| --- | --- |
| `ctx.reply(*text, **kwargs)` | 回复当前消息；频道消息会自动带 `reference_message_id`，私信会发送到当前私信会话。 |
| `ctx.send(*texts, **kwargs)` | 向当前上下文所在频道或私信发送消息。 |
| `ctx.recall(**kwargs)` | 撤回当前频道消息；私信暂不支持。 |

## 错误处理

```python
@bot.on_error
async def on_error(error, ctx):
    print("handler error:", error)

@bot.on_close
async def on_close(close_info, ctx):
    print(close_info.code, close_info.reason)

@bot.on_reconnect
async def on_reconnect(event, ctx):
    print("reconnecting")
```

建议所有 handler 内部只抛出真正需要中断的异常；普通业务错误可以自行捕获并记录日志。
