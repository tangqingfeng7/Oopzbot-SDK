"""Oopz SDK 共享响应处理逻辑。"""

from __future__ import annotations

from typing import NoReturn

import requests

from .exceptions import OopzApiError, OopzRateLimitError
from .models import JsonObject

SUCCESS_CODES = (0, "0", 200, "200", "success")


def safe_json(response: requests.Response) -> object | None:
    """安全解析 JSON。"""
    try:
        return response.json()
    except ValueError:
        return None


def safe_json_object(response: requests.Response) -> JsonObject | None:
    """安全解析 JSON 对象。"""
    payload = safe_json(response)
    return payload if isinstance(payload, dict) else None


def response_preview(response: requests.Response, limit: int = 200) -> str:
    """返回响应摘要文本。"""
    return (response.text or "")[:limit]


def error_message_from_payload(payload: JsonObject | None, default_message: str) -> str:
    """从平台响应中提取错误信息。"""
    if not payload:
        return default_message
    for key in ("message", "error", "msg"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default_message


def raise_api_error(response: requests.Response, default_message: str) -> NoReturn:
    """将 HTTP 响应翻译为 SDK 异常。"""
    payload = safe_json_object(response)
    message = error_message_from_payload(payload, default_message)

    if response.status_code == 429:
        retry_after = 0
        try:
            retry_after = int(response.headers.get("Retry-After", "0") or "0")
        except Exception:
            retry_after = 0
        if not payload and response.text:
            message = f"{default_message}: {response_preview(response)}"
        raise OopzRateLimitError(message=message, retry_after=retry_after, response=payload)

    if not payload and response.text:
        message = f"{default_message}: {response_preview(response)}"
    raise OopzApiError(message, status_code=response.status_code, response=payload)


def raise_payload_error(
    payload: JsonObject | None,
    *,
    default_message: str,
    status_code: int = 200,
) -> NoReturn:
    """将业务失败翻译为 SDK 异常。"""
    message = error_message_from_payload(payload, default_message)
    raise OopzApiError(message, status_code=status_code, response=payload)


def ensure_http_ok(response: requests.Response, default_message: str) -> requests.Response:
    """确保响应 HTTP 状态成功。"""
    if response.status_code != 200:
        raise_api_error(response, default_message)
    return response


def is_success_payload(payload: JsonObject) -> bool:
    """判断平台业务层是否成功。"""
    status = payload.get("status")
    code = payload.get("code")

    if status is True:
        return True
    if status is False:
        return code in SUCCESS_CODES
    if code in SUCCESS_CODES:
        return True
    return False


def ensure_success_payload(response: requests.Response, default_message: str) -> JsonObject:
    """确保 HTTP 与业务状态都成功，并返回 JSON 对象。"""
    ensure_http_ok(response, default_message)
    payload = safe_json_object(response)
    if payload is None:
        raise OopzApiError(f"{default_message}: 响应非 JSON", status_code=response.status_code)
    if not is_success_payload(payload):
        raise_payload_error(payload, default_message=default_message, status_code=response.status_code)
    return payload


def require_dict_data(payload: JsonObject, default_message: str) -> JsonObject:
    """提取字典型 data 字段。"""
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise_payload_error(payload, default_message=default_message)
    return data


def require_list_data(payload: JsonObject, default_message: str) -> list[object]:
    """提取列表型 data 字段。"""
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise_payload_error(payload, default_message=default_message)
    return data
