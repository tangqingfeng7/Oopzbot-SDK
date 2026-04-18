from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional
from urllib.parse import urlencode

import aiohttp

from oopz_sdk.auth.headers import build_oopz_headers
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig, ProxyConfig
from oopz_sdk.exceptions import OopzConnectionError

from .base import BaseTransport
from .proxy import build_aiohttp_proxy, build_requests_proxies


async def _await_if_needed(value):
    if inspect.isawaitable(value):
        return await value
    return value


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

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _SessionFacade:
    def __init__(self, transport: "HttpTransport", config: OopzConfig):
        self._transport = transport
        self.headers = dict(config.get_headers())
        self.proxies = build_requests_proxies(getattr(config, "proxy", ProxyConfig()))

    async def request(self, method: str, url: str, **kwargs):
        return await self._transport._perform_request(method, url, **kwargs)

    async def get(self, url: str, **kwargs):
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs):
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs):
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs):
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs):
        return await self.request("DELETE", url, **kwargs)

    async def close(self) -> None:
        await self._transport.close()


class HttpTransport(BaseTransport):
    def __init__(self, config: OopzConfig, signer: Signer):
        self.config = config
        self.signer = signer
        self.session = _SessionFacade(self, config)
        self._client_session: aiohttp.ClientSession | None = None
        self._rate_lock = asyncio.Lock()
        self._last_request_time = 0.0

    async def throttle(self) -> None:
        interval = self.config.rate_limit_interval
        async with self._rate_lock:
            now = asyncio.get_running_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self._last_request_time = asyncio.get_running_loop().time()

    async def _ensure_client_session(self) -> aiohttp.ClientSession:
        if self._client_session is None or self._client_session.closed:
            self._client_session = aiohttp.ClientSession()
        return self._client_session

    async def _adapt_response(self, response) -> HttpResponse:
        if isinstance(response, HttpResponse):
            return response
        if not isinstance(response, aiohttp.ClientResponse):
            return response

        content = await response.read()
        try:
            text = content.decode(response.charset or "utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
        response.release()
        return HttpResponse(
            status_code=response.status,
            headers=dict(response.headers),
            content=content,
            text=text,
        )

    async def _perform_request(self, method: str, url: str, **kwargs):
        client_session = await self._ensure_client_session()
        proxy = kwargs.pop("proxy", None) or build_aiohttp_proxy(url, self.config.proxy)
        timeout = kwargs.pop("timeout", self.config.request_timeout)
        kwargs.pop("stream", None)
        request_timeout = _build_timeout(timeout)

        try:
            response = await _await_if_needed(
                client_session.request(
                    method,
                    url,
                    timeout=request_timeout,
                    proxy=proxy,
                    **kwargs,
                )
            )
        except aiohttp.ClientError as exc:
            raise OopzConnectionError(f"request failed: {exc}") from exc

        return await self._adapt_response(response)

    async def request(self, method: str, url_path: str, body: dict | None = None, **kwargs):
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
            **self.session.headers,
            **build_oopz_headers(self.config, self.signer, sign_path, body_str),
        }
        url = self.config.base_url + url_path
        try:
            return await _await_if_needed(
                self.session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=(
                        data
                        if body is not None or method.upper() in ("POST", "PUT", "PATCH")
                        else None
                    ),
                    timeout=self.config.request_timeout,
                )
            )
        except aiohttp.ClientError as exc:
            raise OopzConnectionError(f"request failed: {exc}") from exc

    async def get(self, url_path: str, params: Optional[dict] = None):
        return await self.request("GET", url_path, params=params)

    async def post(self, url_path: str, body: dict):
        return await self.request("POST", url_path, body=body)

    async def put(self, url_path: str, body: dict):
        return await self.request("PUT", url_path, body=body)

    async def patch(self, url_path: str, body: dict):
        return await self.request("PATCH", url_path, body=body)

    async def delete(self, url_path: str, body: Optional[dict] = None):
        return await self.request("DELETE", url_path, body=body)

    async def close(self) -> None:
        if self._client_session is not None and not self._client_session.closed:
            await self._client_session.close()
