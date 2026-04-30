from .base import OopzError


class OopzAuthError(OopzError):
    """Authentication or signing failure."""


class OopzPasswordLoginError(OopzAuthError):
    """OOPZ 账号密码登录或凭据提取失败。"""

    def __init__(
        self,
        message: str,
        *,
        code: int | str | None = None,
        payload: object | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload
