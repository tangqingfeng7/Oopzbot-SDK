from __future__ import annotations

import random
import time
import uuid


class ClientMessageIdGenerator:
    def generate(self) -> str:
        timestamp_us = int(time.time() * 1_000_000)
        base_id = timestamp_us % 10_000_000_000_000
        suffix = random.randint(10, 99)
        return str(base_id * 100 + suffix)


def request_id() -> str:
    return str(uuid.uuid4())


def timestamp_ms() -> str:
    return str(int(time.time() * 1000))


def timestamp_us() -> str:
    return str(int(time.time() * 1_000_000))
