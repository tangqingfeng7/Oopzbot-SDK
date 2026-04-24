from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric import rsa

from oopz_sdk.config.settings import OopzConfig


def make_config() -> OopzConfig:
    return OopzConfig(
        device_id="device",
        person_uid="person",
        jwt_token="jwt",
        private_key=rsa.generate_private_key(public_exponent=65537, key_size=2048),

    )
