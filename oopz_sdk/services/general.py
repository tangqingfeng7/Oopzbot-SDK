from __future__ import annotations

from oopz_sdk import models

from . import BaseService


class General(BaseService):
    async def get_daily_speech(self) -> models.DailySpeech:
        data = await self._request_data("GET", "/general/v1/speech")
        return models.DailySpeech.from_api(data)

