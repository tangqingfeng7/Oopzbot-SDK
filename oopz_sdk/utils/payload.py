from __future__ import annotations

import json
from typing import Any


def safe_json_loads(raw, fallback=None):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return fallback if fallback is not None else {}
    return fallback if fallback is not None else {}


def safe_json(response) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None