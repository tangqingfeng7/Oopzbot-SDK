from __future__ import annotations

import asyncio
import json
import os

from oopz_sdk.client.bot import OopzBot
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.events import EventContext


def build_test_config() -> OopzConfig:
    return OopzConfig(

    )


def run_real_bot():

    bot = OopzBot(build_test_config())

    @bot.on_ready
    async def handle_ready(ctx):
        print("[READY] connected")

    @bot.on_message
    async def handle_message(ctx: EventContext, message):
        print("[MESSAGE]", message)
        await ctx.reply("盐盐盐收到了")

    @bot.on_error
    async def handle_error(ctx, error):
        print("[ERROR]", error)

    bot.run()


def main():
    run_real_bot()

if __name__ == "__main__":
    main()