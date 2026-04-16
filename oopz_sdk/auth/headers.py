from __future__ import annotations

from oopz_sdk.config.settings import OopzConfig

from .signer import Signer


def build_oopz_headers(config: OopzConfig, signer: Signer, url_path: str, body_str: str) -> dict[str, str]:
    ts = signer.timestamp_ms()
    md5 = signer.body_md5(url_path, body_str)
    signature = signer.sign(md5 + ts)
    return {
        "Oopz-Sign": signature,
        "Oopz-Request-Id": signer.request_id(),
        "Oopz-Time": ts,
        "Oopz-App-Version-Number": config.app_version,
        "Oopz-Channel": config.channel,
        "Oopz-Device-Id": config.device_id,
        "Oopz-Platform": config.platform,
        "Oopz-Web": str(config.web).lower(),
        "Oopz-Person": config.person_uid,
        "Oopz-Signature": config.jwt_token,
    }
