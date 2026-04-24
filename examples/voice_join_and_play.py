"""语音频道加入与播放音频示例。

依赖：
- `Voice` 使用 `BrowserVoiceTransport`（Playwright + Chromium）驱动 Agora Web SDK。
  运行前需安装浏览器：`python -m playwright install chromium`。
- `OopzConfig.voice_browser_headless` 默认 True。调试时可传 False 查看真实窗口。
- `OopzConfig.agora_app_id` 已内置 Oopz 官方 AppID，一般无需改动。

流程：
1. `asyncio.create_task(bot.start())` 在后台启动 REST + WS（`start()` 本身会一直
   阻塞在 WS 事件循环里，不能直接 `await`）；通过 `@bot.on_ready` 等待连接建好。
2. `bot.voice.start()` 启动浏览器后端（首次较慢）。
3. `bot.voice.join(...)` 进入语音房；返回的 `ChannelSign` 里带 rtc 信息。
4. `bot.voice.play_url(...)` 或 `play_bytes(...)` / `play_file(...)` 推流到房间。
5. `bot.voice.leave()` 离开语音房（同时会踢自己）。
6. `bot.stop()` 会关闭 voice 后端、WS、REST 会话，后台任务随之结束。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from oopz_sdk import OopzBot, OopzConfig


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    area_id = "你的域ID"
    channel_id = "你的语音频道ID"

    config = OopzConfig(
        device_id="你的设备ID",
        person_uid="你的用户UID",
        jwt_token="你的JWT Token",
        private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    )

    bot = OopzBot(config)

    ready = asyncio.Event()

    @bot.on_ready
    async def _on_ready(_ctx):  # noqa: ANN001 - dispatcher 对 ready 事件只传 ctx
        ready.set()

    # WS 循环常驻，把 `bot.start()` 放到后台任务，主协程负责语音操作与清理
    bot_task = asyncio.create_task(bot.start(), name="oopz_bot_start")

    try:
        # 等 WS 建连完毕（on_ready 触发）；给 30 秒超时，防止网络异常时永远等下去
        try:
            await asyncio.wait_for(ready.wait(), timeout=30)
        except asyncio.TimeoutError:
            raise RuntimeError("WebSocket 未在 30s 内就绪，请检查 jwt_token / 网络") from None

        await bot.voice.start()

        sign = await bot.voice.join(area=area_id, channel=channel_id)
        print(
            f"加入成功：rtc_channel={sign.rtc_channel_name} "
            f"rtc_uid={bot.voice.agora_uid}"
        )

        demo = Path(__file__).with_name("demo.mp3")
        if demo.exists():
            await bot.voice.play_file(str(demo))
        else:
            await bot.voice.play_url("https://example.com/demo.mp3")

        await asyncio.sleep(10)

        await bot.voice.stop()
        await bot.voice.leave()
    finally:
        # stop() 会触发 WS 退出，后台任务随之结束；这里等它 join 回收，避免资源泄漏
        await bot.stop()
        if not bot_task.done():
            bot_task.cancel()
        try:
            await bot_task
        except (asyncio.CancelledError, Exception):
            # 后台任务的退出异常不是主流程的关注点，静默即可
            pass


if __name__ == "__main__":
    asyncio.run(main())
