from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional
from urllib.parse import urlencode

import aiohttp

from oopz_sdk.auth.headers import build_oopz_headers
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzConnectionError, OopzApiError, OopzRateLimitError
from oopz_sdk.utils.payload import safe_json
from .base import BaseTransport
from .proxy import build_aiohttp_proxy

def _build_timeout(timeout: float | tuple[float, float]) -> aiohttp.ClientTimeout:
    if isinstance(timeout, tuple):
        connect_timeout, read_timeout = timeout
        return aiohttp.ClientTimeout(
            total=None,
            sock_connect=connect_timeout,
            sock_read=read_timeout,
        )
    return aiohttp.ClientTimeout(total=timeout)


@dataclass(slots=True)
class HttpResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    text: str

    def json(self):
        if not self.content:
            raise ValueError("no json")
        return json.loads(self.text)


class HttpTransport(BaseTransport):
    def __init__(self, config: OopzConfig, signer: Signer):
        self.config = config
        self.signer = signer
        self.headers = dict(config.get_headers())

        self._client_session: aiohttp.ClientSession | None = None
        self._rate_lock = asyncio.Lock()
        self._last_request_time = 0.0

    async def _ensure_client_session(self) -> aiohttp.ClientSession:
        if self._client_session is None or self._client_session.closed:
            self._client_session = aiohttp.ClientSession(headers=self.headers)
        return self._client_session

    async def throttle(self) -> None:
        interval = self.config.rate_limit_interval
        async with self._rate_lock:
            now = asyncio.get_running_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self._last_request_time = asyncio.get_running_loop().time()

    async def request(
        self,
        method: str,
        url_path: str,
        body: dict | None = None,
        **kwargs,
    ) -> HttpResponse:
        await self.throttle()

        params = kwargs.get("params")
        sign_path = url_path
        if params:
            sign_path = f"{url_path}?{urlencode(params)}"

        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
            data = body_str.encode("utf-8")
        elif method.upper() in ("POST", "PUT", "PATCH"):
            body_str = "{}"
            data = b"{}"
        else:
            body_str = ""
            data = None

        headers = {
            **self.headers,
            **build_oopz_headers(self.config, self.signer, sign_path, body_str),
        }

        url = self.config.base_url + url_path
        timeout = _build_timeout(self.config.request_timeout)
        proxy = build_aiohttp_proxy(url, self.config.proxy)

        session = await self._ensure_client_session()

        try:
            async with session.request(
                method,
                url,
                headers=headers,
                params=params,
                data=(
                    data
                    if body is not None or method.upper() in ("POST", "PUT", "PATCH")
                    else None
                ),
                timeout=timeout,
                proxy=proxy,
            ) as resp:
                text = await resp.text()
                return HttpResponse(
                    status_code=resp.status,
                    headers=dict(resp.headers),
                    text=text,
                    content=await resp.read(),
                )

        except asyncio.TimeoutError as exc:
            detail = str(exc).strip() or "timeout"
            raise OopzConnectionError(f"request failed: {detail}") from exc
        except aiohttp.ClientError as exc:
            raise OopzConnectionError(f"request failed: {exc}") from exc

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
        method = method.upper()

        session = await self._ensure_client_session()
        req_timeout = _build_timeout(timeout or self.config.request_timeout)
        proxy = build_aiohttp_proxy(url, self.config.proxy)

        try:
            async with session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=dict(headers or {}),
                    timeout=req_timeout,
                    proxy=proxy,
            ) as resp:
                content = await resp.read()
                try:
                    text = content.decode(resp.charset or "utf-8")
                except UnicodeDecodeError:
                    text = content.decode("utf-8", errors="replace")

                return HttpResponse(
                    status_code=resp.status,
                    headers=dict(resp.headers),
                    content=content,
                    text=text,
                )

        except asyncio.TimeoutError as exc:
            detail = str(exc).strip() or "timeout"
            raise OopzConnectionError(f"request failed: {detail}") from exc
        except aiohttp.ClientError as exc:
            raise OopzConnectionError(f"request failed: {exc}") from exc


    async def get(self, url_path: str, params: Optional[dict] = None) -> HttpResponse:
        return await self.request("GET", url_path, params=params)

    async def request_json(
            self,
            method: str,
            path: str,
            *,
            params: Mapping[str, Any] | None = None,
            body: Mapping[str, Any] | None = None,
    ) -> Any:
        resp = await self.request(
            method,
            path,
            params=params,
            body=body,
        )

        if resp.status_code == 429:
            payload = safe_json(resp)
            message = self._error_message(payload, default="HTTP 429")
            raise OopzRateLimitError(
                message=message, retry_after=self._retry_after_seconds(resp), status_code=429,
                payload=payload, response=resp
            )

        if resp.status_code != 200:
            payload = safe_json(resp)
            detail = self._error_message(payload, default=f"HTTP {resp.status_code}")
            raise OopzApiError(
                detail,
                status_code=resp.status_code,
                payload=payload,
                response=resp,
            )

        try:
            data = resp.json()
        except Exception as e:
            raise OopzApiError(
                f"response is not valid JSON: {e}",
                status_code=resp.status_code,
                response=resp,
            ) from e

        if not isinstance(data, dict):
            raise OopzApiError(
                "response is not valid dict",
                status_code=resp.status_code,
                payload=data,
                response=resp,
            )
        if not data.get("status"):
            message = data.get("message", "")
            raise OopzApiError(
                f"status is not True: {message}",
                status_code=resp.status_code,
                payload=data,
                response=resp,
            )
        return data

    async def request_data(
            self,
            method: str,
            path: str,
            *,
            params: Mapping[str, Any] | None = None,
            body: Mapping[str, Any] | None = None,
    ) -> Any:
        json_data = await self.request_json(
            method, path, params=params,
            body=body)
        if "data" not in json_data:
            raise OopzApiError(
                "response JSON does not contain 'data' field",
                status_code=200,
                payload=json_data,
            )
        return json_data["data"]

    async def request_data_with_retry(
            self,
            method: str,
            path: str,
            *,
            params: Mapping[str, Any] | None = None,
            body: Mapping[str, Any] | None = None,
            max_attempts: int = 3,
            retry_on_429: bool = False,
    ) -> Any:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        for attempt in range(1, max_attempts + 1):
            try:
                json_data = await self.request_json(method, path, params=params, body=body)
            except OopzRateLimitError as e:
                if not retry_on_429 or attempt >= max_attempts:
                    raise
                retry_after = e.retry_after if getattr(e, "retry_after", 0) else 0
                wait_seconds = retry_after if retry_after > 0 else min(attempt, 3)
                await asyncio.sleep(wait_seconds)
                continue

            if "data" not in json_data:
                raise OopzApiError(
                    "response JSON does not contain 'data' field",
                    status_code=200,
                    payload=json_data,
                )
            return json_data["data"]

        raise RuntimeError("unreachable code in request_data_with_retry")

    async def post(self, url_path: str, body: dict) -> HttpResponse:
        return await self.request("POST", url_path, body=body)

    async def put(self, url_path: str, body: dict) -> HttpResponse:
        return await self.request("PUT", url_path, body=body)

    async def patch(self, url_path: str, body: dict) -> HttpResponse:
        return await self.request("PATCH", url_path, body=body)

    async def delete(self, url_path: str, body: Optional[dict] = None) -> HttpResponse:
        return await self.request("DELETE", url_path, body=body)

    async def start(self):
        await self._ensure_client_session()

    async def close(self):
        if self._client_session and not self._client_session.closed:
            await self._client_session.close()

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
