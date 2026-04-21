from __future__ import annotations

import asyncio
import copy
import inspect
from typing import Any, Mapping, Tuple

from oopz_sdk.utils.payload import safe_json
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport, HttpResponse


class BaseService:
    def __init__(
            self,
            config: OopzConfig,
            transport: HttpTransport,
            signer: Signer,
            *,
            bot=None,
    ):
        self._bot = bot
        self._config = config
        self.transport = transport
        self.signer = signer
        self._area_members_cache: dict[tuple[str, int, int], dict] = {}

    def _require_service(self, name: str):
        owner = getattr(self, "_bot", None)
        if owner is None:
            raise RuntimeError(f"{self.__class__.__name__} 缺少 {name} service")
        service = getattr(owner, name, None)
        if service is None:
            raise RuntimeError(f"{self.__class__.__name__} 缺少 {name} service")
        return service

    async def _get(self, url_path: str, params: dict | None = None):
        return await self.transport.get(url_path, params=params)

    async def _request(
            self,
            method: str,
            url_path: str,
            body: dict | None = None,
            params: dict | None = None,
    ):
        return await self.transport.request(method, url_path, body=body, params=params)

    async def _post(self, url_path: str, body: dict):
        return await self.transport.post(url_path, body)

    async def _put(self, url_path: str, body: dict):
        return await self.transport.put(url_path, body)

    async def _delete(self, url_path: str, body: dict | None = None):
        return await self.transport.delete(url_path, body)

    async def _patch(self, url_path: str, body: dict):
        return await self.transport.patch(url_path, body)

    async def _request_data(
            self,
            method: str,
            path: str,
            *,
            params: Mapping[str, Any] | None = None,
            body: Mapping[str, Any] | None = None,
    ) -> Any:
        return await self.transport.request_data(method, path, params=params, body=body)

    async def _request_json_with_retry(
            self,
            method: str,
            path: str,
            *,
            params: Mapping[str, Any] | None = None,
            body: Mapping[str, Any] | None = None,
            max_attempts: int = 3,
            retry_on_429: bool = False,
    ) -> dict[str, Any]:
        return await self.transport.request_data_with_retry(
            method, path, params=params, body=body, max_attempts=max_attempts, retry_on_429=retry_on_429
        )

    async def request_raw(
            self,
            method: str,
            url: str,
            *,
            params: Mapping[str, Any] | None = None,
            data: bytes | str | None = None,
            headers: Mapping[str, str] | None = None,
            timeout: float | tuple[float, float] | None = None,
    ) -> HttpResponse:
        return await self.transport.request_raw(
            method, url, params=params, headers=headers, data=data,
             timeout=timeout
        )

    @staticmethod
    def _retry_after_seconds(response) -> int:
        try:
            return int(response.headers.get("Retry-After", "0") or "0")
        except Exception:
            return 0

    @staticmethod
    def _error_message(payload: dict[str, Any] | None, default: str = "未知错误") -> str:
        if not isinstance(payload, dict):
            return default
        for key in ("message", "error", "msg", "reason"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return default

    def _error_payload(
            self,
            message: str,
            *,
            payload: dict[str, Any] | None = None,
            default: str = "未知错误",
    ) -> dict[str, Any]:
        if isinstance(payload, dict):
            copied = copy.deepcopy(payload)
            if copied.get("error"):
                return copied
            copied["error"] = self._error_message(copied, default)
            return copied
        return {"error": str(message or default)}

    def _model_error(
            self,
            model_cls,
            message: str,
            *,
            response=None,
            payload: dict[str, Any] | None = None,
            default: str = "未知错误",
            **fields,
    ):
        error_payload = self._error_payload(message, payload=payload, default=default)
        build_fields = {"payload": error_payload, **fields}
        if response is not None:
            try:
                signature = inspect.signature(model_cls)
            except (TypeError, ValueError):
                signature = None
            if signature is not None:
                parameters = signature.parameters
                accepts_kwargs = any(
                    parameter.kind is inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters.values()
                )
                if "response" in parameters or accepts_kwargs:
                    build_fields["response"] = response
        return model_cls(**build_fields)

    def _invalid_dict_item_payload(
            self,
            values: object,
            message: str,
            *,
            list_key: str,
            payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(values, list):
            error_payload = self._error_payload(message, payload=payload, default=message)
            error_payload["error"] = message
            error_payload["list_key"] = list_key
            error_payload["invalid_type"] = type(values).__name__
            return error_payload
        for index, item in enumerate(values):
            if not isinstance(item, dict):
                error_payload = self._error_payload(message, payload=payload, default=message)
                error_payload["error"] = message
                error_payload["list_key"] = list_key
                error_payload["invalid_index"] = index
                error_payload["invalid_type"] = type(item).__name__
                return error_payload
        return None

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @classmethod
    def _raise_api_error(cls, response, default_message: str) -> None:
        from oopz_sdk import OopzRateLimitError, OopzApiError
        payload = safe_json(response)
        message = default_message

        if response.status_code == 429:
            try:
                retry_after = int(response.headers.get("Retry-After", "0") or "0")
            except Exception:
                retry_after = 0

            if payload:
                message = str(payload.get("message") or payload.get("error") or message)
            elif response.text:
                message = f"{message}: {response.text[:200]}"

            raise OopzRateLimitError(
                message=message,
                retry_after=retry_after,
                response=payload,
            )

        if payload:
            message = str(payload.get("message") or payload.get("error") or message)
        elif response.text:
            message = f"{message}: {response.text[:200]}"

        raise OopzApiError(message, status_code=response.status_code, response=payload)


__all__ = ["BaseService"]
