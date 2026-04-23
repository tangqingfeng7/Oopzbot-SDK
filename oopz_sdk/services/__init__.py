from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Mapping


from oopz_sdk.utils.payload import safe_json
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport, HttpResponse

if TYPE_CHECKING:
    # 仅给类型检查器 / IDE 用
    from oopz_sdk import OopzBot


class BaseService:
    """所有 service 的公共基类。

    owner 是持有本 service 的对象（OopzRESTClient 或 OopzBot），
    service 通过 owner 访问同级别的其它 service（见 `_require_service`）。

    约定
    ----
    - service 方法的必填参数（`area` / `channel` / `channel_id` / `uid` /
      `target` / `message_id` 等）缺失时，一律抛 `ValueError`，不再走
      "`OperationResult(ok=False, message="缺少 xxx")`" 软失败。
    - 后端业务失败仍用 `OperationResult.ok=False` 或 `OopzApiError` 体系
      表达，调用方按需 `if not result.ok:` 或 `try / except`。
    """

    def __init__(
            self,
            owner: OopzBot | object,
            config: OopzConfig,
            transport: HttpTransport,
            signer: Signer,
    ):
        self._bot = owner
        self._config = config
        self.transport = transport
        self.signer = signer

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

    async def _request_data_with_retry(
            self,
            method: str,
            path: str,
            *,
            params: Mapping[str, Any] | None = None,
            body: Mapping[str, Any] | None = None,
            max_attempts: int = 3,
            retry_on_429: bool = False,
    ) -> Any:
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
