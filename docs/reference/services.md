# Service 总览

`OopzRESTClient` 和 `OopzBot` 都会挂载常用 service。

```python
client = OopzRESTClient(config)
client.messages
client.media
client.areas
client.channels
client.person       # 也可以使用 client.members（别名）
client.moderation
```

`OopzBot` 额外挂载：

```python
bot.voice
```

## Service 列表

| 属性 | 类 | 主要能力 |
| --- | --- | --- |
| `messages` | `Message` | 频道消息、私信、撤回、置顶、历史消息。 |
| `media` | `Media` | 文件上传。 |
| `areas` | `AreaService` | 域信息、域成员、域频道、域身份组。 |
| `channels` | `Channel` | 频道设置、创建、修改、删除、进入频道、语音成员。 |
| `person`（别名 `members`） | `Person` | 用户资料、好友、好友请求。 |
| `moderation` | `Moderation` | 禁言、解禁、禁麦、踢人、拉黑、黑名单。 |
| `voice` | `Voice` | 进入语音频道、推流播放、暂停、恢复、音量、退出。仅 `OopzBot` 默认挂载。 |

## 调用约定

- 所有网络方法都是 `async`，必须使用 `await`
- 参数为空时通常抛出 `ValueError`
- API 响应格式异常时通常抛出 `OopzApiError`

## REST 使用模式

```python
from oopz_sdk import OopzRESTClient

async with OopzRESTClient(config) as client:
    me = await client.person.get_person_info()
    await client.messages.send_message("hello", area=area, channel=channel)
```

## Bot 使用模式

```python
bot = OopzBot(config)

@bot.on_message
async def on_message(message, ctx):
    await ctx.reply("pong")

try:
    await bot.run()
finally:
    await bot.stop()
```
