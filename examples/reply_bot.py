import asyncio

from oopz_sdk import OopzBot, OopzConfig
from oopz_sdk.events import EventContext
from oopz_sdk.models import Message

config = OopzConfig()

config.login(phone="填入登录手机号", password="填入登录密码")

bot = OopzBot(config)

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