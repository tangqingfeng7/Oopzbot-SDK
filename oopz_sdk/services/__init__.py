from __future__ import annotations

from typing import Any

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport


class BaseService:
    def __init__(self, config: OopzConfig, transport: HttpTransport, signer: Signer):
        self._config = config
        self.transport = transport
        self.signer = signer
        self.session = transport.session
        self._area_members_cache: dict[tuple[str, int, int], dict] = {}

    def _throttle(self) -> None:
        self.transport.throttle()

    def _get(self, url_path: str, params: dict | None = None):
        return self.transport.get(url_path, params=params)

    def _request(self, method: str, url_path: str, body: dict | None = None, params: dict | None = None):
        return self.transport.request(method, url_path, body=body, params=params)

    def _post(self, url_path: str, body: dict):
        return self.transport.post(url_path, body)

    def _put(self, url_path: str, body: dict):
        return self.transport.put(url_path, body)

    def _delete(self, url_path: str, body: dict | None = None):
        return self.transport.delete(url_path, body)

    def _patch(self, url_path: str, body: dict):
        return self.transport.patch(url_path, body)

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

    def close(self) -> None:
        self.transport.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = ["BaseService"]
