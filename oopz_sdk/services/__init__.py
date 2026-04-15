from __future__ import annotations

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

    def _post(self, url_path: str, body: dict):
        return self.transport.post(url_path, body)

    def _put(self, url_path: str, body: dict):
        return self.transport.put(url_path, body)

    def _delete(self, url_path: str, body: dict | None = None):
        return self.transport.delete(url_path, body)

    def _patch(self, url_path: str, body: dict):
        return self.transport.patch(url_path, body)

    def close(self) -> None:
        self.transport.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = ["BaseService"]
