"""JWT parsing helpers used for local credential checks.

The payload can be decoded locally, but token validity remains a server-side
decision because this SDK does not possess the issuer's signing key.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode a JWT payload without validating its signature."""
    try:
        payload_part = str(token or "").split(".")[1]
        payload_part += "=" * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_part.encode("utf-8")))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def jwt_expired(token: str, *, now: float | None = None) -> bool:
    """Return whether the unverified JWT ``exp`` claim is already past."""
    expires_at = decode_jwt_payload(token).get("exp")
    if not isinstance(expires_at, (int, float)):
        return False
    return expires_at <= (time.time() if now is None else now)
