# OneBot 快速开始

## 启用 OneBot v11

```python
import asyncio

from oopz_sdk import OopzBot, OopzConfig, OneBotV11Config

config = OopzConfig(
    device_id="你的 device_id",
    person_uid="你的 Oopz 用户 UID",
    jwt_token="你的 JWT",
    private_key="你的 PEM 私钥",
    onebot_v11=OneBotV11Config(
        enabled=True,
        host="127.0.0.1",
        port=6700,
        access_token="",
        enable_http=True,
        enable_ws=True,
    ),
)

bot = OopzBot(config)

asyncio.run(bot.run())
```

默认地址：

```text
http://127.0.0.1:6700/onebot/v11
ws://127.0.0.1:6700/onebot/v11
```

## 启用 OneBot v12

```python
import asyncio

from oopz_sdk import OopzBot, OopzConfig, OneBotV12Config

config = OopzConfig(
    device_id="你的 device_id",
    person_uid="你的 Oopz 用户 UID",
    jwt_token="你的 JWT",
    private_key="你的 PEM 私钥",
    onebot_v12=OneBotV12Config(
        enabled=True,
        host="127.0.0.1",
        port=6727,
        access_token="",
        enable_http=True,
        enable_ws=True,
    ),
)

bot = OopzBot(config)

asyncio.run(bot.run())
```

默认地址：

```text
http://127.0.0.1:6727/onebot/v12
ws://127.0.0.1:6727/onebot/v12
```

## 同时启用 v11 和 v12

v11 和 v12 可以同时启用，但建议使用不同端口：

```python
from oopz_sdk import OopzConfig, OneBotV11Config, OneBotV12Config

config = OopzConfig(
    device_id="你的 device_id",
    person_uid="你的 Oopz 用户 UID",
    jwt_token="你的 JWT",
    private_key="你的 PEM 私钥",
    onebot_v11=OneBotV11Config(
        enabled=True,
        port=6700,
    ),
    onebot_v12=OneBotV12Config(
        enabled=True,
        port=6727,
    ),
)
```

!!! warning "v11 和 v12 的 ID 不互通"
    v11 使用数字 ID 映射，v12 使用字符串 message_id。两个 adapter 的映射表不是同一套协议 ID，不能把 v12 返回的 `message_id` 直接拿去调用 v11 action，反过来也一样。
