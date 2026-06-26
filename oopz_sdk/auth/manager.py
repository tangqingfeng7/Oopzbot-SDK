"""
由 Bot 生命周期托管的统一认证管理组件
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzAuthError, OopzConnectionError
from oopz_sdk.utils.jwt import decode_jwt_payload

if TYPE_CHECKING:
    from oopz_sdk.auth.password_login import OopzLoginCredentials

logger = logging.getLogger(__name__)

ReloginCallback = Callable[[], Awaitable["OopzLoginCredentials"]]
TokenListener = Callable[[OopzConfig], None]

DEFAULT_REFRESH_THRESHOLD_SECONDS = 300.0
# 重登遇瞬时错误(OopzConnectionError)时的有限次退避重试，避免一次网络抖动/5xx
# 就被反应式路径误判为不可恢复而停机；耗尽后才返回失败交由调用方决策。
DEFAULT_RELOGIN_MAX_ATTEMPTS = 3
DEFAULT_RELOGIN_BACKOFF_SECONDS = 1.0


class AuthManager:
    """统一管理 JWT 续期、鉴权失效重试与不可恢复上报。"""

    def __init__(
        self,
        config: OopzConfig,
        *,
        relogin: Optional[ReloginCallback] = None,
        refresh_threshold_seconds: float = DEFAULT_REFRESH_THRESHOLD_SECONDS,
        relogin_max_attempts: int = DEFAULT_RELOGIN_MAX_ATTEMPTS,
        relogin_backoff_seconds: float = DEFAULT_RELOGIN_BACKOFF_SECONDS,
    ) -> None:
        self._config = config
        self._relogin = relogin
        self._refresh_threshold = max(0.0, float(refresh_threshold_seconds))
        self._relogin_max_attempts = max(1, int(relogin_max_attempts))
        self._relogin_backoff_seconds = max(0.0, float(relogin_backoff_seconds))
        self._lock = asyncio.Lock()
        self._token_version = 0
        self._listeners: list[TokenListener] = []

    @property
    def config(self) -> OopzConfig:
        return self._config

    @property
    def can_refresh(self) -> bool:
        """是否持有重登能力（有 relogin 回调）。"""
        return self._relogin is not None

    @property
    def token_version(self) -> int:
        """每次成功续期自增，用于 single-flight 去重与触发副作用。"""
        return self._token_version

    @property
    def refresh_threshold_seconds(self) -> float:
        return self._refresh_threshold

    def add_token_listener(self, listener: TokenListener) -> None:
        """注册 token 变更监听者（续期成功后同步调用）。"""
        self._listeners.append(listener)

    def seconds_until_expiry(self, *, now: float | None = None) -> float | None:
        """返回当前 token 距离 ``exp`` 的剩余秒数；无 exp 时返回 None。"""
        exp = decode_jwt_payload(self._config.jwt_token).get("exp")
        if not isinstance(exp, (int, float)):
            return None
        return exp - (time.time() if now is None else now)

    def needs_refresh(self, *, now: float | None = None) -> bool:
        """token 是否已进入临期窗口（含已过期）。无 exp 时返回 False。

        这里刻意不像 ``jwt_expired`` 那样再叠加时钟容差(leeway)，续期阈值
        (``refresh_threshold``，默认 300s) 本身就是一段提前量，已经覆盖了本地时钟偏差，
        时钟偏快只会让续期“提前”发生（安全方向），不会像启动期硬校验那样误拒有效 token，
        故无需额外 leeway。
        """
        remaining = self.seconds_until_expiry(now=now)
        if remaining is None:
            return False
        return remaining <= self._refresh_threshold

    async def ensure_fresh(self) -> bool:
        """临期且可续期则续期；返回当前 token 是否可用。"""
        if not self.needs_refresh():
            return True
        if not self.can_refresh:
            return False
        return await self.refresh()

    async def handle_auth_error(
        self,
        error: OopzAuthError | None = None,
        *,
        observed_token_version: int | None = None,
    ) -> bool:
        """鉴权失效后的单次重登尝试。

        返回 True 表示已有可用的新 token（调用方可重试一次）；返回 False 表示不可
        恢复（无重登能力或重登失败），调用方应升级为致命错误并停机。

        ``observed_token_version`` 是失败请求所用的 token 版本快照。若当前版本已领先于
        该快照，说明在请求在途期间凭据已被其它路径（如后台续期）轮换，手中已有更新的
        token，调用方直接重试即可，无需再次重登——避免一次网络在途请求的过期 401 触发
        多余的登录调用。
        """
        if not self.can_refresh:
            return False
        if (
            observed_token_version is not None
            and observed_token_version != self._token_version
        ):
            return True
        logger.debug(
            "AuthManager 处理鉴权失效，尝试强制续期 (status_code=%s)",
            getattr(error, "status_code", None),
        )
        return await self.refresh(force=True)

    async def refresh(self, *, force: bool = False) -> bool:
        """执行一次续期（single-flight）。

        - ``force=False``：仅在临期时续期，否则视为已新鲜直接返回 True。
        - ``force=True``：失效场景强制重登。
        若在等待锁期间已有其他协程完成续期，则直接复用其结果。
        """
        if not self.can_refresh:
            return False

        version_before = self._token_version
        async with self._lock:
            # 等待锁期间若已有其他协程续期成功，则无需重复重登。
            if self._token_version != version_before:
                return True
            if not force and not self.needs_refresh():
                return True

            credentials = await self._relogin_with_transient_retry()
            if credentials is None:
                return False

            self._apply(credentials)
            logger.info(
                "AuthManager 已刷新凭据 (token_version=%d)", self._token_version
            )
            return True

    async def _relogin_with_transient_retry(
        self,
    ) -> Optional["OopzLoginCredentials"]:
        """执行一次重登，并对瞬时错误做有限次退避重试。

        - 凭据被服务端拒绝(``OopzAuthError``)：账号/密码失效等，属不可恢复，直接
          上抛，由调用方上报停机。
        - 瞬时连接错误(``OopzConnectionError``，网络/超时/5xx)：退避重试，耗尽后
          返回 ``None``（可恢复失败，调用方可稍后再试），不升级为永久停机。
        - 其它异常：记录并返回 ``None``。
        """
        assert self._relogin is not None
        last_error: OopzConnectionError | None = None
        for attempt in range(1, self._relogin_max_attempts + 1):
            try:
                return await self._relogin()
            except OopzAuthError:
                raise
            except OopzConnectionError as exc:
                last_error = exc
                if attempt >= self._relogin_max_attempts:
                    break
                backoff = self._relogin_backoff_seconds * attempt
                logger.warning(
                    "AuthManager 重登遇瞬时错误，%.1fs 后第 %d 次重试: %s",
                    backoff,
                    attempt + 1,
                    exc,
                )
                if backoff > 0:
                    await asyncio.sleep(backoff)
            except Exception as exc:
                logger.warning("AuthManager 重新登录失败: %s", exc)
                return None

        logger.warning(
            "AuthManager 重登瞬时错误重试 %d 次仍失败: %s",
            self._relogin_max_attempts,
            last_error,
        )
        return None

    def _apply(self, credentials: "OopzLoginCredentials") -> None:
        self._config._apply_login_credentials(credentials)
        self._token_version += 1
        for listener in list(self._listeners):
            try:
                listener(self._config)
            except Exception:
                logger.exception("AuthManager token 监听者执行失败")
