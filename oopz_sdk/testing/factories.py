from __future__ import annotations

from oopz_sdk.config.settings import OopzConfig


def make_config() -> OopzConfig:
    return OopzConfig(
        device_id="device",
        person_uid="person",
        jwt_token="jwt",
        private_key=None,
        default_area="area",
        default_channel="channel",
    )
