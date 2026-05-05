# Oopz SDK 文档

`oopz-sdk` 是一个面向 Oopz 平台的异步 Python SDK，封装 HTTP API、文件上传、WebSocket 事件订阅、消息模型、事件模型、语音推流以及
OneBot v11 / v12 适配能力。

本项目由社区开发与维护，旨在为机器人开发、自动化集成和协议适配提供更方便的 Python 接口。

需要注意的是，项目要求 **Python 3.10 及以上**版本。

项目还处于早期开发阶段，欢迎社区参与测试、反馈和贡献。

## 选择入口

| 你想做什么                          | 应该看                                                     |
|--------------------------------|---------------------------------------------------------|
| 第一次使用，想跑通一个机器人                 | [5 分钟上手](guide/quickstart.md)                           |
| 只想安装 SDK                       | [安装](guide/installation.md)                             |
| 不知道 `area`、`channel`、`ctx` 是什么 | [核心概念](guide/concepts.md)                               |
| 配置凭证、代理、重试、心跳                   | [配置方法](guide/configuration.md)                          |
| 监听消息、撤回、频道变化等事件                | [事件系统](guide/events.md)                                 |
| 发送文本、图片、私信、Segment             | [消息发送](guide/messaging.md)                              |
| 查询已加入域和频道 ID                   | [列出 area 和 channel](recipes/list-areas-and-channels.md) |
| 接入 OneBot v11 / v12、NoneBot2 / AstrBot       | [OneBot 适配](adapters/onebot/index.md)                 |
| 查询 service API                 | [Service 总览](reference/services.md)                     |

## 最小机器人示例

下面的机器人会在频道收到 `ping` 时回复 `pong`。

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
    if message.text.strip() == "ping":
        await ctx.reply("pong")


async def main() -> None:
    try:
        await bot.run()
    finally:
        await bot.stop()


asyncio.run(main())
```

完整解释见 [5 分钟上手](guide/quickstart.md)。

## 文档结构

- **快速开始**：按安装、配置、核心概念、最小机器人顺序学习。
- **基础用法**：消息、事件、生命周期、媒体、语音等常用能力。
- **常见任务**：按任务组织的完整示例，例如回复消息、发图、列频道。
- **适配器**：OneBot v11 / v12、NoneBot2 / AstrBot 等生态接入说明。
- **API 参考**：按 service 和模型查询参数、返回值和注意事项。
- **开发**：文档站点构建、贡献和维护说明。

## 推荐入口

日常使用 SDK 时，推荐从 `OopzBot` 开始。

`OopzBot` 负责组合配置、HTTP Service、WebSocket 连接、事件分发以及上下文能力，并且提供了装饰器和函数式的事件注册，是面向开发者的主要入口。

| 对象                | 说明                                                                    |
|-------------------|-----------------------------------------------------------------------|
| `OopzBot`         | 高层 Bot 入口，负责启动连接、监听事件、分发回调、发送消息和调用各类 service。                         |
| `OopzConfig`      | SDK 配置对象，保存凭证、API 地址、WebSocket 地址、代理、重试、心跳、语音和 OneBot 相关配置。 |
| `OopzRESTClient`  | 底层 REST 客户端，包装 HTTP transport、签名和所有 service。仅做接口调用、不需要 WebSocket 时使用。 |
| `OopzWSClient`    | 底层 WebSocket 客户端，仅做事件接收、不需要 REST 调用时使用。                               |

对于大多数机器人开发场景，只需要直接使用 `OopzBot` 和 `OopzConfig`。

`OopzRESTClient` 与 `OopzWSClient` 属于较底层的客户端封装，通常由 `OopzBot` 自动创建和管理。只有在你需要扩展
SDK、调试底层请求，或绕过 Bot 层直接调用 REST / WebSocket 能力时，才需要关注它们。

