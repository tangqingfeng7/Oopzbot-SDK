# 5 分钟上手

本页会带你完成一个最小机器人：收到 `ping` 时回复 `pong`。

如果你还不知道 `area`、`channel`、`ctx` 的含义，可以先快速看一遍 [核心概念](concepts.md)。

## 1. 安装

```bash
pip install oopz-sdk
```

从源码调试时使用：

```bash
git clone https://github.com/tangqingfeng7/Oopzbot-SDK.git
cd Oopzbot-SDK
pip install -e .
```

## 2. 准备凭证

最小运行需要下面 4 个字段：

| 字段 | 说明 |
| --- | --- |
| `device_id` | 当前登录设备 ID。 |
| `person_uid` | 当前登录账号 UID，通常也是机器人 UID。 |
| `jwt_token` | Oopz 登录态 JWT。 |
| `private_key` | RSA 私钥，用于请求签名。 |

推荐通过环境变量传入，不要硬编码到代码里。

从源码调试时，可以使用仓库里的凭证获取工具辅助获取这些字段：

```powershell
python .\script\credential_tool.py --save
```

工具会打开 Oopz 网页端，请在浏览器里登录账号。登录成功后，它会尝试从请求头、WebSocket 鉴权消息和浏览器存储中捕获 `person_uid`、`device_id`、`jwt_token` 和 `private_key`。

首次运行时如果缺少 Playwright，工具会尝试自动安装 `playwright` 和 Chromium。使用 `--save` 时，工具会把完整凭证摘要写入 `data/credentials.txt`，并生成 `private_key.py`；如果项目根目录已有 `config.py`，还会同步更新其中的 `device_id`、`person_uid` 和 `jwt_token`。这些文件都包含真实登录凭证，只能保留在本地，不要提交到仓库。

## 3. 创建 `bot.py`

```python
import asyncio
import os

from oopz_sdk import OopzBot, OopzConfig


config = OopzConfig(
    device_id=os.environ["OOPZ_DEVICE_ID"],
    person_uid=os.environ["OOPZ_PERSON_UID"],
    jwt_token=os.environ["OOPZ_JWT_TOKEN"],
    private_key=os.environ["OOPZ_PRIVATE_KEY"],
)

bot = OopzBot(config)


@bot.on_ready
async def on_ready(ctx):
    print("[READY] connected")


@bot.on_message
async def on_message(message, ctx):
    if message is None:
        return

    if message.text.strip() == "ping":
        await ctx.reply("pong")


@bot.on_error
async def on_error(ctx, error):
    print("[ERROR]", repr(error))


async def main() -> None:
    try:
        await bot.run()
    finally:
        await bot.stop()


asyncio.run(main())
```

## 4. 设置环境变量

Windows PowerShell：

```powershell
$env:OOPZ_DEVICE_ID="你的设备 ID"
$env:OOPZ_PERSON_UID="你的账号 UID"
$env:OOPZ_JWT_TOKEN="你的 JWT"
$env:OOPZ_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----`n...`n-----END RSA PRIVATE KEY-----"
python bot.py
```

Linux / macOS：

```bash
export OOPZ_DEVICE_ID="你的设备 ID"
export OOPZ_PERSON_UID="你的账号 UID"
export OOPZ_JWT_TOKEN="你的 JWT"
export OOPZ_PRIVATE_KEY=$'-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----'
python bot.py
```

## 5. 测试

在机器人能收到的频道里发送：

```text
ping
```

机器人应该回复：

```text
pong
```

## 6. 下一步

| 目标 | 文档 |
| --- | --- |
| 查询自己加入了哪些域和频道 | [列出 area 和 channel](../recipes/list-areas-and-channels.md) |
| 撤回消息 | [撤回消息](../recipes/recall-message.md) |
| 发送图片 | [发送图片](../recipes/send-image.md) |
| 了解事件回调 | [事件系统](events.md) |
| 了解消息、私信和撤回 | [消息发送](messaging.md) |

## 常见问题

### 机器人为什么不回复自己发的消息？

`OopzConfig.ignore_self_messages` 默认为 `True`，用于避免机器人回复自己导致死循环。

如果你确实需要处理自己发出的消息，可以显式设置：

```python
config = OopzConfig(..., ignore_self_messages=False)
```

### `ctx.reply()` 和 `bot.messages.send_message()` 有什么区别？

`ctx.reply()` 只能在消息事件中使用，会自动使用当前消息的 `area`、`channel` 和 `message_id`。

`bot.messages.send_message()` 是主动发送频道消息，需要你手动传入 `area` 和 `channel`。

### WebSocket 连接后程序为什么一直不退出？

这是正常行为。机器人需要长期保持 WebSocket 连接来接收事件。
