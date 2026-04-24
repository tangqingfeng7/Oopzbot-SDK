# Oopz SDK

Oopz 平台的 Python SDK，封装了 HTTP API、文件上传和 WebSocket 事件订阅，方便快速构建机器人或集成工具。

- 支持 Python 3.10 / 3.11 / 3.12 / 3.13
- 统一的异步接口（`asyncio` + `aiohttp`）
- 基于 `pydantic v2` 的响应模型
- WebSocket 事件分发 + 装饰器式注册

## 安装

```bash
pip install oopz-sdk
```

## 准备凭证

调用接口前需要准备：

- `device_id`：设备 ID
- `person_uid`：机器人所属账号 UID
- `jwt_token`：登录态 JWT
- `private_key`：RSA 私钥（PEM 格式），用于请求签名

凭证均通过 `OopzConfig` 传入。除上述必填项外，`OopzConfig` 还支持若干可选参数，例如：

- `ignore_self_messages`：WebSocket 事件中是否忽略自己发出的消息（默认开启，避免回声死循环）
- `auto_recall_enabled` / `auto_recall_delay`：发消息后自动撤回
- `use_announcement_style`：默认以公告样式发消息

## 发送一条频道消息

```python
import asyncio

from oopz_sdk import OopzConfig, OopzRESTClient


async def main() -> None:
    config = OopzConfig(
        device_id="你的设备ID",
        person_uid="你的用户UID",
        jwt_token="你的JWT Token",
        private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    )

    async with OopzRESTClient(config) as client:
        result = await client.messages.send_message(
            "Hello Oopz!",
            area="你的域ID",
            channel="你的频道ID",
        )
        print("message_id:", result.message_id)


asyncio.run(main())
```

> `async with OopzRESTClient(...)` 会在退出时统一关闭底层 HTTP 会话。
> 不要对子 service（`client.messages` / `client.media` / ...）单独使用 `async with`，
> 它们共享同一个连接，应由 `OopzRESTClient` 或 `OopzBot` 统一管理生命周期。

## 监听消息并自动回复

```python
import asyncio

from oopz_sdk import OopzBot, OopzConfig


async def main() -> None:
    bot = OopzBot(OopzConfig(
        device_id="...",
        person_uid="...",
        jwt_token="...",
        private_key="...",
    ))

    @bot.on_message
    async def on_message(message, ctx) -> None:
        if (message.content or "").strip().lower() == "ping":
            await ctx.reply("pong")

    try:
        await bot.run()
    finally:
        await bot.stop()


asyncio.run(main())
```

更多示例见 `examples/` 目录：

- `examples/send_message.py`：最小发送消息示例
- `examples/reply_bot.py`：基于 `OopzBot` 的事件驱动示例
- `examples/upload_private_image.py`：上传图片并通过私信发送

## 主要入口

| 名称 | 说明 |
| --- | --- |
| `OopzConfig` | SDK 配置，持有凭证和可选运行时参数 |
| `OopzRESTClient` | REST 总入口，按领域挂载各 service |
| `OopzBot` | 高阶入口，组合 REST 与 WebSocket，提供事件注册装饰器 |
| `OopzWSClient` | 纯 WebSocket 客户端，供需要自行处理事件分发的场景使用 |
| `Signer` | 请求签名工具，便于自定义传输层时复用 |

REST / Bot 上挂载的 service：

| 属性 | 类 | 说明 |
| --- | --- | --- |
| `messages` | `Message` | 频道消息 / 私信 / 撤回 / 富文本片段 |
| `media` | `Media` | 文件上传（图片、附件等） |
| `areas` | `AreaService` | 域（群/服务器）信息与成员分页 |
| `channels` | `Channel` | 频道信息与语音频道 `enter/leave` |
| `members` | `Member` | 成员信息查询 |
| `moderation` | `Moderation` | 禁言 / 解禁 / 踢人 / 拉黑 |
| `voice` | `Voice` | 语音频道加入与推流（需浏览器后端，见 `examples`） |

## 许可证

MIT License，详见仓库根目录 `LICENSE` 文件。
