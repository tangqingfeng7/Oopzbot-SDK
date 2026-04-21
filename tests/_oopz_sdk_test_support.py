from __future__ import annotations

import asyncio

from cryptography.hazmat.primitives.asymmetric import rsa

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config import OopzConfig
from oopz_sdk.services.message import Message
from oopz_sdk.transport.http import HttpTransport


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8") if text else b"{}"

    def __await__(self):
        async def _wrapped():
            return self

        return _wrapped().__await__()

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def _make_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _make_config(**overrides) -> OopzConfig:
    config = OopzConfig(
        device_id="device",
        person_uid="person",
        jwt_token="jwt",
        private_key=_make_private_key(),
        default_area="area",
        default_channel="channel",
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def _make_message_service(*, bot=None, config: OopzConfig | None = None, **config_overrides) -> Message:
    config = config or _make_config(**config_overrides)
    signer = Signer(config)
    transport = HttpTransport(config, signer)
    return Message(bot, config, transport, signer)


def _run(awaitable):
    return asyncio.run(awaitable)
