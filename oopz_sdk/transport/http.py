from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Optional, Any, Mapping
from urllib.parse import urlencode

import aiohttp

from oopz_sdk.auth.headers import build_oopz_headers
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig, ProxyConfig
from oopz_sdk.exceptions import OopzConnectionError

from .base import BaseTransport
from .proxy import build_aiohttp_proxy, build_requests_proxies


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

        except aiohttp.ClientError as exc:
            raise OopzConnectionError(f"request failed: {exc}") from exc

    async def get(self, url_path: str, params: Optional[dict] = None) -> HttpResponse:
        return await self.request("GET", url_path, params=params)

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