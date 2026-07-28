from .base import OopzError

# 表示「凭据本身已失效」的状态码：命中后应触发续期/停机决策，而不是当成普通
# 业务错误重试或忽略。REST（HTTP 状态码）与 WS 握手（HTTP 升级响应状态码）共用
# 这一份定义，新增需要按此语义对待的状态码时只改这里。
#
# 刻意排除 403：Oopz 用 403 表示对具体资源无权限（如向无权限频道发消息），属正常
# 业务返回，若当作凭据失效会误把整个客户端停机。428 表示已签名凭据的前置条件失效。
AUTH_FAILURE_STATUS_CODES = frozenset({401, 428})


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
