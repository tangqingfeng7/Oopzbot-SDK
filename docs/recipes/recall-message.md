# 撤回消息

频道消息撤回需要三个信息：

| 字段 | 说明 |
| --- | --- |
| `message_id` | 要撤回的消息 ID。 |
| `area` | 消息所在域 ID。 |
| `channel` | 消息所在频道 ID。 |

## 撤回刚发送的频道消息

```python
result = await bot.messages.send_message(
    "这条消息稍后撤回",
    area=area,
    channel=channel,
)

await bot.messages.recall_message(
    message_id=result.message_id,
    area=area,
    channel=channel,
)
```

## 在事件中撤回当前消息

```python
@bot.on_message
async def on_message(message, ctx):
    if message and message.text.strip() == "/recallme":
        await ctx.recall()
```

## 私信撤回

```python
await bot.messages.recall_private_message(
    message_id="消息 ID",
    channel="私信会话 ID",
    target="目标用户 UID",
)
```

## 延迟撤回

SDK 不再内置「发完自动撤回」的开关。如果你确实需要这种行为，自己在调用方包一层即可，task 的生命周期、错误处理都由你：

```python
import asyncio

async def send_and_recall_later(
    bot,
    text: str,
    *,
    area: str,
    channel: str,
    delay: float = 30.0,
) -> None:
    result = await bot.messages.send_message(text, area=area, channel=channel)

    async def _recall() -> None:
        await asyncio.sleep(delay)
        await bot.messages.recall_message(
            message_id=result.message_id,
            area=area,
            channel=channel,
        )

    asyncio.create_task(_recall())
```

如果你希望在 `bot.stop()` 时一并取消未到期的撤回任务，把 `asyncio.create_task(...)` 返回的 `Task` 自己存起来，在停止流程里逐个 `cancel()` 即可。

私信场景把 `recall_message` 换成 `recall_private_message(message_id, channel, target)` 就行。
