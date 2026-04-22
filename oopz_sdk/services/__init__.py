from __future__ import annotations

import asyncio
import copy
import inspect
from typing import TYPE_CHECKING, Any, Mapping, Tuple

from oopz_sdk.utils.payload import safe_json
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport, HttpResponse

if TYPE_CHECKING:
    # 仅给类型检查器 / IDE 用。运行时不会真的 import，避开
    # oopz_sdk 包初始化早期 `oopz_sdk.models` 顶层聚合未 ready 的问题。
    from oopz_sdk.models.base import OperationResult


class BaseService:
    """所有 service 的公共基类。

    owner 是持有本 service 的对象（OopzRESTClient 或 OopzBot），
    service 通过 owner 访问同级别的其它 service（见 `_require_service`）。

    约定
    ----
    - 对 **返回 `OperationResult` 的方法**，当 `area` / `channel` / `channel_id` /
      `uid` / `target` / `message_id` 等必填参数缺失时，一律走 **软失败**：
      直接 `return models.OperationResult(ok=False, message="缺少 xxx")`，
      而不是抛 `ValueError`。目的是让调用方可以用统一的 `if not result.ok:`
      分支处理"业务失败"和"参数缺失"。
    - 对 **返回具体领域模型的读操作**（如 `get_area_info` / `get_area_members`），
      缺必填参数时抛 `ValueError`，因为这类方法没有"软失败"的返回形态。
    """

    def __init__(
            self,
            owner,
            config: OopzConfig,
            transport: HttpTransport,
            signer: Signer,
    ):
        self._owner = owner
        self._config = config
        self.transport = transport
        self.signer = signer
        self._area_members_cache: dict[tuple[str, int, int], dict] = {}

    def _require_service(self, name: str):
        service = getattr(self._owner, name, None)
        if service is None:
            raise RuntimeError(f"{self.__class__.__name__} 缺少 {name} service")
        return service

    @staticmethod
    def _missing_arg_result(arg: str) -> OperationResult:
        """统一的"缺必填参数"软失败返回。

        见类 docstring 的"约定"部分：OperationResult 方法在 `area` /
        `channel` / `channel_id` / `uid` / `target` / `message_id`
        等必填参数缺失时统一用这个返回，避免各 service 自己手写
        `OperationResult(ok=False, message="缺少 xxx")` 产生文案漂移。
        """
        # 延迟 import：services/__init__ 会在 oopz_sdk 包初始化早期被加载
        # （OopzRESTClient -> services.*），此时 `oopz_sdk.models` 的顶层
        # 聚合还没 ready，直接从子模块拿 OperationResult 最稳。
        from oopz_sdk.models.base import OperationResult
        return OperationResult(ok=False, message=f"缺少 {arg}")

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
