from __future__ import annotations

import inspect
from typing import Any

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport


class BaseService:
    def __init__(
        self,
        config: OopzConfig,
        transport: HttpTransport,
        signer: Signer,
        *,
        bot=None,
    ):
        self._bot = bot
        self._config = config
        self.transport = transport
        self.signer = signer
        self.session = transport.session
        self._area_members_cache: dict[tuple[str, int, int], dict] = {}

    @staticmethod
    async def _await_if_needed(value):
        if inspect.isawaitable(value):
            return await value
        return value

    def _throttle(self) -> None:
        self.transport.throttle()

    async def _get(self, url_path: str, params: dict | None = None):
        return await self._await_if_needed(self.transport.get(url_path, params=params))

    async def _request(
        self,
        method: str,
        url_path: str,
        body: dict | None = None,
        params: dict | None = None,
    ):
        return await self._await_if_needed(
            self.transport.request(method, url_path, body=body, params=params)
        )

    async def _post(self, url_path: str, body: dict):
        return await self._await_if_needed(self.transport.post(url_path, body))

    async def _put(self, url_path: str, body: dict):
        return await self._await_if_needed(self.transport.put(url_path, body))

    async def _delete(self, url_path: str, body: dict | None = None):
        return await self._await_if_needed(self.transport.delete(url_path, body))

    async def _patch(self, url_path: str, body: dict):
        return await self._await_if_needed(self.transport.patch(url_path, body))

    def _resolve_area(self, area: str | None) -> str:
        value = str(area or self._config.default_area).strip()
        if not value:
            raise ValueError("缺少 area，且未配置 default_area")
        return value

    def _resolve_channel(self, channel: str | None) -> str:
        value = str(channel or self._config.default_channel).strip()
        if not value:
            raise ValueError("缺少 channel，且未配置 default_channel")
        return value

    @staticmethod
    def _safe_json(response) -> dict[str, Any] | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


__all__ = ["BaseService"]
