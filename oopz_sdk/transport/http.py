from __future__ import annotations

import json
import threading
import time
from typing import Optional
from urllib.parse import urlencode

import requests

from oopz_sdk.auth.headers import build_oopz_headers
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig, ProxyConfig

from .base import BaseTransport
from .proxy import build_requests_proxies


class HttpTransport(BaseTransport):
    def __init__(self, config: OopzConfig, signer: Signer):
        self.config = config
        self.signer = signer
        self.session = requests.Session()
        self.session.headers.update(config.get_headers())
        proxies = build_requests_proxies(getattr(config, "proxy", ProxyConfig()))
        if proxies:
            self.session.proxies.update(proxies)
        self._rate_lock = threading.Lock()
        self._last_request_time = 0.0

    def throttle(self) -> None:
        interval = self.config.rate_limit_interval
        with self._rate_lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < interval:
                time.sleep(interval - elapsed)
            self._last_request_time = time.time()

    def request(self, method: str, url_path: str, body: dict | None = None, **kwargs):
        self.throttle()
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
        return self.session.request(
            method,
            url,
            headers=headers,
            params=params,
            data=data if body is not None or method.upper() in ("POST", "PUT", "PATCH") else None,
            timeout=self.config.request_timeout,
        )

    def get(self, url_path: str, params: Optional[dict] = None):
        return self.request("GET", url_path, params=params)

    def post(self, url_path: str, body: dict):
        return self.request("POST", url_path, body=body)

    def put(self, url_path: str, body: dict):
        return self.request("PUT", url_path, body=body)

    def patch(self, url_path: str, body: dict):
        return self.request("PATCH", url_path, body=body)

    def delete(self, url_path: str, body: Optional[dict] = None):
        return self.request("DELETE", url_path, body=body)

    def close(self) -> None:
        self.session.close()
