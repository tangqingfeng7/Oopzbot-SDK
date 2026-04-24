from __future__ import annotations

import json
from typing import Any


_TRUE_LITERALS = frozenset({"true", "1", "yes", "y", "on"})
_FALSE_LITERALS = frozenset({"false", "0", "no", "n", "off", ""})


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


def coerce_bool(value: Any, *, default: bool = False) -> bool:
    """严格把 API payload 里的值转成 bool。

    Python 的 ``bool(value)`` 对非空字符串一律视作真，会把 ``"false"`` / ``"0"``
    误判成 ``True``。服务端在不同接口上可能把布尔字段序列化成字符串，
    各模型/响应层不能直接用 ``bool(...)`` 判断。

    规则（大小写不敏感，字符串会先 ``strip().lower()``）：

    - ``None`` → ``default``
    - ``bool`` → 原样
    - ``int`` / ``float`` → ``0`` 为 ``False``，其它为 ``True``
    - ``str``：
        * ``"true"`` / ``"1"`` / ``"yes"`` / ``"y"`` / ``"on"`` → ``True``
        * ``"false"`` / ``"0"`` / ``"no"`` / ``"n"`` / ``"off"`` / ``""`` → ``False``
        * 其它字面量 → ``default``（保守：默认值兜底，避免误判）
    - 其它类型 → ``default``
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_LITERALS:
            return True
        if normalized in _FALSE_LITERALS:
            return False
        return default
    return default