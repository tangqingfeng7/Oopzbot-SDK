import asyncio

from oopz_sdk import OopzBot, OopzConfig
from oopz_sdk.events import EventContext
from oopz_sdk.models import Message

config = OopzConfig()

config.login(phone="18306357121", password="Dd114133627")

bot = OopzBot(config)

@bot.on_message
async def handle_message(message: Message, ctx: EventContext):
    if message.text.strip() == "ping":
        await bot.messages.send_message("Hello from OopzBot!", area=message.area, channel=message.channel)


async def main() -> None:
    try:
        await bot.run()
    finally:
        await bot.stop()


asyncio.run(main())