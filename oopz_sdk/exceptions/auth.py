from .base import OopzError


class OopzAuthError(OopzError):
    """Authentication or signing failure.

    Carries optional ``status_code``/``payload``/``response`` so that error
    handlers (e.g. ``on_error``) can react programmatically instead of having
    to parse the message string.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: object | None = None,
        response: object | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload
        self.response = response


class OopzPasswordLoginError(OopzAuthError):
    """OOPZ 账号密码登录或凭据提取失败。"""

    def __init__(
        self,
        message: str,
        *,
        code: int | str | None = None,
        payload: object | None = None,
        response: object | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=code if isinstance(code, int) else None,
            payload=payload,
            response=response,
        )
        self.code = code
