# 接入 HoshinoBot

[HoshinoBot](https://github.com/Ice9Coffee/HoshinoBot) 支持 OneBot v11 协议，可以通过 Oopz SDK 的 OneBot v11 适配器接入。
只要设置反向WS地址指向 HoshinoBot 的 OneBot v11 插件，就能把 SDK 收到的事件上报给 HoshinoBot。

示例：

```python
import asyncio
import os

from oopz_sdk import OopzBot, OopzConfig, OneBotV11Config, setup_logging


setup_logging("INFO")


config = OopzConfig(
    device_id=os.environ["OOPZ_DEVICE_ID"],
    person_uid=os.environ["OOPZ_PERSON_UID"],
    jwt_token=os.environ["OOPZ_JWT_TOKEN"],
    private_key=os.environ["OOPZ_PRIVATE_KEY"],

    onebot_v11=OneBotV11Config(
        enabled=True,
        host="127.0.0.1",
        port=6700,

        # HoshinoBot 通常不需要主动连接 SDK 的正向 WebSocket
        enable_ws=False,
        enable_http=False,
        # 关键：把 OneBot v11 事件上报给 HoshinoBot
        ws_reverse_url="ws://127.0.0.1:8080/ws/",

        # 推荐固定数据库路径，避免 group_id / message_id 映射变化
        db_path="./data/onebot_v11.sqlite3",
    ),
)


bot = OopzBot(config)


@bot.on_ready
async def handle_ready(ctx):
    print("Oopz SDK connected")


asyncio.run(bot.run())
```