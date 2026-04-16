from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTransport(ABC):
    @abstractmethod
    def request(self, method: str, url_path: str, body: dict | None = None, **kwargs: Any):
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
