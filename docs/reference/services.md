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
client.general
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
| `general` | `General` | 获取每日一言等通用平台信息。 |
| `voice` | `Voice` | 进入语音频道、推流播放、暂停、恢复、音量、退出。仅 `OopzBot` 默认挂载。 |

## 调用约定

- 所有网络方法都是 `async`，必须使用 `await`
- 参数为空时通常抛出 `ValueError`
- API 响应格式异常时通常抛出 `OopzApiError`

## 错误与限流

- 业务 HTTP 请求返回 429 时抛出 `OopzRateLimitError`，可读取 `status_code` 和
  `retry_after` 判断状态与等待秒数。仅使用了限流重试入口的接口会自动退避，
  配置 `RetryConfig` 不会让所有请求自动重试。
- 401/428 作为鉴权失效处理；`OopzBot` 配置了续期能力时，会先尝试重登并重试请求一次。
  直接创建的 `OopzRESTClient` 默认不携带 `AuthManager`。403 等其他状态按普通 API 错误处理。
- 错误响应中的 `message` 或 `error` 为 `null` 时按空值处理，继续使用其他可用错误字段或默认说明，
  不再因 `.strip()` 异常掩盖 API 错误。

密码登录接口的 429 与业务请求使用不同异常类型，详见 [认证与凭据](auth.md)。

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
