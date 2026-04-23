"""
联调脚本 python -m smoke.smoke
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


_load_env(ROOT / "test.env")

from PIL import Image as PILImage  # noqa: E402
from oopz_sdk import OopzConfig, OopzRESTClient  # noqa: E402
from oopz_sdk.client.bot import OopzBot  # noqa: E402
from oopz_sdk.exceptions import OopzApiError, OopzError  # noqa: E402
from oopz_sdk.models.segment import Image as ImageSegment  # noqa: E402


ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_YELLOW = "\033[33m"
ANSI_RESET = "\033[0m"


results: list[tuple[str, bool, str]] = []


def _short(value: Any, limit: int = 200) -> str:
    text = repr(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


async def step(name: str, awaitable_factory: Callable[[], Any], summarize=None) -> Any:
    """跑一步，返回值或 None（若失败）。"""
    started = time.time()
    print(f"{ANSI_YELLOW}[RUN]{ANSI_RESET} {name}")
    try:
        result = await awaitable_factory()
    except OopzApiError as exc:
        cost_ms = int((time.time() - started) * 1000)
        summary = f"OopzApiError status={exc.status_code} msg={exc.message!r} payload={_short(exc.payload, 400)}"
        print(f"{ANSI_RED}[FAIL]{ANSI_RESET} {name} ({cost_ms}ms): {summary}")
        results.append((name, False, summary))
        return None
    except OopzError as exc:
        cost_ms = int((time.time() - started) * 1000)
        summary = f"{type(exc).__name__}: {exc}"
        print(f"{ANSI_RED}[FAIL]{ANSI_RESET} {name} ({cost_ms}ms): {summary}")
        results.append((name, False, summary))
        return None
    except Exception as exc:
        cost_ms = int((time.time() - started) * 1000)
        summary = f"{type(exc).__name__}: {exc}"
        print(f"{ANSI_RED}[FAIL]{ANSI_RESET} {name} ({cost_ms}ms): {summary}")
        traceback.print_exc()
        results.append((name, False, summary))
        return None

    cost_ms = int((time.time() - started) * 1000)
    if summarize:
        summary = summarize(result)
    else:
        summary = _short(result)
    print(f"{ANSI_GREEN}[ OK ]{ANSI_RESET} {name} ({cost_ms}ms): {summary}")
    results.append((name, True, summary))
    return result


def _load_config() -> tuple[OopzConfig, dict[str, str]]:
    env = {
        "device_id": os.environ.get("OOPZ_DEVICE_ID", ""),
        "person_uid": os.environ.get("OOPZ_PERSON_UID", ""),
        "jwt_token": os.environ.get("OOPZ_JWT_TOKEN", ""),
        "area": os.environ.get("OOPZ_AREA_ID", ""),
        "channel": os.environ.get("OOPZ_CHANNEL_ID", ""),
        "target": os.environ.get("OOPZ_TARGET_UID", ""),
    }
    for key in ("device_id", "person_uid", "jwt_token", "area", "channel"):
        if not env[key]:
            raise SystemExit(f"环境变量缺失: {key}，请检查 test.env")

    private_key = os.environ.get("OOPZ_PRIVATE_KEY")
    private_key_file = os.environ.get("OOPZ_PRIVATE_KEY_FILE")
    if private_key_file:
        private_key = Path(private_key_file).read_text(encoding="utf-8")
    if not private_key:
        raise SystemExit("必须设置 OOPZ_PRIVATE_KEY 或 OOPZ_PRIVATE_KEY_FILE")

    config = OopzConfig(
        device_id=env["device_id"],
        person_uid=env["person_uid"],
        jwt_token=env["jwt_token"],
        private_key=private_key,
        default_area=env["area"],
        default_channel=env["channel"],
    )
    return config, env


def _make_test_png() -> str:
    buf = io.BytesIO()
    PILImage.new("RGB", (32, 32), color=(64, 128, 200)).save(buf, format="PNG")
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(buf.getvalue())
    tmp.close()
    return tmp.name


async def rest_smoke(sender: OopzRESTClient, env: dict[str, str]) -> None:
    area = env["area"]
    channel = env["channel"]
    target = env["target"]

    await step(
        "areas.get_joined_areas",
        lambda: sender.areas.get_joined_areas(),
        summarize=lambda r: f"count={len(r)}",
    )
    await step(
        "areas.get_area_info",
        lambda: sender.areas.get_area_info(area),
        summarize=lambda r: f"area_id={getattr(r, 'area_id', None)} name={getattr(r, 'name', None)!r}",
    )
    await step(
        "areas.get_area_members",
        lambda: sender.areas.get_area_members(area, offset_start=0, offset_end=5),
        summarize=lambda r: f"total={getattr(r, 'total_count', None)} fetched={len(getattr(r, 'members', []) or [])}",
    )
    await step(
        "channels.get_channel_setting_info",
        lambda: sender.channels.get_channel_setting_info(channel),
        summarize=lambda r: f"channel={getattr(r, 'channel', None)} name={getattr(r, 'name', None)!r}",
    )
    if target:
        await step(
            "areas.get_area_user_detail",
            lambda: sender.areas.get_area_user_detail(area=area, target=target),
            summarize=lambda r: f"higher_uid={getattr(r, 'higher_uid', None)!r} roles={len(getattr(r, 'roles', []) or [])}",
        )

    tag = f"smoke-ts-{int(time.time())}"
    send_msg = await step(
        "messages.send_message",
        lambda: sender.messages.send_message(f"SDK smoke {tag}", area=area, channel=channel),
        summarize=lambda r: f"message_id={getattr(r, 'message_id', None)}",
    )
    if send_msg is not None and getattr(send_msg, "message_id", None):
        await step(
            "messages.recall_message",
            lambda: sender.messages.recall_message(send_msg.message_id, area=area, channel=channel),
            summarize=lambda r: f"ok={getattr(r, 'ok', None)}",
        )

    await step(
        "messages.get_channel_messages",
        lambda: sender.messages.get_channel_messages(area=area, channel=channel, size=3),
        summarize=lambda r: f"fetched={len(r) if isinstance(r, list) else type(r).__name__}",
    )

    png_path = _make_test_png()
    upload = await step(
        "media.upload_file",
        lambda: sender.media.upload_file(png_path, file_type="IMAGE", ext=".png"),
        summarize=lambda r: f"file_key={getattr(r, 'file_key', None)} url={getattr(r, 'url', None)}",
    )

    if upload is not None:
        seg_msg = await step(
            "messages.send_message(ImageSegment)",
            lambda: sender.messages.send_message(
                ImageSegment.from_file(png_path),
                area=area,
                channel=channel,
            ),
            summarize=lambda r: f"message_id={getattr(r, 'message_id', None)}",
        )
        if seg_msg is not None and getattr(seg_msg, "message_id", None):
            await step(
                "messages.recall_message(ImageSegment)",
                lambda: sender.messages.recall_message(seg_msg.message_id, area=area, channel=channel),
                summarize=lambda r: f"ok={getattr(r, 'ok', None)}",
            )

    if target:
        session = await step(
            "messages.open_private_session",
            lambda: sender.messages.open_private_session(target),
            summarize=lambda r: f"session_id={getattr(r, 'session_id', None)}",
        )
        pm = await step(
            "messages.send_private_message",
            lambda: sender.messages.send_private_message(
                f"SDK smoke pm {tag}", target=target,
            ),
            summarize=lambda r: f"message_id={getattr(r, 'message_id', None)}",
        )
        if (
                session is not None
                and pm is not None
                and getattr(session, "session_id", None)
                and getattr(pm, "message_id", None)
        ):
            await step(
                "messages.recall_private_message",
                lambda: sender.messages.recall_private_message(
                    pm.message_id,
                    channel=session.session_id,
                    target=target,
                ),
                summarize=lambda r: f"ok={getattr(r, 'ok', None)}",
            )

    try:
        os.unlink(png_path)
    except OSError:
        pass


async def ws_smoke(config: OopzConfig) -> None:
    wait_seconds = int(os.environ.get("OOPZ_SMOKE_WS_WAIT_SECONDS", "0") or "0")
    if wait_seconds <= 0:
        return

    expect_message = os.environ.get("OOPZ_SMOKE_EXPECT_WS_MESSAGE", "0") == "1"

    bot = OopzBot(config)
    ready_event = asyncio.Event()
    received: list[Any] = []
    errors: list[Exception] = []

    @bot.on_ready
    async def _on_ready(ctx):
        ready_event.set()

    @bot.on_message
    async def _on_message(message, ctx):
        received.append(message)

    @bot.on_private_message
    async def _on_private_message(message, ctx):
        received.append(("private", message))

    @bot.on_error
    async def _on_error(ctx, error):
        errors.append(error)

    started = time.time()
    print(f"{ANSI_YELLOW}[RUN]{ANSI_RESET} ws.start + wait_on_ready")
    start_task = asyncio.create_task(bot.start())
    try:
        try:
            await asyncio.wait_for(ready_event.wait(), timeout=15)
        except asyncio.TimeoutError:
            cost = int((time.time() - started) * 1000)
            print(f"{ANSI_RED}[FAIL]{ANSI_RESET} ws.on_ready 超时 ({cost}ms)")
            results.append(("ws.on_ready", False, "timeout 15s"))
        else:
            cost = int((time.time() - started) * 1000)
            print(f"{ANSI_GREEN}[ OK ]{ANSI_RESET} ws.on_ready ({cost}ms)")
            results.append(("ws.on_ready", True, f"{cost}ms"))

            if expect_message:
                print(
                    f"{ANSI_YELLOW}[WAIT]{ANSI_RESET} 等待 {wait_seconds}s，让频道里发一条真实消息……"
                )
                await asyncio.sleep(wait_seconds)
            else:
                await asyncio.sleep(min(wait_seconds, 5))

            summary = f"received={len(received)} errors={len(errors)}"
            if received:
                results.append(("ws.inbound", True, summary))
                print(f"{ANSI_GREEN}[ OK ]{ANSI_RESET} ws.inbound {summary}")
            elif expect_message:
                results.append(("ws.inbound", False, summary))
                print(f"{ANSI_RED}[FAIL]{ANSI_RESET} ws.inbound 期望至少收到 1 条消息，实际 0")
            else:
                results.append(("ws.inbound", True, summary))
                print(f"{ANSI_GREEN}[ OK ]{ANSI_RESET} ws.inbound {summary}（未要求必须收到）")
    finally:
        try:
            await bot.stop()
        except Exception as exc:
            print(f"{ANSI_YELLOW}[WARN]{ANSI_RESET} bot.stop 异常: {exc}")
        if not start_task.done():
            start_task.cancel()
            try:
                await start_task
            except (asyncio.CancelledError, Exception):
                pass


def _print_summary() -> None:
    print()
    print("=" * 60)
    print("SMOKE SUMMARY")
    print("=" * 60)
    ok = [r for r in results if r[1]]
    bad = [r for r in results if not r[1]]
    print(f"passed: {len(ok)}, failed: {len(bad)}")
    for name, passed, summary in results:
        mark = f"{ANSI_GREEN}PASS{ANSI_RESET}" if passed else f"{ANSI_RED}FAIL{ANSI_RESET}"
        print(f"  [{mark}] {name}: {summary}")
    if bad:
        sys.exit(1)


async def _main() -> None:
    config, env = _load_config()
    try:
        async with OopzRESTClient(config) as sender:
            await rest_smoke(sender, env)
    finally:
        print(f"{ANSI_YELLOW}[DBG]{ANSI_RESET} entering ws_smoke ...")
        try:
            await ws_smoke(config)
        except Exception as exc:
            print(f"{ANSI_RED}[DBG]{ANSI_RESET} ws_smoke raised: {type(exc).__name__}: {exc}")
            traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    finally:
        _print_summary()
