from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

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

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


__all__ = ["BaseService"]
