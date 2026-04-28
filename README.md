# Oopz SDK

面向 Oopz 平台的 Python SDK。

`oopz-sdk` 将 HTTP API、文件上传、WebSocket 事件、消息模型、事件模型和语音能力封装为一致的异步接口，让机器人、自动化脚本和集成工具可以用更清晰的方式接入 Oopz。

项目以 `asyncio`、`aiohttp` 和 `pydantic v2` 为基础，提供类型友好的数据模型、可组合的 service 层，以及面向机器人开发的高层入口 `OopzBot`。

## 快速入口

| 入口 | 说明 |
| --- | --- |
| [文档首页](https://github.com/tangqingfeng7/Oopzbot-SDK/blob/main/docs/index.md) | 完整的使用指南、概念说明和参考文档。 |
| [5 分钟上手](https://github.com/tangqingfeng7/Oopzbot-SDK/blob/main/docs/guide/quickstart.md) | 从零跑通一个最小机器人。 |
| [API 参考](https://github.com/tangqingfeng7/Oopzbot-SDK/blob/main/docs/reference/services.md) | 查看 service、参数、返回值和调用约定。 |
| [示例目录](https://github.com/tangqingfeng7/Oopzbot-SDK/tree/main/examples) | 参考可运行的本地示例脚本。 |

## 安装

```bash
pip install oopz-sdk
```

本地开发：

```bash
pip install -e ".[dev]"
```

## 能力概览

- REST service：消息、媒体、域、频道、用户、管理操作。
- WebSocket 事件：消息、撤回、频道变化、语音状态、用户状态等事件分发。
- Bot 开发入口：装饰器式事件注册、上下文回复、生命周期管理。
- 语音能力：加入语音频道，播放 URL、本地文件或 bytes，并支持暂停、继续、停止、进度跳转、音量设置和状态查询。

## 许可证

MIT License，详见 [LICENSE](https://github.com/tangqingfeng7/Oopzbot-SDK/blob/main/LICENSE)。
