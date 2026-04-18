"""Shared response helpers exposed from oopz_sdk."""

from __future__ import annotations

from typing import NoReturn

import requests

from oopz_sdk.exceptions import OopzApiError, OopzConnectionError, OopzRateLimitError

JsonObject = dict[str, object]
SUCCESS_CODES = (0, "0", 200, "200", "success")


def safe_json(response: requests.Response) -> object | None:
    try:
        return response.json()
    except ValueError:
        return None


def safe_json_object(response: requests.Response) -> JsonObject | None:
    payload = safe_json(response)
    return payload if isinstance(payload, dict) else None


def response_preview(response: requests.Response, limit: int = 200) -> str:
    return (response.text or "")[:limit]


def error_message_from_payload(
    payload: JsonObject | None, default_message: str
) -> str:
    if not payload:
        return default_message
    for key in ("message", "error", "msg", "reason"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default_message


def raise_connection_error(
    exc: requests.RequestException,
    default_message: str = "request failed",
) -> NoReturn:
    raise OopzConnectionError(f"{default_message}: {exc}") from exc


def raise_api_error(response: requests.Response, default_message: str) -> NoReturn:
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
        raise OopzRateLimitError(
            message=message,
            retry_after=retry_after,
            response=payload,
        )

    if not payload and response.text:
        message = f"{default_message}: {response_preview(response)}"
    raise OopzApiError(message, status_code=response.status_code, response=payload)


def raise_payload_error(
    payload: JsonObject | None,
    *,
    default_message: str,
    status_code: int = 200,
) -> NoReturn:
    raise OopzApiError(
        error_message_from_payload(payload, default_message),
        status_code=status_code,
        response=payload,
    )


def ensure_http_ok(
    response: requests.Response, default_message: str
) -> requests.Response:
    if response.status_code != 200:
        raise_api_error(response, default_message)
    return response


def is_success_payload(payload: JsonObject) -> bool:
    status = payload.get("status")
    code = payload.get("code")

    if status is True:
        return True
    if status is False:
        return code in SUCCESS_CODES
    if payload.get("success") is True:
        return True
    if payload.get("success") is False:
        return False
    return code in SUCCESS_CODES


def ensure_success_payload(
    response: requests.Response, default_message: str
) -> JsonObject:
    ensure_http_ok(response, default_message)
    payload = safe_json_object(response)
    if payload is None:
        raise OopzApiError(
            f"{default_message}: response is not JSON",
            status_code=response.status_code,
        )
    if not is_success_payload(payload):
        raise_payload_error(
            payload,
            default_message=default_message,
            status_code=response.status_code,
        )
    return payload


def require_dict_data(payload: JsonObject, default_message: str) -> JsonObject:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise_payload_error(payload, default_message=default_message)
    return data


def require_list_data(payload: JsonObject, default_message: str) -> list[object]:
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise_payload_error(payload, default_message=default_message)
    return data


def retry_delay_from_exception(
    exc: Exception, attempt: int, *, max_delay: float = 4.0
) -> float:
    if isinstance(exc, OopzRateLimitError) and exc.retry_after > 0:
        return float(exc.retry_after)
    return min(float(2 ** (attempt - 1)), max_delay)


__all__ = [
    "SUCCESS_CODES",
    "ensure_http_ok",
    "ensure_success_payload",
    "error_message_from_payload",
    "is_success_payload",
    "raise_api_error",
    "raise_connection_error",
    "raise_payload_error",
    "require_dict_data",
    "require_list_data",
    "response_preview",
    "retry_delay_from_exception",
    "safe_json",
    "safe_json_object",
]
