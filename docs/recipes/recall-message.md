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
async def on_message(event, ctx):
    message = event.message
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
