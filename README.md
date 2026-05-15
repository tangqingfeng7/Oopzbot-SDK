<div align="center">

# Oopzbot SDK

面向 Oopz 语音平台的现代化异步 Python SDK。


[![License](https://img.shields.io/github/license/tangqingfeng7/Oopzbot-SDK?labelColor=555&color=97CA00)](https://github.com/tangqingfeng7/Oopzbot-SDK)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/oopz-sdk?logo=pypi&logoColor=white&label=PyPI&labelColor=3775A9&color=2D9CDB)](https://pypi.org/project/oopz-sdk/)
[![Async](https://img.shields.io/badge/asyncio-ready-7B61FF.svg)](https://docs.python.org/3/library/asyncio.html)
[![Typing](https://img.shields.io/badge/typing-pydantic%20v2-E92063.svg?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![OneBot](https://img.shields.io/badge/OneBot-v11-8A2BE2)](https://tangqingfeng7.github.io/Oopzbot-SDK/adapters/onebot/)
[![Docs](https://img.shields.io/badge/docs-online-2ea44f?logo=materialformkdocs&logoColor=white)](https://tangqingfeng7.github.io/Oopzbot-SDK/)

**异步优先 · 事件驱动 · 类型友好 · 消息 / 媒体 / 语音**

[//]: # (· OneBot v12 适配)

[快速开始](https://tangqingfeng7.github.io/Oopzbot-SDK/guide/quickstart/) · [功能特性](#-功能特性) · [文档](https://tangqingfeng7.github.io/Oopzbot-SDK/) · [示例](https://tangqingfeng7.github.io/Oopzbot-SDK/recipes/) · [贡献](https://tangqingfeng7.github.io/Oopzbot-SDK/development/contributing/)

</div>

---

## 这是什么？

`oopz-sdk` 是一个面向 **Oopz 平台** 的异步 Python SDK，用于快速构建机器人、监听事件、收发消息、上传媒体并调用平台服务。

> [!IMPORTANT]
> 项目仍处于早期开发阶段，接口和适配能力可能继续调整。欢迎参与测试、反馈和贡献。

## ✨ 功能特性

- **Bot 入口简单**：通过 `OopzBot` 完成连接、事件监听、消息回复和 Service 调用。
- **异步优先**：基于 `asyncio`，适合长期运行的机器人和服务端应用。
- **类型友好**：核心模型基于 Pydantic v2，便于补全、校验和测试。
- **事件驱动**：支持消息、私信、撤回、编辑、频道变化、语音进出、身份组变化等事件。
- **消息与媒体**：支持文本、图片、私信、引用回复、消息段解析和文件上传。
- **Service 分层**：提供消息、媒体、域、频道、用户、管理、语音等能力入口。
- **生态适配**：OneBot v11和v12 适配正在不断完善~

## 📦 安装

```bash
pip install oopz-sdk
```

从源码安装：

```bash
git clone https://github.com/tangqingfeng7/Oopzbot-SDK.git
cd Oopzbot-SDK
pip install -e .
```

开发环境：

```bash
pip install -e ".[dev]"
pytest
```

需要语音能力时，还需要安装 Playwright Chromium：

```bash
python -m playwright install chromium
```

## 🚀 快速开始

创建 `bot.py`：

```python
import asyncio

from oopz_sdk import OopzBot, OopzConfig


bot = OopzBot(OopzConfig.from_env())


@bot.on_ready
async def on_ready(ctx):
    print("[READY] connected")


@bot.on_message
async def on_message(message, ctx):
    if message.text.strip() == "ping":
        await ctx.reply("pong")


asyncio.run(bot.run())
```

设置环境变量后运行：

```bash
export OOPZ_LOGIN_PHONE="..."
export OOPZ_LOGIN_PASSWORD="..."
python bot.py
```

Windows PowerShell：

```powershell
$env:OOPZ_LOGIN_PHONE = "你的 OOPZ 登录账号"
$env:OOPZ_LOGIN_PASSWORD = "你的 OOPZ 登录密码"
python bot.py
```

更多登录方法详见 [认证与凭据](https://tangqingfeng7.github.io/Oopzbot-SDK/reference/auth/)：

在机器人能收到的频道里发送：

```text
ping
```

机器人会回复：

```text
pong
```

更多用法请查看[文档](https://tangqingfeng7.github.io/Oopzbot-SDK/)。

## 许可

`Oopzbot-SDK `采用 `MIT` 许可证进行开源

## 免责声明

本项目由社区开发与维护，旨在为 Oopz 机器人开发、自动化集成和协议适配提供更方便的 Python 接口。使用本项目时请遵守 Oopz 平台相关规则，并妥善保管账号凭证、JWT、私钥等敏感信息。
