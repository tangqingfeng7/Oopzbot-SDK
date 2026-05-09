from __future__ import annotations

import logging
import time
import copy
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional, Hashable

T = TypeVar("T")

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry(Generic[T]):
    value: T
    ts: float
    expires_at: float | None = None


class TTLCache(Generic[T]):
    def __init__(self, *, max_entries: int = 1000, ttl: float = 300.0):
        self.max_entries = max_entries
        self.ttl = ttl
        self._store: OrderedDict[Hashable, CacheEntry[T]] = OrderedDict()

    def get(self, key: Hashable) -> Optional[T]:
        if self.max_entries <= 0:
            return None

        entry = self._store.get(key)
        if entry is None:
            return None

        now = time.time()
        if entry.expires_at is not None and now > entry.expires_at:
            self._store.pop(key, None)
            return None

        # LRU：访问后移动到末尾
        self._store.move_to_end(key)
        logger.debug(f"GET: key: {key}, value: {entry.value}")
        return copy.deepcopy(entry.value)

    def set(self, key: Hashable, value: T, *, ttl: float | None = None) -> None:
        if self.max_entries <= 0:
            self._store.clear()
            return

        now = time.time()
        real_ttl = self.ttl if ttl is None else ttl
        expires_at = None if real_ttl <= 0 else now + real_ttl

        self._store[key] = CacheEntry(
            value=copy.deepcopy(value),
            ts=now,
            expires_at=expires_at,
        )
        self._store.move_to_end(key)
        logger.debug(f"SET: key: {key}, value: {value}, expires_at: {expires_at}")
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def delete(self, key: Hashable) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def delete_where(self, predicate) -> int:
        keys = [key for key in self._store if predicate(key)]
        for key in keys:
            self._store.pop(key, None)
        return len(keys)