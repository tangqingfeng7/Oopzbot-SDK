"""最小收消息并自动回复示例。"""

import asyncio

from oopz_sdk import OopzBot, OopzConfig


async def main() -> None:
    config = OopzConfig(
        device_id="你的设备ID",
        person_uid="你的用户UID",
        jwt_token="你的JWT Token",
        private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    )

    bot = OopzBot(config)

    @bot.on_message
    async def on_message(message, ctx) -> None:
        content = message.content or ""
        if content.strip().lower() == "ping":
            await ctx.reply("pong")

    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
