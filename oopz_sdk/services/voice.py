from __future__ import annotations

import asyncio
import logging
from typing import Any

from oopz_sdk import models
from oopz_sdk.services import BaseService
from oopz_sdk.transport.voice_browser import BrowserVoiceTransport

logger = logging.getLogger(__name__)


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

    async def start(self) -> None:
        await self.backend.start()

    async def close(self) -> None:
        await self._stop_identity_heartbeat()
        await self.backend.close()

    async def join(
        self,
        *,
        area: str,
        channel: str,
        from_area: str = "",
        from_channel: str = "",
        rtc_uid: str | int | None = None,
    ) -> models.ChannelSign:
        uid = str(rtc_uid or self.backend.agora_uid)
        sign = await self._bot.channels.enter_channel(
            channel=channel,
            area=area,
            channel_type="VOICE",
            from_channel=from_channel,
            from_area=from_area,
            pid=uid,
        )
        if not sign.rtc_token or not sign.rtc_channel_name:
            raise RuntimeError("enter_channel returned no supplierSign/roomId")

        ok = await self.backend.join(
            app_id=self._config.agora_app_id,
            token=sign.rtc_token,
            room_id=sign.rtc_channel_name,
            uid=uid,
        )
        if not ok:
            raise RuntimeError("failed to join Agora room from browser backend")

        self._current_sign = sign
        self._current_area = area
        self._current_channel = channel
        self._current_uid = uid

        await self._send_identity_once()
        await self._start_identity_heartbeat()
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

    async def _send_identity_once(self) -> None:
        if not self._current_uid:
            return
        try:
            await self.backend.send_identity(self._config.person_uid, self._current_uid)
        except Exception:
            logger.debug("send identity failed", exc_info=True)

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
