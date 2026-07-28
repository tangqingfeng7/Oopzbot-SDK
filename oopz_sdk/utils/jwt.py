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


def jwt_expired(token: str, *, now: float | None = None, leeway: float = 0.0) -> bool:
    """Return whether the unverified JWT ``exp`` claim is already past.

    ``leeway`` (seconds) guards against a fast local clock: the token is only
    reported as expired once it is past ``exp`` by at least ``leeway`` seconds,
    so a small clock skew will not wrongly reject an otherwise valid token.
    """
    expires_at = decode_jwt_payload(token).get("exp")
    if not isinstance(expires_at, (int, float)):
        return False
    now_value = time.time() if now is None else now
    return expires_at <= (now_value - leeway)
