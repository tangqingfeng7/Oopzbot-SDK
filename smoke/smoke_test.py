"""Oopz SDK 真实环境联调脚本。"""

from __future__ import annotations

import os
import tempfile
import threading
import time

from PIL import Image

from oopz_sdk import ChatMessageEvent, LifecycleEvent, OopzClient, OopzConfig, OopzSender


def _read_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量: {name}")
    return value


def _read_private_key() -> str:
    file_path = os.getenv("OOPZ_PRIVATE_KEY_FILE", "").strip()
    if file_path:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    return _read_required_env("OOPZ_PRIVATE_KEY")


def _build_config() -> OopzConfig:
    return OopzConfig(
        device_id=_read_required_env("OOPZ_DEVICE_ID"),
        person_uid=_read_required_env("OOPZ_PERSON_UID"),
        jwt_token=_read_required_env("OOPZ_JWT_TOKEN"),
        private_key=_read_private_key(),
        default_area=_read_required_env("OOPZ_AREA_ID"),
        default_channel=_read_required_env("OOPZ_CHANNEL_ID"),
    )


def _create_temp_image() -> str:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    handle.close()
    image = Image.new("RGB", (16, 16), color=(46, 125, 50))
    image.save(handle.name, format="PNG")
    return handle.name


def _run_websocket_smoke(config: OopzConfig) -> None:
    wait_seconds = int(os.getenv("OOPZ_SMOKE_WS_WAIT_SECONDS", "20") or "20")
    require_message = os.getenv("OOPZ_SMOKE_EXPECT_WS_MESSAGE", "").strip() == "1"
    lifecycle_event = threading.Event()
    message_event = threading.Event()
    lifecycle_states: list[str] = []
    failure_reason = {"value": ""}

    def on_lifecycle(event: LifecycleEvent) -> None:
        lifecycle_states.append(event.state)
        print(f"[WS] 生命周期: {event.state} reason={event.reason} error={event.error}")
        if event.state == "auth_failed":
            failure_reason["value"] = event.reason or event.error or "认证失败"
            lifecycle_event.set()
        if event.state == "auth_ok":
            lifecycle_event.set()

    def on_message(event: ChatMessageEvent) -> None:
        print(f"[WS] 收到消息: area={event.area} channel={event.channel} person={event.person} content={event.content[:60]}")
        message_event.set()

    client = OopzClient(
        config,
        on_chat_message=on_message,
        on_lifecycle_event=on_lifecycle,
    )
    client.start_async()
    if not lifecycle_event.wait(wait_seconds):
        client.stop()
        raise RuntimeError(f"WebSocket 在 {wait_seconds}s 内未完成认证，生命周期={lifecycle_states}")
    if failure_reason["value"]:
        client.stop()
        raise RuntimeError(f"WebSocket 认证失败: {failure_reason['value']}")
    if require_message and not message_event.wait(wait_seconds):
        client.stop()
        raise RuntimeError(
            "WebSocket 已认证成功，但在等待窗口内未收到真实消息。"
            "如需验证收消息，请用另一个账号向测试频道发言。"
        )
    client.stop()
    print("[WS] WebSocket 联调完成")


def main() -> None:
    config = _build_config()
    smoke_image = os.getenv("OOPZ_SMOKE_IMAGE", "").strip()
    target_uid = os.getenv("OOPZ_TARGET_UID", "").strip()
    created_temp_image = ""

    if not smoke_image:
        created_temp_image = _create_temp_image()
        smoke_image = created_temp_image

    try:
        with OopzSender(config) as sender:
            joined = sender.get_joined_areas()
            print(f"[HTTP] 已加入域数量: {len(joined.areas)} from_cache={joined.from_cache}")

            detail = sender.get_self_detail()
            print(f"[HTTP] 当前账号: uid={detail.uid} name={detail.name} from_cache={detail.from_cache}")

            channels = sender.get_area_channels()
            channel_count = sum(len(group.get('channels') or []) for group in channels.groups)
            print(f"[HTTP] 频道数量: {channel_count} from_cache={channels.from_cache}")

            members = sender.get_area_members()
            print(
                "[HTTP] 域成员: total=%s online=%s from_cache=%s"
                % (members.get("totalCount"), members.get("onlineCount"), members.get("from_cache"))
            )

            send_result = sender.send_message("Oopz SDK v0.4 smoke test", auto_recall=False)
            print(f"[HTTP] 频道发消息成功: {send_result.message_id}")

            recall_result = sender.recall_message(send_result.message_id, timestamp=send_result.timestamp)
            print(f"[HTTP] 撤回消息成功: {recall_result.message}")

            upload_result = sender.upload_file(smoke_image, file_type="IMAGE", ext=os.path.splitext(smoke_image)[1] or ".png")
            print(f"[HTTP] 上传成功: {upload_result.attachment.url}")

            image_message = sender.upload_and_send_image(smoke_image, text="smoke 图片消息")
            print(f"[HTTP] 发图成功: {image_message.message_id}")

            time.sleep(1.0)
            sender.recall_message(image_message.message_id, timestamp=image_message.timestamp)
            print("[HTTP] 图片消息撤回成功")

            if target_uid:
                dm_result = sender.send_private_message(target_uid, "Oopz SDK v0.4 私信联调")
                print(f"[HTTP] 私信成功: target={dm_result.target} message_id={dm_result.message_id}")
            else:
                print("[HTTP] 未提供 OOPZ_TARGET_UID，跳过私信联调")

        _run_websocket_smoke(config)
        print("联调全部完成")
    finally:
        if created_temp_image and os.path.exists(created_temp_image):
            os.remove(created_temp_image)


if __name__ == "__main__":
    main()
