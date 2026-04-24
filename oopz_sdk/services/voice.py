from __future__ import annotations

import asyncio
import logging
from typing import Any

from oopz_sdk import models
from oopz_sdk.services import BaseService
from oopz_sdk.transport.voice_browser import BrowserVoiceTransport

logger = logging.getLogger("oopz_sdk.services.voice")


class Voice(BaseService):
    """High-level voice orchestration service.

    Responsibilities:
    - call Oopz `enter_channel(..., channel_type="VOICE")` to obtain `ChannelSign`
    - join/publish via `BrowserVoiceTransport`
    - periodically re-send the identity bridge payload used by Oopzbot
    """

    def __init__(self, owner, config, transport, signer):
        super().__init__(owner, config, transport, signer)
        self.backend = BrowserVoiceTransport(config)
        self._current_sign: models.ChannelSign | None = None
        self._current_area: str | None = None
        self._current_channel: str | None = None
        self._current_uid: str | None = None
        self._identity_task: asyncio.Task | None = None

    @property
    def agora_uid(self) -> str:
        return self.backend.agora_uid

    @property
    def current_sign(self) -> models.ChannelSign | None:
        return self._current_sign

    async def _cleanup_failed_join(self, area: str, channel: str) -> None:
        """
        `enter_channel` 成功后若浏览器/Agora 未就绪或加入失败，服务端可能仍认为在语音房；
        尽力退出 Agora 并调用服务端 `leave_voice_channel`，避免残留状态。
        """
        try:
            await self.backend.leave()
        except Exception:
            logger.debug("backend.leave after failed Voice.join", exc_info=True)
        try:
            await self._bot.channels.leave_voice_channel(
                channel=channel,
                area=area,
                target=self._config.person_uid,
            )
        except Exception:
            logger.debug("leave_voice_channel after failed Voice.join", exc_info=True)

    async def start(self) -> None:
        await self.backend.start()

    async def close(self) -> None:
        await self._stop_identity_heartbeat()
        await self.backend.close()

    @staticmethod
    def _coerce_rtc_uid(rtc_uid: str | int | None, *, default: str) -> str:
        """把 rtc_uid 规整成后端必须的「整数形式字符串」。

        ``BrowserVoiceTransport.join`` / ``send_identity`` 内部都会对 uid 做 ``int(...)``，
        非数字字符串（例如 ``"user-abc"``）不在服务端 ``enter_channel`` 之前校验，
        会导致 Oopz 服务端已记录加入语音频道，然后浏览器侧才因为 ``int()`` 崩溃，
        还得走失败清理、留下脏状态。统一在这里把不合法值挡在请求之前。
        """
        if rtc_uid is None:
            return default
        # bool 是 int 的子类，但当 UID 显然是语义错误
        if isinstance(rtc_uid, bool):
            raise TypeError(f"rtc_uid must be an integer, got bool {rtc_uid!r}")
        if isinstance(rtc_uid, int):
            if rtc_uid < 0:
                raise ValueError(f"rtc_uid must be non-negative, got {rtc_uid!r}")
            return str(rtc_uid)
        if isinstance(rtc_uid, str):
            stripped = rtc_uid.strip()
            if not stripped:
                return default
            try:
                parsed = int(stripped)
            except ValueError as exc:
                raise ValueError(
                    f"rtc_uid must be an integer-compatible string, got {rtc_uid!r}"
                ) from exc
            if parsed < 0:
                raise ValueError(f"rtc_uid must be non-negative, got {rtc_uid!r}")
            return str(parsed)
        raise TypeError(
            f"rtc_uid must be int or str of int, got {type(rtc_uid).__name__}"
        )

    async def join(
        self,
        *,
        area: str,
        channel: str,
        from_area: str = "",
        from_channel: str = "",
        rtc_uid: str | int | None = None,
    ) -> models.ChannelSign:
        uid = self._coerce_rtc_uid(rtc_uid, default=self.backend.agora_uid)
        sign = await self._bot.channels.enter_channel(
            channel=channel,
            area=area,
            channel_type="VOICE",
            from_channel=from_channel,
            from_area=from_area,
            pid=uid,
        )
        if not sign.rtc_token or not sign.rtc_channel_name:
            await self._cleanup_failed_join(area, channel)
            raise RuntimeError("enter_channel returned no supplierSign/roomId")

        try:
            ok = await self.backend.join(
                app_id=self._config.agora_app_id,
                token=sign.rtc_token,
                room_id=sign.rtc_channel_name,
                uid=uid,
            )
        except Exception:
            await self._cleanup_failed_join(area, channel)
            raise

        if not ok:
            await self._cleanup_failed_join(area, channel)
            raise RuntimeError("failed to join Agora room from browser backend")

        self._current_sign = sign
        self._current_area = area
        self._current_channel = channel
        self._current_uid = uid

        try:
            # 首次发送身份绑定：浏览器端没有可用 WebSocket 时 agoraSendIdentity 会
            # 返回 {ok:false}，BrowserVoiceTransport.send_identity 因此返回 False。
            # 这种情况下机器人虽然进了 Agora 房间，但服务端/其他客户端没法把 Oopz
            # UID 与 Agora UID 对齐，必须视为加入失败、完整回滚；心跳循环里的后续
            # 失败（_send_identity_once）可以容忍，记录 debug 日志即可。
            sent = await self._send_identity_once()
            if not sent:
                raise RuntimeError(
                    "voice identity bridge not ready: "
                    "browser WebSocket missing or agoraSendIdentity returned ok=false"
                )
            await self._start_identity_heartbeat()
        except Exception:
            try:
                await self.leave()
            except Exception:
                logger.debug("leave after post-join failure in Voice.join", exc_info=True)
            raise
        return sign

    async def leave(self) -> None:
        await self._stop_identity_heartbeat()
        try:
            await self.backend.leave()
        finally:
            if self._current_area and self._current_channel:
                try:
                    await self._bot.channels.leave_voice_channel(
                        channel=self._current_channel,
                        area=self._current_area,
                        target=self._config.person_uid,
                    )
                except Exception:
                    logger.debug("leave_voice_channel failed", exc_info=True)
            self._current_sign = None
            self._current_area = None
            self._current_channel = None
            self._current_uid = None

    async def play_url(self, url: str) -> dict[str, Any]:
        if not url.strip():
            raise ValueError("url cannot be empty")
        return await self.backend.play_url(url)

    async def play_file(self, file_path: str, *, mime_type: str | None = None) -> dict[str, Any]:
        if not file_path.strip():
            raise ValueError("file_path cannot be empty")
        return await self.backend.play_file(file_path, mime_type=mime_type)

    async def play_bytes(self, data: bytes, *, mime_type: str = "audio/mpeg") -> dict[str, Any]:
        if not data:
            raise ValueError("data cannot be empty")
        return await self.backend.play_bytes(data, mime_type=mime_type)

    async def stop(self) -> None:
        await self.backend.stop_audio()

    async def pause(self) -> bool:
        return await self.backend.pause()

    async def resume(self) -> bool:
        return await self.backend.resume()

    async def seek(self, seconds: float) -> bool:
        return await self.backend.seek(seconds)

    async def set_volume(self, volume: int) -> bool:
        return await self.backend.set_volume(volume)

    async def get_state(self) -> str:
        return await self.backend.get_state()

    async def get_current_time(self) -> float:
        return await self.backend.get_current_time()

    async def _send_identity_once(self) -> bool:
        """向浏览器桥发送身份绑定。返回 True 代表浏览器端 ack 成功。

        首次失败需要在 ``join`` 里触发回滚，后续心跳循环里失败只记日志、等下次重试。
        """
        if not self._current_uid:
            return False
        try:
            ok = await self.backend.send_identity(self._config.person_uid, self._current_uid)
        except Exception:
            logger.debug("send identity failed", exc_info=True)
            return False
        return bool(ok)

    async def _start_identity_heartbeat(self) -> None:
        await self._stop_identity_heartbeat()

        async def _loop() -> None:
            while True:
                await asyncio.sleep(10)
                await self._send_identity_once()

        self._identity_task = asyncio.create_task(_loop(), name="oopz_voice_identity_heartbeat")

    async def _stop_identity_heartbeat(self) -> None:
        task = self._identity_task
        self._identity_task = None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
