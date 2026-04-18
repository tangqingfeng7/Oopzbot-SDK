from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTransport(ABC):
    @abstractmethod
    async def request(
        self, method: str, url_path: str, body: dict | None = None, **kwargs: Any
    ):
        raise NotImplementedError

    @abstractmethod
    async def get(self, url_path: str, params: dict | None = None):
        raise NotImplementedError

    @abstractmethod
    async def post(self, url_path: str, body: dict):
        raise NotImplementedError

    @abstractmethod
    async def put(self, url_path: str, body: dict):
        raise NotImplementedError

    @abstractmethod
    async def patch(self, url_path: str, body: dict):
        raise NotImplementedError

    @abstractmethod
    async def delete(self, url_path: str, body: dict | None = None):
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
