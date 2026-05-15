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

你需要使用`手机号`和`密码`来进行登录, 密码可以在oopz的账号设置中进行修改

[//]: # (最小运行需要下面 4 个字段：)

[//]: # ()
[//]: # (| 字段 | 说明 |)

[//]: # (| --- | --- |)

[//]: # (| `device_id` | 当前登录设备 ID。 |)

[//]: # (| `person_uid` | 当前登录账号 UID，通常也是机器人 UID。 |)

[//]: # (| `jwt_token` | Oopz 登录态 JWT。 |)

[//]: # (| `private_key` | RSA 私钥，用于请求签名。 |)

[//]: # (推荐通过环境变量传入，不要硬编码到代码里。如果还没有这些凭据，可以参考 [账号密码登录提取凭据]&#40;../recipes/password-login.md&#41; 从 OOPZ Web 登录态自动抓取。)

## 3. 创建 `bot.py`

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

`OopzConfig.from_env()` 默认读取 `OOPZ_LOGIN_PHONE`、`OOPZ_LOGIN_PASSWORD`；如果你想直接用账号密码登录，更推荐先创建 `config = OopzConfig()`，再调用 `config.login(...)`，详见 [认证与凭据](../reference/auth.md)。

## 4. 设置环境变量

Windows PowerShell：

```powershell
$env:OOPZ_LOGIN_PHONE = "你的 OOPZ 登录账号"
$env:OOPZ_LOGIN_PASSWORD = "你的 OOPZ 登录密码"
python bot.py
```

Linux / macOS：

```bash
export OOPZ_LOGIN_PHONE="..."
export OOPZ_LOGIN_PASSWORD="..."
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

