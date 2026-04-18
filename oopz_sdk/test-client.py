from __future__ import annotations

import asyncio
from oopz_sdk.client.bot import OopzBot
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.events import EventContext


def build_test_config() -> OopzConfig:
    return OopzConfig(

    )


async def main():

    bot = OopzBot(build_test_config())

    @bot.on_ready
    async def handle_ready(ctx):
        print("[READY] connected")

    @bot.on_message
    async def handle_message(message, ctx: EventContext):
        print("[MESSAGE]", message)
        await ctx.send("这是测试消息")
        await ctx.reply("那是什么")

    @bot.on_private_message
    async def handle_private_message(message, ctx: EventContext):
        print("[PRIVATE MESSAGE]", message)
        await ctx.send("撤回")
        await ctx.reply("这是测试私聊消息")

    @bot.on_error
    async def handle_error(ctx, error):
        print("[ERROR]", error)

    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())