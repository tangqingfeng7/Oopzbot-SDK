from __future__ import annotations

import copy
import inspect
from typing import Any

from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport


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
        self.session = transport.session
        self._area_members_cache: dict[tuple[str, int, int], dict] = {}

    @staticmethod
    async def _await_if_needed(value):
        if inspect.isawaitable(value):
            return await value
        return value

    def _throttle(self) -> None:
        self.transport.throttle()

    async def _get(self, url_path: str, params: dict | None = None):
        return await self._await_if_needed(self.transport.get(url_path, params=params))

    async def _request(
        self,
        method: str,
        url_path: str,
        body: dict | None = None,
        params: dict | None = None,
    ):
        return await self._await_if_needed(
            self.transport.request(method, url_path, body=body, params=params)
        )

    async def _post(self, url_path: str, body: dict):
        return await self._await_if_needed(self.transport.post(url_path, body))

    async def _put(self, url_path: str, body: dict):
        return await self._await_if_needed(self.transport.put(url_path, body))

    async def _delete(self, url_path: str, body: dict | None = None):
        return await self._await_if_needed(self.transport.delete(url_path, body))

    async def _patch(self, url_path: str, body: dict):
        return await self._await_if_needed(self.transport.patch(url_path, body))

    def _resolve_area(self, area: str | None) -> str:
        value = str(area or self._config.default_area).strip()
        if not value:
            raise ValueError("缺少 area，且未配置 default_area")
        return value

    def _resolve_channel(self, channel: str | None) -> str:
        value = str(channel or self._config.default_channel).strip()
        if not value:
            raise ValueError("缺少 channel，且未配置 default_channel")
        return value

    @staticmethod
    def _safe_json(response) -> dict[str, Any] | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

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


__all__ = ["BaseService"]
