from __future__ import annotations

import asyncio
import json
import os

from oopz_sdk.client.bot import OopzBot
from oopz_sdk.config.settings import OopzConfig


def build_test_config() -> OopzConfig:
    return OopzConfig(
    )


def install_debug_send_stub(bot: OopzBot) -> None:
    """
    把真实 send_message 临时替换成打印函数，方便本地验证 ctx.reply()。
    """
    def fake_send_message(*, text: str, area: str = "", channel: str = "", **kwargs):
        print("\n[FAKE SEND]")
        print("text    =", text)
        print("area    =", area)
        print("channel =", channel)
        print("kwargs  =", kwargs)
        return {
            "ok": True,
            "text": text,
            "area": area,
            "channel": channel,
            "kwargs": kwargs,
        }

    bot.messages.send_message = fake_send_message


def print_registered_handlers(bot: OopzBot) -> None:
    print("\n[REGISTERED HANDLERS]")
    for event_name, handlers in getattr(bot.registry, "_handlers", {}).items():
        print(f"- {event_name}: {[h.__name__ for h in handlers]}")


def build_fake_message_event() -> str:
    """
    构造一个假的 Oopz WS 消息事件，直接喂给 bot._handle_ws_message(...)。
    """
    payload = {
        "event": 9,
        "body": json.dumps({
            "data": json.dumps({
                "id": "msg-001",
                "messageId": "msg-001",
                "area": "demo-area",
                "channel": "demo-channel",
                "text": "ping",
                "timestamp": "1712345678901",
                "sender": {
                    "id": "user-123",
                    "nickname": "Gary"
                },
                "mentionList": [],
                "styleTags": [],
                "attachments": [],
            })
        })
    }
    return json.dumps(payload)


def build_fake_heartbeat_event() -> str:
    payload = {
        "event": 254,
        "body": json.dumps({
            "ts": "1712345678999"
        })
    }
    return json.dumps(payload)


async def run_local_simulation():
    bot = OopzBot(build_test_config())
    install_debug_send_stub(bot)

    # -------------------------
    # 注册事件
    # -------------------------
    @bot.on_ready
    async def handle_ready(ctx):
        print("\n[READY]")
        print("ctx.bot =", type(ctx.bot).__name__)

    @bot.on_message
    async def handle_message(message, ctx):
        print("\n[MESSAGE HANDLER]")
        print("message =", message)
        text = message.get("text", "") if isinstance(message, dict) else getattr(message, "text", "")
        if text == "ping":
            await ctx.reply("pong")

    @bot.on_error
    async def handle_error(error, ctx):
        print("\n[ERROR HANDLER]")
        print("error =", error)

    @bot.on_reconnect
    async def handle_reconnect(ctx):
        print("\n[RECONNECT]")

    @bot.on_close
    async def handle_close(event, ctx):
        print("\n[CLOSE]")
        print("event =", event)

    @bot.on_raw_event
    async def handle_raw(event, ctx):
        print("\n[RAW EVENT]")
        print("name =", getattr(event, "name", None))
        print("event_type =", getattr(event, "event_type", None))

    print_registered_handlers(bot)

    # -------------------------
    # 手动触发 ready
    # -------------------------
    print("\n=== TRIGGER READY ===")
    bot._handle_open()
    await asyncio.sleep(0.05)

    # -------------------------
    # 手动喂一条 message 事件
    # -------------------------
    print("\n=== TRIGGER MESSAGE ===")
    bot._handle_ws_message(build_fake_message_event())
    await asyncio.sleep(0.05)

    # -------------------------
    # 手动喂 heartbeat，看 raw_event/其他事件走向
    # -------------------------
    print("\n=== TRIGGER HEARTBEAT ===")
    bot._handle_ws_message(build_fake_heartbeat_event())
    await asyncio.sleep(0.05)

    # -------------------------
    # 手动触发 error
    # -------------------------
    print("\n=== TRIGGER ERROR ===")
    bot._handle_error(RuntimeError("test error"))
    await asyncio.sleep(0.05)

    # -------------------------
    # 手动触发 reconnect
    # -------------------------
    print("\n=== TRIGGER RECONNECT ===")
    bot._handle_reconnect()
    await asyncio.sleep(0.05)

    # -------------------------
    # 手动触发 close
    # -------------------------
    print("\n=== TRIGGER CLOSE ===")
    bot._handle_close(1000, "normal close")
    await asyncio.sleep(0.05)

    print("\n=== DONE ===")


def run_real_bot():

    bot = OopzBot(build_test_config())

    @bot.on_ready
    async def handle_ready(ctx):
        print("[READY] connected")

    @bot.on_message
    async def handle_message(message, ctx):
        print("[MESSAGE]", message)

    @bot.on_error
    async def handle_error(error, ctx):
        print("[ERROR]", error)

    bot.run()


def main():
    # mode = os.getenv("OOPZ_MAIN_MODE", "local").strip().lower()
    #
    # if mode == "real":
    #     print("Running REAL bot mode...")
    #     run_real_bot()
    #     return
    #
    # print("Running LOCAL simulation mode...")
    # asyncio.run(run_local_simulation())
    run_real_bot()

if __name__ == "__main__":
    main()