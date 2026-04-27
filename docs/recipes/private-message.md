# 发送私信

私信发送需要目标用户 UID。通常不需要你手动创建私信会话，SDK 会自动调用 `open_private_session(target)`。


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
        bot.messages.send_private_message(
            "pong",
            target=message.sender_id,
        )

@bot.on_private_message
async def on_private_message(message, ctx):
    if message.text.strip() == "ping":
        await ctx.reply("pong")


async def main() -> None:
    try:
        await bot.run()
    finally:
        await bot.stop()


asyncio.run(main())
```
