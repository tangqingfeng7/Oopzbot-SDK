"""Runtime configuration objects for the Oopz SDK."""

from __future__ import annotations

import asyncio
import logging
import os
import warnings
from dataclasses import dataclass, field
from typing import Any
from .constants import DEFAULT_HEADERS

logger = logging.getLogger(__name__)


@dataclass
class RequestConfig:
    timeout: float | tuple[float, float] = (10, 30)


@dataclass
class RetryConfig:
    max_attempts: int = 3


@dataclass
class RateLimitConfig:
    interval: float = 0.0


@dataclass
class HeartbeatConfig:
    interval: float = 10.0
    reconnect_interval: float = 2.0
    max_reconnect_interval: float = 120.0


@dataclass
class ProxyConfig:
    http: str | None = None
    https: str | None = None
    websocket: str | None = None


@dataclass
class OneBotV12Config:
    """
    OneBot v12 适配配置。

    enabled:
        是否启用 OneBot v12 适配器。

    auto_start_server:
        是否在 OopzBot.start() 时自动启动 OneBot v12 server。
        如果只是想内部调用 adapter，可以设为 False。

    host / port:
        正向 HTTP / WebSocket server 监听地址。

    access_token:
        OneBot 连接层鉴权 token。

    ws_reverse_urls:
        反向 WebSocket 地址。配置后 SDK 会主动连接这些地址。

    webhook_urls:
        HTTP webhook 地址。事件会 POST 到这些 URL。
    """

    enabled: bool = False
    auto_start_server: bool = True

    platform: str = "oopz"
    self_id: str = ""

    db_path: str | None = None

    host: str = "127.0.0.1"
    port: int = 6727

    access_token: str = ""

    enable_http: bool = True
    enable_ws: bool = True

    webhook_urls: list[str] = field(default_factory=list)

    ws_reverse_urls: list[str] = field(default_factory=list)
    ws_reverse_reconnect_interval: float = 3.0

    send_connect_event: bool = True


@dataclass
class OneBotV11Config:
    """
    OneBot v11 适配配置。

    注意：Oopz 是 area/channel 双层结构，而 v11 是 group 单层结构。
    v11 的 group_id 默认映射为 Oopz channel_id；发送群消息时建议额外传
    oopz_area_id/area/guild_id，或在 default_area 中配置默认 area。
    """

    enabled: bool = False
    auto_start_server: bool = True

    platform: str = "oopz"
    self_id: str = ""

    db_path: str | None = None

    host: str = "127.0.0.1"
    port: int = 6700

    access_token: str = ""
    secret: str = ""

    enable_http: bool = True
    enable_ws: bool = True
    enable_http_post: bool = True
    enable_ws_reverse: bool = True

    # OneBot v11 HTTP POST 事件上报地址
    http_post_urls: list[str] = field(default_factory=list)
    http_post_timeout: float = 0.0

    # OneBot v11 反向 WebSocket。
    # ws_reverse_url 表示 Universal 连接
    ws_reverse_url: str = ""
    # ws_reverse_api_url / ws_reverse_event_url 表示 API / Event 分离连接。
    ws_reverse_api_url: str = ""
    ws_reverse_event_url: str = ""
    ws_reverse_reconnect_interval: float = 3.0

    send_connect_event: bool = True

    # 因为目前的实现将area+channel作为group进行处理, 所以有些对群组的危险操作会影响整个域
    # 是否启用群组禁言被当做整个域禁言的action
    enable_area_scoped_group_ban: bool = False
    # 是否启用群组离开被当做整个域离开的action
    enable_set_group_leave_as_area_leave: bool = False
    # 是否启用群组踢人被当做整个域移除的action
    enable_set_group_kick_as_area_kick: bool = False


@dataclass
class OopzConfig:
    device_id: str = ""
    person_uid: str = ""
    jwt_token: str = ""
    private_key: Any = None

    base_url: str = "https://gateway.oopz.cn"
    ws_url: str = "wss://ws.oopz.cn"
    app_version: str = "69514"
    channel: str = "Web"
    platform: str = "windows"
    web: bool = True

    use_announcement_style: bool = False

    agora_app_id: str = "358eebceadb94c2a9fd91ecd7b341602"
    agora_init_timeout: int = 1800

    voice_backend: str = "browser"
    voice_browser_headless: bool = True
    voice_browser_executable_path: str = ""
    voice_agora_sdk_url: str = "https://download.agora.io/sdk/release/AgoraRTC_N.js"

    userinfo_cache_max_entries: int = 5000
    userinfo_cache_ttl: float = 1800.0

    area_channels_cache_max_entries: int = 1000
    area_channels_cache_ttl: float = 1800.0

    person_profiles_cache_max_entries: int = 3000
    person_profile_cache_ttl: float = 1800.0

    area_user_nickname_cache_max_entries: int = 20000
    area_user_nickname_cache_ttl: float = 300.0

    area_members_page_cache_max_entries: int = 200
    area_members_page_cache_ttl: float = 10.0

    headers: dict[str, str] = field(default_factory=dict)
    retry: RetryConfig = field(default_factory=RetryConfig)
    request_config: RequestConfig = field(default_factory=RequestConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)

    ignore_self_messages: bool = True   # 如果设置为False, 会导致bot接收到自己处理的消息, 可能导致死循环

    auto_subscribe_joined_areas: bool = False # 加入后自动请求账号加入的所有域, 然后向websocket注册加入的域, 接受来自域的事件

    onebot_v11: OneBotV11Config = field(default_factory=OneBotV11Config)

    def __post_init__(self) -> None:
        self.device_id = str(self.device_id or "").strip()
        self.person_uid = str(self.person_uid or "").strip()
        self.jwt_token = str(self.jwt_token or "").strip()

        if self.has_credentials() and self._is_missing_private_key(self.private_key):
            self.private_key = self._fallback_private_key()

    @staticmethod
    def _require_non_empty(value: str, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return text

    @staticmethod
    def _is_missing_private_key(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (bytes, bytearray)):
            return not value
        return False

    @staticmethod
    def _require_env(name: str, *, strip: bool = True) -> str:
        raw = os.environ.get(name, "")
        if not raw or not raw.strip():
            raise ValueError(f"{name} environment variable is required")

    @staticmethod
    def _fallback_private_key() -> Any:
        from oopz_sdk.auth._builtin_login_bundle import get_client_signing_key

        logger.warning(
            "OOPZ private_key not provided, falling back to builtin client signing key."
        )
        return get_client_signing_key()

    @staticmethod
    def _has_credentials(
        *,
        device_id: str,
        person_uid: str,
        jwt_token: str,
    ) -> bool:
        return all(
            str(value or "").strip()
            for value in (device_id, person_uid, jwt_token)
        )

    def has_credentials(self) -> bool:
        return self._has_credentials(
            device_id=self.device_id,
            person_uid=self.person_uid,
            jwt_token=self.jwt_token,
        )

    def ensure_credentials(self) -> None:
        if self.has_credentials():
            if self._is_missing_private_key(self.private_key):
                self.private_key = self._fallback_private_key()
            return

        raise ValueError(
            "OopzConfig credentials are incomplete. Fill device_id/person_uid/jwt_token, "
            "or call `config.login(...)` / `await config.login_async(...)` / "
            "`OopzConfig.from_env()` / `await OopzConfig.from_env_async(...)` "
            "before creating clients."
        )

    @staticmethod
    def _normalize_login_method(method: str) -> str:
        normalized = str(method or "auto").strip().lower().replace("-", "_")
        if normalized not in {"auto", "credentials", "password", "password_api", "password_browser"}:
            raise ValueError(
                "login.method must be one of: auto, credentials, password, "
                "password_api, password_browser"
            )
        return normalized

    @staticmethod
    def _build_password_kwargs(
        *,
        headful_env: str,
        headless: bool | None,
        browser_data_dir: str | None,
        chromium_executable_path: str | None,
        timeout: float | None,
        proxy: ProxyConfig | dict[str, Any] | str | None,
    ) -> dict[str, Any]:
        from oopz_sdk.auth.password_login import truthy_env

        kwargs: dict[str, Any] = {
            "headless": headless
            if headless is not None
            else not truthy_env(os.environ.get(headful_env))
        }
        if browser_data_dir:
            kwargs["browser_data_dir"] = browser_data_dir
        if chromium_executable_path:
            kwargs["chromium_executable_path"] = chromium_executable_path
        if timeout is not None:
            kwargs["timeout"] = timeout
        if proxy is not None:
            kwargs["proxy"] = proxy
        return kwargs

    @classmethod
    def _credentials_mapping(
        cls,
        *,
        device_id: str,
        person_uid: str,
        jwt_token: str,
        private_key: Any = None,
        app_version: str = "",
    ) -> dict[str, Any]:
        signing_key = private_key
        if cls._is_missing_private_key(signing_key):
            signing_key = cls._fallback_private_key()

        return {
            "device_id": str(device_id or "").strip(),
            "person_uid": str(person_uid or "").strip(),
            "jwt_token": str(jwt_token or "").strip(),
            "private_key": signing_key,
            "app_version": str(app_version or "").strip(),
        }

    @classmethod
    async def _resolve_login_credentials(
        cls,
        *,
        method: str,
        device_id: str = "",
        person_uid: str = "",
        jwt_token: str = "",
        private_key: Any = None,
        app_version: str = "",
        phone: str = "",
        password: str = "",
        headful_env: str = "OOPZ_LOGIN_HEADFUL",
        headless: bool | None = None,
        browser_data_dir: str | None = None,
        chromium_executable_path: str | None = None,
        timeout: float | None = None,
        proxy: ProxyConfig | dict[str, Any] | str | None = None,
    ) -> Any:
        from oopz_sdk.auth import OopzLoginCredentials
        from oopz_sdk.auth import api_password_login as api_password_login_module
        from oopz_sdk.auth import password_login as password_login_module

        method = cls._normalize_login_method(method)
        password_kwargs = cls._build_password_kwargs(
            headful_env=headful_env,
            headless=headless,
            browser_data_dir=browser_data_dir,
            chromium_executable_path=chromium_executable_path,
            timeout=timeout,
            proxy=proxy,
        )

        if method == "credentials":
            if not cls._has_credentials(
                device_id=device_id,
                person_uid=person_uid,
                jwt_token=jwt_token,
            ):
                raise ValueError(
                    "login.method='credentials' requires device_id/person_uid/jwt_token."
                )

            return OopzLoginCredentials.from_mapping(
                cls._credentials_mapping(
                    device_id=device_id,
                    person_uid=person_uid,
                    jwt_token=jwt_token,
                    private_key=private_key,
                    app_version=app_version,
                )
            )

        if method == "password_api":
            return await asyncio.to_thread(
                api_password_login_module.login_with_api_password,
                cls._require_non_empty(phone, "phone"),
                str(password or ""),
                device_id=str(device_id or "") or None,
                timeout=timeout if timeout is not None else 20,
            )

        if method == "password_browser":
            return await password_login_module.login_with_playwright_password(
                cls._require_non_empty(phone, "phone"),
                str(password or ""),
                **password_kwargs,
            )

        if method == "password":
            return await password_login_module.login_with_password(
                cls._require_non_empty(phone, "phone"),
                str(password or ""),
                **password_kwargs,
            )

        if cls._has_credentials(
            device_id=device_id,
            person_uid=person_uid,
            jwt_token=jwt_token,
        ):
            return OopzLoginCredentials.from_mapping(
                cls._credentials_mapping(
                    device_id=device_id,
                    person_uid=person_uid,
                    jwt_token=jwt_token,
                    private_key=private_key,
                    app_version=app_version,
                )
            )

        if str(phone or "").strip() and str(password or ""):
            return await password_login_module.login_with_password(
                cls._require_non_empty(phone, "phone"),
                str(password or ""),
                **password_kwargs,
            )

        raise ValueError(
            "No valid login configuration found. Provide device_id/person_uid/jwt_token "
            "or phone/password."
        )

    @classmethod
    async def _build_config_from_login(
        cls,
        *,
        overrides: dict[str, Any] | None = None,
        **login_kwargs: Any,
    ) -> "OopzConfig":
        credentials = await cls._resolve_login_credentials(**login_kwargs)

        values: dict[str, Any] = {
            "device_id": credentials.device_id,
            "person_uid": credentials.person_uid,
            "jwt_token": credentials.jwt_token,
            "private_key": credentials.private_key_pem,
        }
        if credentials.app_version:
            values["app_version"] = credentials.app_version

        values.update(overrides or {})
        return cls(**values)

    def _apply_login_credentials(
        self,
        credentials: Any,
    ) -> "OopzConfig":
        self.device_id = str(credentials.device_id or "").strip()
        self.person_uid = str(credentials.person_uid or "").strip()
        self.jwt_token = str(credentials.jwt_token or "").strip()
        self.private_key = credentials.private_key_pem

        if self.has_credentials() and self._is_missing_private_key(self.private_key):
            self.private_key = self._fallback_private_key()

        if credentials.app_version:
            self.app_version = credentials.app_version

        return self

    @staticmethod
    def _run_coroutine_sync(
        coro: Any,
        *,
        sync_api: str,
        async_api: str,
    ) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        coro.close()
        raise RuntimeError(
            f"{sync_api} cannot be used inside a running event loop. "
            f"Use `{async_api}` instead."
        )

    @classmethod
    async def from_env_async(
        cls,
        prefix: str = "OOPZ_",
        **overrides: Any,
    ) -> "OopzConfig":
        method = cls._normalize_login_method(os.environ.get("OOPZ_LOGIN_METHOD", "auto"))

        device_id = os.environ.get(f"{prefix}DEVICE_ID", "")
        person_uid = os.environ.get(f"{prefix}PERSON_UID", "")
        jwt_token = os.environ.get(f"{prefix}JWT_TOKEN", "")
        private_key = os.environ.get(f"{prefix}PRIVATE_KEY", "")
        app_version = os.environ.get(f"{prefix}APP_VERSION", "").strip()

        phone = os.environ.get(f"{prefix}LOGIN_PHONE", "").strip()
        password = os.environ.get(f"{prefix}LOGIN_PASSWORD", "")

        has_any_credential_value = any(
            str(value or "").strip()
            for value in (device_id, person_uid, jwt_token, private_key)
        )

        if method in {"auto", "credentials"} and cls._has_credentials(
            device_id=device_id,
            person_uid=person_uid,
            jwt_token=jwt_token,
        ):
            values: dict[str, Any] = {
                "device_id": cls._require_env(f"{prefix}DEVICE_ID"),
                "person_uid": cls._require_env(f"{prefix}PERSON_UID"),
                "jwt_token": cls._require_env(f"{prefix}JWT_TOKEN"),
            }

            if private_key.strip():
                values["private_key"] = cls._require_env(
                    f"{prefix}PRIVATE_KEY",
                    strip=False,
                )

            if app_version:
                values["app_version"] = app_version

            values.update(overrides)
            return cls(**values)

        if method == "credentials":
            raise ValueError(
                "OOPZ credentials are incomplete. "
                f"Set {prefix}DEVICE_ID, {prefix}PERSON_UID, and {prefix}JWT_TOKEN. "
                f"{prefix}PRIVATE_KEY is optional."
            )

        if method == "auto" and has_any_credential_value and not phone and not password:
            raise ValueError(
                "Partial OOPZ credentials found. "
                f"Set {prefix}DEVICE_ID, {prefix}PERSON_UID, and {prefix}JWT_TOKEN, "
                "or provide OOPZ_LOGIN_PHONE/OOPZ_LOGIN_PASSWORD."
            )

        return await cls._build_config_from_login(
            method=method,
            device_id=device_id,
            person_uid=person_uid,
            jwt_token=jwt_token,
            private_key=private_key,
            app_version=app_version,
            phone=phone,
            password=password,
            headful_env="OOPZ_LOGIN_HEADFUL",
            overrides=overrides,
        )

    @classmethod
    def from_env(
        cls,
        prefix: str = "OOPZ_",
        **overrides: Any,
    ) -> "OopzConfig":
        return cls._run_coroutine_sync(
            cls.from_env_async(prefix=prefix, **overrides),
            sync_api="OopzConfig.from_env()",
            async_api="await OopzConfig.from_env_async(...)",
        )

    async def login_async(
        self,
        *,
        phone: str = "",
        password: str = "",
        device_id: str = "",
        person_uid: str = "",
        jwt_token: str = "",
        private_key: Any = None,
        method: str = "auto",
        app_version: str = "",
        headful_env: str = "OOPZ_LOGIN_HEADFUL",
        headless: bool | None = None,
        browser_data_dir: str | None = None,
        chromium_executable_path: str | None = None,
        timeout: float | None = None,
        proxy: ProxyConfig | dict[str, Any] | str | None = None,
    ) -> "OopzConfig":
        credentials = await type(self)._resolve_login_credentials(
            method=method,
            device_id=device_id or self.device_id,
            person_uid=person_uid or self.person_uid,
            jwt_token=jwt_token or self.jwt_token,
            private_key=private_key if private_key is not None else self.private_key,
            app_version=app_version or self.app_version,
            phone=phone,
            password=password,
            headful_env=headful_env,
            headless=headless,
            browser_data_dir=browser_data_dir,
            chromium_executable_path=chromium_executable_path,
            timeout=timeout,
            proxy=proxy,
        )
        return self._apply_login_credentials(credentials)

    def login(
        self,
        *,
        phone: str = "",
        password: str = "",
        device_id: str = "",
        person_uid: str = "",
        jwt_token: str = "",
        private_key: Any = None,
        method: str = "auto",
        app_version: str = "",
        headful_env: str = "OOPZ_LOGIN_HEADFUL",
        headless: bool | None = None,
        browser_data_dir: str | None = None,
        chromium_executable_path: str | None = None,
        timeout: float | None = None,
        proxy: ProxyConfig | dict[str, Any] | str | None = None,
    ) -> "OopzConfig":
        return type(self)._run_coroutine_sync(
            self.login_async(
                phone=phone,
                password=password,
                device_id=device_id,
                person_uid=person_uid,
                jwt_token=jwt_token,
                private_key=private_key,
                method=method,
                app_version=app_version,
                headful_env=headful_env,
                headless=headless,
                browser_data_dir=browser_data_dir,
                chromium_executable_path=chromium_executable_path,
                timeout=timeout,
                proxy=proxy,
            ),
            sync_api="OopzConfig.login()",
            async_api="await config.login_async(...)",
        )

    @classmethod
    async def _from_password_impl(
        cls,
        phone: str,
        password: str,
        *,
        headful_env: str = "OOPZ_LOGIN_HEADFUL",
        headless: bool | None = None,
        **kwargs: Any,
    ) -> "OopzConfig":
        config_overrides = dict(kwargs.pop("config_overrides", {}) or {})
        config = cls(**config_overrides)

        return await config.login_async(
            method="password",
            phone=cls._require_non_empty(phone, "phone"),
            password=str(password or ""),
            headful_env=headful_env,
            headless=headless,
            browser_data_dir=kwargs.pop("browser_data_dir", None),
            chromium_executable_path=kwargs.pop("chromium_executable_path", None),
            timeout=kwargs.pop("timeout", None),
            proxy=kwargs.pop("proxy", None),
            **kwargs,
        )

    @classmethod
    async def from_password(
        cls,
        phone: str,
        password: str,
        *,
        headful_env: str = "OOPZ_LOGIN_HEADFUL",
        headless: bool | None = None,
        **kwargs: Any,
    ) -> "OopzConfig":
        warnings.warn(
            "OopzConfig.from_password() is deprecated; create OopzConfig(...) first "
            "and then call `await config.login_async(...)`.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await cls._from_password_impl(
            phone,
            password,
            headful_env=headful_env,
            headless=headless,
            **kwargs,
        )

    @classmethod
    async def from_password_env(
        cls,
        *,
        phone_env: str = "OOPZ_LOGIN_PHONE",
        password_env: str = "OOPZ_LOGIN_PASSWORD",
        headful_env: str = "OOPZ_LOGIN_HEADFUL",
        headless: bool | None = None,
        **kwargs: Any,
    ) -> "OopzConfig":
        warnings.warn(
            "OopzConfig.from_password_env() is deprecated; use `from_env_async` instead, "
            "or create `OopzConfig(...)` and then call `await config.login_async(...)`.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await cls._from_password_impl(
            cls._require_env(phone_env),
            cls._require_env(password_env, strip=False),
            headful_env=headful_env,
            headless=headless,
            **kwargs,
        )

    @classmethod
    def from_password_env_sync(cls, **kwargs: Any) -> "OopzConfig":
        warnings.warn(
            "OopzConfig.from_password_env_sync() is deprecated; use "
            "`OopzConfig.from_env()` or `config = OopzConfig(); config.login(...)`.",
            DeprecationWarning,
            stacklevel=2,
        )

        return cls._run_coroutine_sync(
            cls._from_password_impl(
                cls._require_env(kwargs.pop("phone_env", "OOPZ_LOGIN_PHONE")),
                cls._require_env(kwargs.pop("password_env", "OOPZ_LOGIN_PASSWORD"), strip=False),
                headful_env=kwargs.pop("headful_env", "OOPZ_LOGIN_HEADFUL"),
                headless=kwargs.pop("headless", None),
                **kwargs,
            ),
            sync_api="OopzConfig.from_password_env_sync()",
            async_api="await OopzConfig.from_password_env(...)",
        )

    @property
    def rate_limit_interval(self) -> float:
        return self.rate_limit.interval

    @rate_limit_interval.setter
    def rate_limit_interval(self, value: float) -> None:
        self.rate_limit.interval = value

    @property
    def request_timeout(self) -> float | tuple[float, float]:
        return self.request_config.timeout

    @request_timeout.setter
    def request_timeout(self, value: float | tuple[float, float]) -> None:
        self.request_config.timeout = value

    def get_headers(self) -> dict[str, str]:
        return {**DEFAULT_HEADERS, **self.headers}