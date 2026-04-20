from .base import OopzError
from typing import Any


class OopzApiError(OopzError):
    def __init__(self, message: str, status_code: int | None = None, response = None, payload: Any = None,):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.payload = payload
        self.message = message


class OopzRateLimitError(OopzApiError):
    def __init__(self, message: str = "HTTP 429", retry_after: int = 0, **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after
