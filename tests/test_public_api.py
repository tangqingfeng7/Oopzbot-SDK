from oopz import (
    OopzApiError,
    OopzAuthError,
    OopzConfig,
    OopzRateLimitError,
    OopzSender,
    Signer,
    __version__,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _make_config() -> OopzConfig:
    return OopzConfig(
        device_id="device",
        person_uid="person",
        jwt_token="jwt",
        private_key=None,
        default_area="area",
        default_channel="channel",
    )


def test_version_is_exposed() -> None:
    assert __version__ == "0.2.0"


def test_signer_invalid_private_key_raises_auth_error() -> None:
    config = _make_config()
    config.private_key = object()

    try:
        Signer(config)
    except OopzAuthError:
        return

    raise AssertionError("Signer 应在无效私钥类型时抛出 OopzAuthError")


def test_sender_context_manager_closes_session(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    state = {"closed": False}

    def _close() -> None:
        state["closed"] = True

    monkeypatch.setattr(sender.session, "close", _close)

    with sender as managed_sender:
        assert managed_sender is sender

    assert state["closed"] is True


def test_send_message_raises_rate_limit_error(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    def _fake_post(url_path: str, body: dict):
        return _FakeResponse(
            429,
            payload={"message": "请求过快"},
            headers={"Retry-After": "3"},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)

    try:
        sender.send_message("hello", auto_recall=False)
    except OopzRateLimitError as exc:
        assert exc.retry_after == 3
        assert exc.status_code == 429
        return

    raise AssertionError("send_message 应在 429 时抛出 OopzRateLimitError")


def test_send_message_raises_api_error_on_business_failure(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    def _fake_post(url_path: str, body: dict):
        return _FakeResponse(
            200,
            payload={"status": False, "message": "业务失败"},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)

    try:
        sender.send_message("hello", auto_recall=False)
    except OopzApiError as exc:
        assert "业务失败" in str(exc)
        assert exc.status_code == 200
        return

    raise AssertionError("send_message 应在业务失败时抛出 OopzApiError")
