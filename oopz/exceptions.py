"""Oopz SDK 异常定义。"""


class OopzError(Exception):
    """SDK 基础异常。"""


class OopzApiError(OopzError):
    """平台 API 调用失败（HTTP 非 200 或业务状态异常）。"""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class OopzAuthError(OopzError):
    """认证相关错误（签名失败、JWT 无效等）。"""


class OopzConnectionError(OopzError):
    """WebSocket 连接错误。"""


class OopzRateLimitError(OopzApiError):
    """请求被限流（HTTP 429）。"""

    def __init__(self, message: str = "HTTP 429", retry_after: int = 0, **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after
