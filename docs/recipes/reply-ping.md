# 回复机器人

这个示例会在收到 `ping` 时回复 `pong`。

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


@bot.on_message
async def on_message(message, ctx):
    if message.text.strip() == "ping":
        await ctx.reply("pong")


async def main() -> None:
    try:
        await bot.run()
    finally:
        await bot.stop()


asyncio.run(main())
```

`ctx.reply()` 会自动读取当前事件中的 `area`、`channel` 和 `message_id`。
