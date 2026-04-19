import asyncio
import io
import oopz_sdk
import oopz_sdk.client as oopz_client
import oopz_sdk.services.media as oopz_media_service
import oopz_sdk.transport.http as oopz_http_transport
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from PIL import Image

from oopz_sdk import OopzRESTClient, models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.client.bot import OopzBot
from oopz_sdk.client.ws import OopzWSClient
from oopz_sdk.config import OopzConfig
from oopz_sdk.config.constants import EVENT_PRIVATE_MESSAGE
from oopz_sdk.exceptions import OopzApiError, OopzConnectionError, OopzParseError, OopzRateLimitError
from oopz_sdk.events.context import EventContext
from oopz_sdk.events.dispatcher import EventDispatcher
from oopz_sdk.events.parser import EventParser
from oopz_sdk.events.registry import EventRegistry
from oopz_sdk.models.event import MessageEvent
from oopz_sdk.models.segment import Image as ImageSegment
from oopz_sdk.services import BaseService
from oopz_sdk.services.area import AreaService
from oopz_sdk.services.channel import Channel
from oopz_sdk.services.media import Media
from oopz_sdk.services.member import Member
from oopz_sdk.services.message import Message
from oopz_sdk.services.moderation import Moderation
from oopz_sdk.transport.http import HttpTransport


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8") if text else b"{}"

    def __await__(self):
        async def _wrapped():
            return self

        return _wrapped().__await__()

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def _make_private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _make_config(**overrides) -> OopzConfig:
    config = OopzConfig(
        device_id="device",
        person_uid="person",
        jwt_token="jwt",
        private_key=_make_private_key(),
        default_area="area",
        default_channel="channel",
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def _run(awaitable):
    return asyncio.run(awaitable)


def test_oopz_sdk_config_requires_private_key():
    with pytest.raises(ValueError):
        OopzConfig(
            device_id="device",
            person_uid="person",
            jwt_token="jwt",
            private_key=None,
        )


def test_oopz_sdk_signer_from_pem_does_not_mutate_original_config():
    original_key = _make_private_key()
    replacement_key = _make_private_key()
    pem = replacement_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    config = _make_config(private_key=original_key)

    signer = Signer.from_pem(pem, config)

    assert config.private_key is original_key
    assert signer.private_key is not original_key


def test_oopz_sdk_response_helper_treats_explicit_failure_as_failure():
    assert oopz_sdk.is_success_payload({"status": False, "code": 0}) is False

    with pytest.raises(OopzApiError, match="helper rejected"):
        oopz_sdk.ensure_success_payload(
            _FakeResponse(200, payload={"status": False, "code": 0, "message": "helper rejected"}),
            "fallback message",
        )


def test_oopz_sdk_send_message_returns_result_model(monkeypatch):
    service = Message(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "msg-1"}},
        ),
    )

    result = _run(service.send_message("hello", auto_recall=False))

    assert isinstance(result, models.MessageSendResult)
    assert result.message_id == "msg-1"
    assert result.area == "area"
    assert result.channel == "channel"


def test_oopz_sdk_send_message_rejects_explicit_failure_payload(monkeypatch):
    service = Message(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": False, "code": 0, "message": "denied"},
        ),
    )

    with pytest.raises(OopzApiError, match="denied"):
        _run(service.send_message("hello", auto_recall=False))


def test_oopz_sdk_recall_message_returns_operation_result(monkeypatch):
    service = Message(None, _make_config())
    captured = {}
    monkeypatch.setattr(
        service.transport,
        "request",
        lambda method, url_path, body=None, params=None: captured.update(
            {"method": method, "url_path": url_path, "body": body, "params": params}
        ) or _FakeResponse(200, payload={"status": True, "message": "ok"}),
    )

    result = _run(service.recall_message("msg-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is True
    assert result.message == "ok"
    assert captured["method"] == "POST"
    assert captured["url_path"] == "/im/session/v1/recallGim"
    assert captured["params"]["messageId"] == "msg-1"
    assert captured["params"]["channel"] == "channel"


def test_oopz_sdk_recall_message_rejects_explicit_failure_payload(monkeypatch):
    service = Message(None, _make_config())
    monkeypatch.setattr(
        service.transport,
        "request",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "code": 0, "message": "denied"},
        ),
    )

    result = _run(service.recall_message("msg-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "denied"


def test_oopz_sdk_open_private_session_rejects_explicit_failure_payload(monkeypatch):
    service = Message(None, _make_config())
    monkeypatch.setattr(
        service,
        "_request",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "denied", "data": {"channel": "dm-1"}},
        ),
    )

    result = _run(service.open_private_session("target-1"))

    assert result.channel == ""
    assert result.target == "target-1"
    assert result.payload["error"] == "denied"


def test_oopz_sdk_get_channel_messages_returns_error_dict_on_http_failure(monkeypatch):
    service = Message(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="upstream timeout"),
    )

    result = _run(service.get_channel_messages())

    assert result["error"] == "HTTP 503"
    assert result["debug_reason"] == "get_channel_messages_http_error"
    assert result["channel"] == "channel"


def test_oopz_sdk_recall_private_message_raises_not_implemented_error():
    service = Message(None, _make_config())

    with pytest.raises(NotImplementedError, match="暂不支持撤回私信消息"):
        _run(service.recall_private_message("msg-1", channel="dm-1", target="user-1"))


def test_oopz_sdk_find_message_timestamp_raises_when_channel_messages_fail(monkeypatch):
    service = Message(None, _make_config())

    async def _fake_get_channel_messages(*args, **kwargs):
        return {"error": "HTTP 503"}

    monkeypatch.setattr(service, "get_channel_messages", _fake_get_channel_messages)

    with pytest.raises(OopzApiError, match="HTTP 503") as exc_info:
        _run(service.find_message_timestamp("msg-1"))

    assert exc_info.value.response == {"error": "HTTP 503"}


def test_oopz_sdk_get_channel_messages_returns_error_dict_when_message_item_is_invalid(
    monkeypatch,
):
    service = Message(None, _make_config())
    payload = {
        "status": True,
        "data": {
            "messages": [
                {"messageId": "msg-1", "content": "hello"},
                "broken-message-item",
            ]
        },
    }
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(200, payload=payload),
    )

    result = _run(service.get_channel_messages())

    assert result["error"] == "channel messages响应格式异常"
    assert result["debug_reason"] == "get_channel_messages_invalid_item"
    assert result["invalid_index"] == 1


def test_oopz_sdk_get_channel_messages_returns_error_dict_on_failed_status(monkeypatch):
    service = Message(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "message list rejected", "data": {"messages": []}},
        ),
    )

    result = _run(service.get_channel_messages())

    assert result["error"] == "message list rejected"
    assert result["debug_reason"] == "get_channel_messages_failed_status"


def test_oopz_sdk_get_channel_messages_returns_error_dict_when_root_payload_is_invalid(
    monkeypatch,
):
    service = Message(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(200, payload=["bad-root"]),
    )

    result = _run(service.get_channel_messages())

    assert result == {
        "error": "channel messages响应格式异常",
        "debug_reason": "get_channel_messages_malformed_root",
        "area": "area",
        "channel": "channel",
        "size": 50,
        "payload": ["bad-root"],
    }


def test_oopz_sdk_model_error_supports_models_without_response_field():
    service = BaseService(
        _make_config(),
        SimpleNamespace(session=None),
        signer=None,
    )

    class _ModelWithoutResponse:
        def __init__(self, *, payload):
            self.payload = payload

    result = service._model_error(_ModelWithoutResponse, "boom", response=_FakeResponse(500))

    assert result.payload == {"error": "boom"}


def test_oopz_sdk_model_error_does_not_swallow_other_type_errors():
    service = BaseService(
        _make_config(),
        SimpleNamespace(session=None),
        signer=None,
    )

    class _ModelRaisesTypeError:
        def __init__(self, *, payload, response=None):
            if response is not None:
                raise TypeError("bad constructor")
            self.payload = payload

    with pytest.raises(TypeError, match="bad constructor"):
        service._model_error(_ModelRaisesTypeError, "boom", response=_FakeResponse(500))


def test_oopz_sdk_private_message_returns_result_model(monkeypatch):
    service = Message(None, _make_config())
    dm_channel = "DM12345678901234567890"
    calls = []
    monkeypatch.setattr(
        service.transport,
        "request",
        lambda method, url_path, body=None, params=None: calls.append(
            {"method": method, "url_path": url_path, "body": body, "params": params}
        ) or _FakeResponse(200, payload={"status": True, "data": {"channel": dm_channel}}),
    )
    monkeypatch.setattr(
        service,
        "_post",
        lambda url_path, body: calls.append(
            {"method": "POST", "url_path": url_path, "body": body, "params": None}
        ) or _FakeResponse(200, payload={"status": True, "data": {"messageId": "dm-1"}}),
    )

    result = _run(service.send_private_message("hello", target="target-1"))

    assert isinstance(result, models.MessageSendResult)
    assert result.channel == dm_channel
    assert result.message_id == "dm-1"
    assert result.target == "target-1"
    assert [call["method"] for call in calls] == ["PATCH", "POST"]
    assert calls[0]["params"] == {"target": "target-1"}
    assert calls[1]["url_path"] == "/im/session/v2/sendImMessage"


def test_oopz_sdk_upload_file_returns_upload_result(monkeypatch, tmp_path):
    service = Media(None, _make_config())
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"hello")

    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={
                "data": {
                    "signedUrl": "https://upload.example.com",
                    "file": "file-key",
                    "url": "https://cdn.example.com/file-key",
                }
            },
        ),
    )

    class _UploadResp:
        status_code = 200
        text = ""

    async def _upload_to_signed_url(*args, **kwargs):
        return _UploadResp()

    monkeypatch.setattr(service, "_upload_to_signed_url", _upload_to_signed_url)

    result = _run(service.upload_file(str(sample), file_type="IMAGE", ext=".bin"))

    assert isinstance(result, models.UploadResult)
    assert result.attachment.file_key == "file-key"
    assert result.attachment.url == "https://cdn.example.com/file-key"


def test_oopz_sdk_upload_file_raises_api_error_for_200_failure_payload(monkeypatch, tmp_path):
    service = Media(None, _make_config())
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"hello")

    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": False, "message": "signed url failed"},
        ),
    )

    with pytest.raises(OopzApiError, match="signed url failed"):
        _run(service.upload_file(str(sample), file_type="IMAGE", ext=".bin"))


def test_oopz_sdk_upload_file_wraps_put_request_exception(monkeypatch, tmp_path):
    service = Media(None, _make_config())
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"hello")

    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={
                "data": {
                    "signedUrl": "https://upload.example.com",
                    "file": "file-key",
                    "url": "https://cdn.example.com/file-key",
                }
            },
        ),
    )
    async def _upload_to_signed_url(*args, **kwargs):
        raise OopzConnectionError("文件上传失败: upload timeout")

    monkeypatch.setattr(service, "_upload_to_signed_url", _upload_to_signed_url)

    with pytest.raises(OopzConnectionError, match="upload timeout"):
        _run(service.upload_file(str(sample), file_type="IMAGE", ext=".bin"))


def test_oopz_sdk_download_external_wraps_timeout_as_connection_error(monkeypatch):
    service = Media(None, _make_config())

    class _TimeoutContext:
        async def __aenter__(self):
            raise asyncio.TimeoutError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _TimeoutSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return _TimeoutContext()

    monkeypatch.setattr(oopz_media_service.aiohttp, "ClientSession", _TimeoutSession)

    with pytest.raises(OopzConnectionError, match="下载外部文件失败: boom"):
        _run(service._download_external("https://example.com/file.bin", timeout=1))


def test_oopz_sdk_upload_to_signed_url_wraps_timeout_as_connection_error(monkeypatch):
    service = Media(None, _make_config())

    class _TimeoutContext:
        async def __aenter__(self):
            raise asyncio.TimeoutError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _TimeoutSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def put(self, *args, **kwargs):
            return _TimeoutContext()

    monkeypatch.setattr(oopz_media_service.aiohttp, "ClientSession", _TimeoutSession)

    with pytest.raises(OopzConnectionError, match="上传失败: boom"):
        _run(service._upload_to_signed_url("https://upload.example.com", b"data", default_message="上传失败"))


def test_oopz_sdk_upload_file_from_url_does_not_reuse_authenticated_session(monkeypatch):
    service = Media(None, _make_config())
    service.transport.headers["X-Test-Auth"] = "secret"

    image_buffer = io.BytesIO()
    Image.new("RGB", (8, 6), color="white").save(image_buffer, format="PNG")

    captured = {}

    class _ExternalResp:
        status_code = 200
        headers = {}
        content = image_buffer.getvalue()

        def raise_for_status(self):
            return None

    async def _download_external(url, **kwargs):
        captured.update({"url": url, "headers": kwargs.get("headers", {}), **kwargs})
        return _ExternalResp()

    monkeypatch.setattr(service, "_download_external", _download_external)
    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={
                "data": {
                    "signedUrl": "https://upload.example.com",
                    "file": "file-key",
                    "url": "https://cdn.example.com/file-key",
                }
            },
        ),
    )

    class _UploadResp:
        status_code = 200
        text = ""

    async def _upload_to_signed_url(*args, **kwargs):
        return _UploadResp()

    monkeypatch.setattr(service, "_upload_to_signed_url", _upload_to_signed_url)

    result = _run(service.upload_file_from_url("https://example.com/image.png"))

    assert result.attachment.file_key == "file-key"
    assert captured["url"] == "https://example.com/image.png"
    assert captured["headers"] == {}
    assert "X-Test-Auth" not in captured["headers"]


def test_oopz_sdk_upload_file_from_url_preserves_rate_limit_error(monkeypatch):
    service = Media(None, _make_config())

    image_buffer = io.BytesIO()
    Image.new("RGB", (8, 6), color="white").save(image_buffer, format="PNG")

    class _ExternalResp:
        status_code = 200
        headers = {}
        content = image_buffer.getvalue()

        def raise_for_status(self):
            return None

    async def _download_external(*args, **kwargs):
        return _ExternalResp()

    monkeypatch.setattr(service, "_download_external", _download_external)
    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            429,
            payload={"message": "too fast"},
            headers={"Retry-After": "7"},
        ),
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(service.upload_file_from_url("https://example.com/image.png"))

    assert exc_info.value.retry_after == 7


def test_oopz_sdk_upload_audio_from_url_preserves_rate_limit_error(monkeypatch):
    service = Media(None, _make_config())

    class _ExternalResp:
        status_code = 200
        headers = {"Content-Type": "audio/mpeg"}
        content = b"audio-bytes"

        def raise_for_status(self):
            return None

    async def _download_external(*args, **kwargs):
        return _ExternalResp()

    monkeypatch.setattr(service, "_download_external", _download_external)
    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            429,
            payload={"message": "too fast"},
            headers={"Retry-After": "11"},
        ),
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(service.upload_audio_from_url("https://example.com/audio.mp3"))

    assert exc_info.value.retry_after == 11


def test_oopz_sdk_send_image_delegates_to_message_service(monkeypatch, tmp_path):
    service = Media(None, _make_config())
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"fake-image")

    monkeypatch.setattr(
        "oopz_sdk.services.media.get_image_info",
        lambda path: (16, 16, 10),
    )
    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
                200,
                payload={
                    "data": {
                        "signedUrl": "https://upload.example.com",
                        "file": "file-key",
                        "url": "https://cdn.example.com/file-key",
                    }
                },
            ),
    )

    class _UploadResp:
        status_code = 200
        text = ""

    async def _upload_to_signed_url(*args, **kwargs):
        return _UploadResp()

    monkeypatch.setattr(service, "_upload_to_signed_url", _upload_to_signed_url)

    captured = {}

    class _Messages:
        async def send_message(self, *texts, **kwargs):
            captured["texts"] = list(texts)
            captured.update(kwargs)
            return "ok"

    monkeypatch.setattr(service, "_message_service", lambda: _Messages())

    result = _run(service.send_image(str(sample), text="hello"))

    assert result == "ok"
    assert captured["texts"] == ["![IMAGEw16h16](file-key)\nhello"]
    assert captured["attachments"][0]["fileKey"] == "file-key"


def test_oopz_sdk_send_image_raises_api_error_for_incomplete_upload_data(monkeypatch, tmp_path):
    service = Media(None, _make_config())
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"fake-image")

    monkeypatch.setattr(
        "oopz_sdk.services.media.get_image_info",
        lambda path: (16, 16, 10),
    )
    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"signedUrl": "https://upload.example.com"}},
        ),
    )

    with pytest.raises(OopzApiError, match="incomplete upload data"):
        _run(service.send_image(str(sample), text="hello"))


def test_oopz_sdk_send_image_wraps_put_request_exception(monkeypatch, tmp_path):
    service = Media(None, _make_config())
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"fake-image")

    monkeypatch.setattr(
        "oopz_sdk.services.media.get_image_info",
        lambda path: (16, 16, 10),
    )
    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={
                "data": {
                    "signedUrl": "https://upload.example.com",
                    "file": "file-key",
                    "url": "https://cdn.example.com/file-key",
                }
            },
        ),
    )
    async def _upload_to_signed_url(*args, **kwargs):
        raise OopzConnectionError("图片上传失败: upload disconnected")

    monkeypatch.setattr(service, "_upload_to_signed_url", _upload_to_signed_url)

    with pytest.raises(OopzConnectionError, match="upload disconnected"):
        _run(service.send_image(str(sample), text="hello"))


def test_oopz_sdk_send_private_image_preserves_rate_limit_error(monkeypatch, tmp_path):
    service = Media(None, _make_config())
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"fake-image")

    monkeypatch.setattr(
        "oopz_sdk.services.media.get_image_info",
        lambda path: (16, 16, 10),
    )
    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            429,
            payload={"message": "too fast"},
            headers={"Retry-After": "5"},
        ),
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(service.send_private_image("target-1", str(sample), text="hello"))

    assert exc_info.value.retry_after == 5


def test_oopz_sdk_send_image_requires_injected_message_service(monkeypatch, tmp_path):
    service = Media(_make_config())
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"fake-image")

    monkeypatch.setattr(
        "oopz_sdk.services.media.get_image_info",
        lambda path: (16, 16, 10),
    )
    monkeypatch.setattr(
        service,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={
                "data": {
                    "signedUrl": "https://upload.example.com",
                    "file": "file-key",
                    "url": "https://cdn.example.com/file-key",
                }
            },
        ),
    )

    class _UploadResp:
        status_code = 200
        text = ""

    async def _upload_to_signed_url(*args, **kwargs):
        return _UploadResp()

    monkeypatch.setattr(service, "_upload_to_signed_url", _upload_to_signed_url)

    with pytest.raises(RuntimeError, match="messages"):
        _run(service.send_image(str(sample), text="hello"))


def test_oopz_sdk_media_service_reuses_sender_message_service():
    sender = OopzRESTClient(_make_config())

    assert sender.media._message_service() is sender.messages


def test_oopz_sdk_area_members_retries_after_429(monkeypatch):
    service = AreaService(_make_config())
    calls = {"count": 0}

    def _fake_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return _FakeResponse(429, payload={"message": "too fast"})
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"members": [{"uid": "u1", "online": 1}]}},
        )

    monkeypatch.setattr(service, "_get", _fake_get)
    async def _sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr("oopz_sdk.services.area.asyncio.sleep", _sleep)

    result = _run(service.get_area_members())

    assert calls["count"] == 3
    assert result["members"][0]["uid"] == "u1"


def test_oopz_sdk_area_members_does_not_fallback_to_stale_cache_on_http_failure(monkeypatch):
    service = AreaService(_make_config())
    cache_key = ("area", 0, 49)
    service._set_cached_area_members(
        cache_key,
        {
            "members": [{"uid": "stale-user", "name": "Stale", "online": 1}],
            "onlineCount": 1,
            "totalCount": 1,
            "userCount": 1,
            "fetchedCount": 1,
        },
    )
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_area_members())

    assert result["error"] == "HTTP 503"
    assert result["debug_reason"] == "get_area_members_http_error"
    assert "members" not in result


def test_oopz_sdk_area_members_quiet_cache_hit_preserves_model_shape():
    service = AreaService(_make_config())
    cache_key = ("area", 0, 49)
    service._set_cached_area_members(
        cache_key,
        {
            "members": [{"uid": "u1", "name": "Alice", "online": 1}],
            "onlineCount": 1,
            "totalCount": 1,
            "userCount": 1,
            "fetchedCount": 1,
        },
    )

    result = _run(service.get_area_members(quiet=True, as_model=True))

    assert isinstance(result, models.AreaMembersPage)
    assert result.members[0].uid == "u1"
    assert result.total_count == 1


def test_oopz_sdk_area_members_as_model_returns_result_object_when_response_missing(monkeypatch):
    service = AreaService(_make_config())

    async def _fake_get(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_get", _fake_get)

    result = _run(service.get_area_members(as_model=True))

    assert isinstance(result, models.AreaMembersPage)
    assert result.payload["error"] == "未获得响应"
    assert result.payload["debug_reason"] == "get_area_members_missing_response"


def test_oopz_sdk_area_members_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = AreaService(_make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ["bad"]},
        ),
    )

    result = _run(service.get_area_members(as_model=True))

    assert isinstance(result, models.AreaMembersPage)
    assert result.payload["error"] == "area members响应格式异常"
    assert result.payload["debug_reason"] == "get_area_members_malformed_data"


def test_oopz_sdk_area_members_as_model_returns_result_object_on_malformed_member_entry(
    monkeypatch,
):
    service = AreaService(_make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "members": [{"uid": "u1"}, "broken-member"],
                    "onlineCount": 1,
                    "totalCount": 2,
                },
            },
        ),
    )

    result = _run(service.get_area_members(as_model=True))

    assert isinstance(result, models.AreaMembersPage)
    assert result.payload["error"] == "area members响应格式异常"
    assert result.payload["debug_reason"] == "get_area_members_invalid_member"
    assert result.payload["invalid_index"] == 1


def test_oopz_sdk_joined_areas_as_model(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": [{"id": "area-1", "name": "测试域"}]},
        ),
    )

    result = _run(service.get_joined_areas(as_model=True))

    assert isinstance(result, models.JoinedAreasResult)
    assert result.areas[0].id == "area-1"
    assert result.areas[0].name == "测试域"


def test_oopz_sdk_joined_areas_as_model_returns_result_object_on_malformed_entry(
    monkeypatch,
):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": [{"id": "area-1"}, "broken-area"]},
        ),
    )

    result = _run(service.get_joined_areas(as_model=True))

    assert isinstance(result, models.JoinedAreasResult)
    assert result.payload["error"] == "joined areas响应格式异常"
    assert result.payload["invalid_index"] == 1


def test_oopz_sdk_joined_areas_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_joined_areas(as_model=True))

    assert isinstance(result, models.JoinedAreasResult)
    assert result.payload == {"error": "HTTP 503"}


def test_oopz_sdk_joined_areas_returns_error_dict_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_joined_areas())

    assert result == {"error": "HTTP 503"}


def test_oopz_sdk_joined_areas_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"id": "area-1"}},
        ),
    )

    result = _run(service.get_joined_areas(as_model=True))

    assert isinstance(result, models.JoinedAreasResult)
    assert result.payload == {"error": "joined areas响应格式异常"}


def test_oopz_sdk_area_info_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_area_info(as_model=True))

    assert isinstance(result, models.Area)
    assert result.payload == {"error": "HTTP 503"}


def test_oopz_sdk_area_info_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ["bad"]},
        ),
    )

    result = _run(service.get_area_info(as_model=True))

    assert isinstance(result, models.Area)
    assert result.payload == {"error": "area info响应格式异常"}


def test_oopz_sdk_area_service_get_area_channels_returns_error_dict_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_area_channels())

    assert result == {"error": "HTTP 503"}


def test_oopz_sdk_area_service_get_area_channels_returns_format_error_on_malformed_group(
    monkeypatch,
):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ["broken-group"]},
        ),
    )

    result = _run(service.get_area_channels(quiet=False))

    assert result["error"] == "channel groups响应格式异常"
    assert result["list_key"] == "groups"
    assert result["invalid_index"] == 0


def test_oopz_sdk_area_service_get_area_channels_returns_format_error_on_falsey_channels_value(
    monkeypatch,
):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": [
                    {
                        "id": "group-1",
                        "channels": "",
                    }
                ],
            },
        ),
    )

    result = _run(service.get_area_channels(quiet=False))

    assert result["error"] == "channel groups响应格式异常"
    assert result["list_key"] == "channels"
    assert result["invalid_type"] == "str"


def test_oopz_sdk_area_service_get_area_channels_returns_format_error_on_falsey_data(
    monkeypatch,
):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ""},
        ),
    )

    result = _run(service.get_area_channels(quiet=False))

    assert result == {"error": "channel groups响应格式异常"}


def test_oopz_sdk_populate_names_propagates_joined_area_error(monkeypatch):
    service = AreaService(None, _make_config())

    async def _fake_get_joined_areas(*args, **kwargs):
        return {"error": "joined areas unavailable"}

    monkeypatch.setattr(service, "get_joined_areas", _fake_get_joined_areas)

    result = _run(service.populate_names())

    assert result == {"error": "joined areas unavailable"}


def test_oopz_sdk_populate_names_propagates_channel_group_error(monkeypatch):
    service = AreaService(None, _make_config())

    async def _fake_get_joined_areas(*args, **kwargs):
        return [{"id": "area-1", "name": "测试域"}]

    async def _fake_get_area_channels(*args, **kwargs):
        return {"error": "channel groups unavailable"}

    monkeypatch.setattr(service, "get_joined_areas", _fake_get_joined_areas)
    monkeypatch.setattr(service, "get_area_channels", _fake_get_area_channels)

    result = _run(service.populate_names())

    assert result == {"error": "获取域频道列表失败: channel groups unavailable"}


def test_oopz_sdk_populate_names_does_not_commit_partial_names_before_failure(monkeypatch):
    service = AreaService(None, _make_config())
    named_areas = []
    named_channels = []

    async def _fake_get_joined_areas(*args, **kwargs):
        return [
            {"id": "area-1", "name": "测试域1"},
            {"id": "area-2", "name": "测试域2"},
        ]

    async def _fake_get_area_channels(area_id, *args, **kwargs):
        if area_id == "area-1":
            return [
                {
                    "channels": [
                        {"id": "channel-1", "name": "大厅"},
                    ]
                }
            ]
        return {"error": "channel groups unavailable"}

    monkeypatch.setattr(service, "get_joined_areas", _fake_get_joined_areas)
    monkeypatch.setattr(service, "get_area_channels", _fake_get_area_channels)

    result = _run(
        service.populate_names(
            set_area=lambda area_id, area_name: named_areas.append((area_id, area_name)),
            set_channel=lambda channel_id, channel_name: named_channels.append((channel_id, channel_name)),
        )
    )

    assert result == {"error": "获取域频道列表失败: channel groups unavailable"}
    assert named_areas == []
    assert named_channels == []


def test_oopz_sdk_channel_groups_as_model(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": [
                    {
                        "id": "group-1",
                        "name": "分组",
                        "channels": [{"id": "channel-1", "name": "大厅", "type": "TEXT"}],
                    }
                ],
            },
        ),
    )

    result = _run(service.get_area_channels(as_model=True))

    assert isinstance(result, models.ChannelGroupsResult)
    assert result.groups[0].channels[0].id == "channel-1"
    assert result.groups[0].channels[0].name == "大厅"


def test_oopz_sdk_channel_groups_as_model_returns_result_object_on_malformed_group_entry(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": [{"id": "group-1"}, "broken-group"]},
        ),
    )

    result = _run(service.get_area_channels(as_model=True))

    assert isinstance(result, models.ChannelGroupsResult)
    assert result.payload["error"] == "channel groups响应格式异常"
    assert result.payload["invalid_index"] == 1


def test_oopz_sdk_channel_groups_as_model_returns_result_object_on_malformed_channel_entry(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": [
                    {
                        "id": "group-1",
                        "channels": [{"id": "channel-1"}, "broken-channel"],
                    }
                ],
            },
        ),
    )

    result = _run(service.get_area_channels(as_model=True))

    assert isinstance(result, models.ChannelGroupsResult)
    assert result.payload["error"] == "channel groups响应格式异常"
    assert result.payload["invalid_index"] == 1
    assert result.payload["list_key"] == "channels"


def test_oopz_sdk_channel_group_model_rejects_falsey_non_list_channels():
    with pytest.raises(ValueError, match="channel groups响应格式异常"):
        Channel._to_channel_group_model({"id": "group-1", "channels": ""})


def test_oopz_sdk_get_area_channels_returns_format_error_on_falsey_channels_value(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": [
                    {
                        "id": "group-1",
                        "channels": "",
                    }
                ],
            },
        ),
    )

    result = _run(service.get_area_channels())

    assert result["error"] == "channel groups响应格式异常"
    assert result["list_key"] == "channels"
    assert result["invalid_type"] == "str"


def test_oopz_sdk_get_area_channels_returns_format_error_on_falsey_data(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ""},
        ),
    )

    result = _run(service.get_area_channels())

    assert result == {"error": "channel groups响应格式异常"}


def test_oopz_sdk_channel_groups_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_area_channels(as_model=True))

    assert isinstance(result, models.ChannelGroupsResult)
    assert result.payload == {"error": "HTTP 503"}


def test_oopz_sdk_channel_groups_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"id": "group-1"}},
        ),
    )

    result = _run(service.get_area_channels(as_model=True))

    assert isinstance(result, models.ChannelGroupsResult)
    assert result.payload == {"error": "channel groups响应格式异常"}


def test_oopz_sdk_get_area_channels_returns_error_dict_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_area_channels())

    assert result == {"error": "HTTP 503"}


def test_oopz_sdk_channel_setting_as_model_returns_result_object_on_malformed_role_fields(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "channel": "channel-1",
                    "textRoles": "broken-roles",
                },
            },
        ),
    )

    result = _run(service.get_channel_setting_info("channel-1", as_model=True))

    assert isinstance(result, models.ChannelSetting)
    assert result.payload == {"error": "频道设置响应格式异常"}


def test_oopz_sdk_channel_setting_as_model_returns_result_object_on_malformed_role_entry(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "channel": "channel-1",
                    "textRoles": [{"roleID": 1}],
                },
            },
        ),
    )

    result = _run(service.get_channel_setting_info("channel-1", as_model=True))

    assert isinstance(result, models.ChannelSetting)
    assert result.payload == {"error": "频道设置响应格式异常"}


def test_oopz_sdk_get_channel_setting_info_returns_error_dict_on_malformed_role_fields(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "channel": "channel-1",
                    "textRoles": "broken-roles",
                },
            },
        ),
    )

    result = _run(service.get_channel_setting_info("channel-1"))

    assert result == {"error": "频道设置响应格式异常"}


def test_oopz_sdk_get_channel_setting_info_returns_error_dict_on_malformed_role_entry(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "channel": "channel-1",
                    "textRoles": [{"roleID": 1}],
                },
            },
        ),
    )

    result = _run(service.get_channel_setting_info("channel-1"))

    assert result == {"error": "频道设置响应格式异常"}


def test_oopz_sdk_get_channel_setting_info_returns_raw_detail_dict_on_success(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "channel": "channel-1",
                    "area": "area-1",
                    "name": "大厅",
                    "textRoles": [1, 2],
                    "accessibleMembers": ["u1"],
                    "serverOnlyField": "keep-me",
                },
            },
        ),
    )

    result = _run(service.get_channel_setting_info("channel-1"))

    assert result == {
        "channel": "channel-1",
        "area": "area-1",
        "name": "大厅",
        "textRoles": [1, 2],
        "accessibleMembers": ["u1"],
        "serverOnlyField": "keep-me",
    }


def test_oopz_sdk_pick_channel_group_propagates_group_fetch_error(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_area_channels(*args, **kwargs):
        return {"error": "group list unavailable"}

    monkeypatch.setattr(
        service,
        "get_area_channels",
        _fake_get_area_channels,
    )

    result = _run(service._pick_channel_group("area-1"))

    assert result == {"error": "group list unavailable"}


def test_oopz_sdk_create_channel_reports_group_fetch_error(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_pick_channel_group(*args, **kwargs):
        return {"error": "group list unavailable"}

    monkeypatch.setattr(
        service,
        "_pick_channel_group",
        _fake_pick_channel_group,
    )

    result = _run(service.create_channel(name="测试频道"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "获取频道分组失败: group list unavailable"


def test_oopz_sdk_create_channel_returns_error_when_root_payload_is_not_dict(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(200, payload=[], text="[]"),
    )

    result = _run(service.create_channel(name="测试频道", group_id="group-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "创建频道响应格式异常"


def test_oopz_sdk_update_channel_returns_setting_error_when_role_fields_are_malformed(
    monkeypatch,
):
    service = Channel(None, _make_config())

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return {"error": "频道设置响应格式异常"}

    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)

    result = _run(service.update_channel(channel_id="channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "获取频道设置失败: 频道设置响应格式异常"


def test_oopz_sdk_update_channel_returns_setting_error_when_role_entry_is_malformed(
    monkeypatch,
):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "channel": "channel-1",
                    "textRoles": [{"roleID": 1}],
                },
            },
        ),
    )
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应继续写回频道设置")),
    )

    result = _run(service.update_channel(channel_id="channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "获取频道设置失败: 频道设置响应格式异常"


def test_oopz_sdk_update_channel_uses_explicit_channel_id_when_setting_omits_channel(
    monkeypatch,
):
    service = Channel(None, _make_config())
    captured = {}

    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "area": "area-1",
                    "name": "大厅",
                    "textRoles": [1],
                    "voiceRoles": [],
                    "accessible": [],
                    "accessibleMembers": ["u1"],
                },
            },
        ),
    )

    def _fake_post(url_path, body):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "message": "ok"})

    monkeypatch.setattr(service, "_post", _fake_post)

    result = _run(service.update_channel(channel_id="channel-1", area="area-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is True
    assert captured["url_path"] == "/area/v3/channel/setting/edit"
    assert captured["body"]["channel"] == "channel-1"


def test_oopz_sdk_update_channel_returns_error_when_root_payload_is_not_dict(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return models.ChannelSetting(channel="channel-1")

    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(200, payload=[], text="[]"),
    )

    result = _run(service.update_channel(channel_id="channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "更新频道响应格式异常"


def test_oopz_sdk_voice_channel_members_as_model_returns_result_object_on_malformed_success(
    monkeypatch,
):
    service = Channel(None, _make_config())

    async def _fake_get_voice_channel_ids(area):
        return ["voice-1"]

    monkeypatch.setattr(service, "_get_voice_channel_ids", _fake_get_voice_channel_ids)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"channelMembers": ["bad"]}},
        ),
    )

    result = _run(service.get_voice_channel_members(as_model=True))

    assert isinstance(result, models.VoiceChannelMembersResult)
    assert result.payload == {"error": "voice channel members响应格式异常"}


def test_oopz_sdk_voice_channel_members_as_model_returns_result_object_on_malformed_channel_members_entry(
    monkeypatch,
):
    service = Channel(None, _make_config())

    async def _fake_get_voice_channel_ids(area):
        return ["voice-1"]

    monkeypatch.setattr(service, "_get_voice_channel_ids", _fake_get_voice_channel_ids)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {"channelMembers": {"voice-1": [{"uid": "u1"}, "broken-member"]}},
            },
        ),
    )

    result = _run(service.get_voice_channel_members(as_model=True))

    assert isinstance(result, models.VoiceChannelMembersResult)
    assert result.payload["error"] == "voice channel members响应格式异常"
    assert result.payload["invalid_index"] == 1
    assert result.payload["list_key"] == "channelMembers.voice-1"


def test_oopz_sdk_voice_channel_members_as_model_returns_result_object_on_non_list_channel_members(
    monkeypatch,
):
    service = Channel(None, _make_config())

    async def _fake_get_voice_channel_ids(area):
        return ["voice-1"]

    monkeypatch.setattr(service, "_get_voice_channel_ids", _fake_get_voice_channel_ids)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {"channelMembers": {"voice-1": "broken-members"}},
            },
        ),
    )

    result = _run(service.get_voice_channel_members(as_model=True))

    assert isinstance(result, models.VoiceChannelMembersResult)
    assert result.payload["error"] == "voice channel members响应格式异常"
    assert result.payload["list_key"] == "channelMembers.voice-1"
    assert result.payload["invalid_type"] == "str"


def test_oopz_sdk_voice_channel_members_returns_error_dict_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_voice_channel_ids(area):
        return ["voice-1"]

    monkeypatch.setattr(service, "_get_voice_channel_ids", _fake_get_voice_channel_ids)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_voice_channel_members())

    assert result == {"error": "HTTP 503"}


def test_oopz_sdk_voice_channel_members_returns_error_dict_on_failed_payload(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_voice_channel_ids(area):
        return ["voice-1"]

    monkeypatch.setattr(service, "_get_voice_channel_ids", _fake_get_voice_channel_ids)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "voice members rejected"},
        ),
    )

    result = _run(service.get_voice_channel_members())

    assert result == {"error": "voice members rejected"}


def test_oopz_sdk_get_voice_channel_for_user_raises_on_error_dict(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_voice_channel_members(*args, **kwargs):
        return {"error": "voice members rejected"}

    monkeypatch.setattr(
        service,
        "get_voice_channel_members",
        _fake_get_voice_channel_members,
    )

    with pytest.raises(OopzApiError, match="voice members rejected") as exc_info:
        _run(service.get_voice_channel_for_user("user-1"))

    assert exc_info.value.response == {"error": "voice members rejected"}


def test_oopz_sdk_get_voice_channel_ids_propagates_group_fetch_error(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_area_channels(*args, **kwargs):
        return {"error": "group list unavailable"}

    monkeypatch.setattr(
        service,
        "get_area_channels",
        _fake_get_area_channels,
    )

    result = _run(service._get_voice_channel_ids("area-1"))

    assert result == {"error": "group list unavailable"}
    assert getattr(service, "_voice_ids_cache", {}) == {}


def test_oopz_sdk_create_voice_channel_invalidates_voice_ids_cache(monkeypatch):
    service = Channel(None, _make_config())
    service._voice_ids_cache = {
        "area": {"ids": ["voice-old"], "ts": 1.0},
        "area-2": {"ids": ["voice-keep"], "ts": 1.0},
    }
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(200, payload={"status": True, "data": {"channelId": "voice-new"}}),
    )

    result = _run(service.create_channel(area="area", name="语音房", channel_type="voice", group_id="group-1"))

    assert result.ok is True
    assert "area" not in service._voice_ids_cache
    assert service._voice_ids_cache["area-2"]["ids"] == ["voice-keep"]


def test_oopz_sdk_delete_channel_invalidates_voice_ids_cache(monkeypatch):
    service = Channel(None, _make_config())
    service._voice_ids_cache = {
        "area": {"ids": ["voice-old"], "ts": 1.0},
        "area-2": {"ids": ["voice-keep"], "ts": 1.0},
    }
    monkeypatch.setattr(
        service,
        "_delete",
        lambda *args, **kwargs: _FakeResponse(200, payload={"status": True, "message": "ok"}),
    )

    result = _run(service.delete_channel("channel-1", area="area"))

    assert result.ok is True
    assert "area" not in service._voice_ids_cache
    assert service._voice_ids_cache["area-2"]["ids"] == ["voice-keep"]


def test_oopz_sdk_delete_channel_returns_error_when_root_payload_is_not_dict(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_delete",
        lambda *args, **kwargs: _FakeResponse(200, payload=[], text="[]"),
    )

    result = _run(service.delete_channel("channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "删除频道响应格式异常"


def test_oopz_sdk_voice_channel_members_returns_error_when_voice_ids_fetch_fails(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_voice_channel_ids(*args, **kwargs):
        return {"error": "group list unavailable"}

    monkeypatch.setattr(service, "_get_voice_channel_ids", _fake_get_voice_channel_ids)

    result = _run(service.get_voice_channel_members())

    assert result == {"error": "group list unavailable"}


def test_oopz_sdk_channel_setting_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_channel_setting_info("channel-1", as_model=True))

    assert isinstance(result, models.ChannelSetting)
    assert result.channel == "channel-1"
    assert result.payload == {"error": "HTTP 503"}


def test_oopz_sdk_channel_setting_as_model_returns_result_object_when_channel_missing():
    service = Channel(None, _make_config())

    result = _run(service.get_channel_setting_info("", as_model=True))

    assert isinstance(result, models.ChannelSetting)
    assert result.payload == {"error": "缺少 channel"}


def test_oopz_sdk_create_restricted_text_channel_aborts_when_group_fetch_fails(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_pick_channel_group(*args, **kwargs):
        return {"error": "group list unavailable"}

    monkeypatch.setattr(
        service,
        "_pick_channel_group",
        _fake_pick_channel_group,
    )

    result = _run(service.create_restricted_text_channel("target-1"))

    assert result == {"error": "获取频道分组失败: group list unavailable"}


def test_oopz_sdk_create_restricted_text_channel_cleans_up_when_setting_fetch_fails(monkeypatch):
    service = Channel(None, _make_config())
    deleted = {}

    async def _fake_pick_channel_group(*args, **kwargs):
        return "group-1"

    async def _fake_delete_channel(channel, area=None):
        deleted["channel"] = channel
        deleted["area"] = area
        return models.OperationResult(ok=True, message="deleted")

    monkeypatch.setattr(
        service,
        "_pick_channel_group",
        _fake_pick_channel_group,
    )
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"channel": "channel-1"}},
        ),
    )

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return {"error": "setting unavailable"}

    monkeypatch.setattr(
        service,
        "get_channel_setting_info",
        _fake_get_channel_setting_info,
    )
    monkeypatch.setattr(
        service,
        "delete_channel",
        _fake_delete_channel,
    )

    result = _run(service.create_restricted_text_channel("target-1", area="area-1"))

    assert result == {"error": "获取频道设置失败: setting unavailable"}
    assert deleted == {"channel": "channel-1", "area": "area-1"}


def test_oopz_sdk_create_restricted_text_channel_reports_cleanup_failure(
    monkeypatch,
):
    service = Channel(None, _make_config())
    deleted = {}

    async def _fake_pick_channel_group(*args, **kwargs):
        return "group-1"

    async def _fake_delete_channel(channel, area=None):
        deleted["channel"] = channel
        deleted["area"] = area
        return models.OperationResult(ok=False, message="delete failed")

    monkeypatch.setattr(
        service,
        "_pick_channel_group",
        _fake_pick_channel_group,
    )
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"channel": "channel-1"}},
        ),
    )

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return {"error": "setting unavailable"}

    monkeypatch.setattr(
        service,
        "get_channel_setting_info",
        _fake_get_channel_setting_info,
    )
    monkeypatch.setattr(
        service,
        "delete_channel",
        _fake_delete_channel,
    )

    result = _run(service.create_restricted_text_channel("target-1", area="area-1"))

    assert result["error"] == "获取频道设置失败: setting unavailable；删除新建频道失败: delete failed"
    assert result["cleanup_error"] == "delete failed"
    assert deleted == {"channel": "channel-1", "area": "area-1"}


def test_oopz_sdk_create_restricted_text_channel_cleans_up_when_setting_has_malformed_role_entry(
    monkeypatch,
):
    service = Channel(None, _make_config())
    deleted = {}

    async def _fake_pick_channel_group(*args, **kwargs):
        return "group-1"

    async def _fake_delete_channel(channel, area=None):
        deleted["channel"] = channel
        deleted["area"] = area
        return models.OperationResult(ok=True, message="deleted")

    def _fake_post(url_path, body):
        if url_path == "/client/v1/area/v1/channel/v1/create":
            return _FakeResponse(200, payload={"status": True, "data": {"channel": "channel-1"}})
        raise AssertionError("不应继续写回受限频道设置")

    monkeypatch.setattr(service, "_pick_channel_group", _fake_pick_channel_group)
    monkeypatch.setattr(service, "_post", _fake_post)
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "channel": "channel-1",
                    "textRoles": [{"roleID": 1}],
                },
            },
        ),
    )
    monkeypatch.setattr(service, "delete_channel", _fake_delete_channel)

    result = _run(service.create_restricted_text_channel("target-1", area="area-1"))

    assert result == {"error": "获取频道设置失败: 频道设置响应格式异常"}
    assert deleted == {"channel": "channel-1", "area": "area-1"}


def test_oopz_sdk_create_restricted_text_channel_forces_secret_when_setting_omits_it(
    monkeypatch,
):
    service = Channel(None, _make_config())
    captured = {}

    async def _fake_pick_channel_group(*args, **kwargs):
        return "group-1"

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return models.ChannelSetting(channel="channel-1", area="area-1")

    def _fake_post(url_path, body):
        if url_path == "/client/v1/area/v1/channel/v1/create":
            return _FakeResponse(200, payload={"status": True, "data": {"channel": "channel-1"}})
        if url_path == "/area/v3/channel/setting/edit":
            captured["body"] = body
            return _FakeResponse(200, payload={"status": True, "message": "ok"})
        raise AssertionError(url_path)

    monkeypatch.setattr(service, "_pick_channel_group", _fake_pick_channel_group)
    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)
    monkeypatch.setattr(service, "_post", _fake_post)

    result = _run(service.create_restricted_text_channel("target-1", area="area-1"))

    assert result["status"] is True
    assert captured["body"]["secret"] is True
    assert captured["body"]["accessControlEnabled"] is True


def test_oopz_sdk_create_restricted_text_channel_uses_created_channel_id_when_setting_omits_channel(
    monkeypatch,
):
    service = Channel(None, _make_config())
    captured = {}

    async def _fake_pick_channel_group(*args, **kwargs):
        return "group-1"

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return models.ChannelSetting(channel="", area="area-1")

    def _fake_post(url_path, body):
        if url_path == "/client/v1/area/v1/channel/v1/create":
            return _FakeResponse(200, payload={"status": True, "data": {"channel": "channel-1"}})
        if url_path == "/area/v3/channel/setting/edit":
            captured["body"] = body
            return _FakeResponse(200, payload={"status": True, "message": "ok"})
        raise AssertionError(url_path)

    monkeypatch.setattr(service, "_pick_channel_group", _fake_pick_channel_group)
    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)
    monkeypatch.setattr(service, "_post", _fake_post)

    result = _run(service.create_restricted_text_channel("target-1", area="area-1"))

    assert result["status"] is True
    assert captured["body"]["channel"] == "channel-1"


def test_oopz_sdk_update_channel_requires_area_before_fetching_setting(monkeypatch):
    service = Channel(None, _make_config(default_area=""))

    async def _fake_get_channel_setting_info(*args, **kwargs):
        raise AssertionError("不应在缺少 area 时继续获取频道设置")

    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)

    with pytest.raises(ValueError, match="缺少 area"):
        _run(service.update_channel(channel_id="channel-1"))


def test_oopz_sdk_person_detail_as_model(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": [{"uid": "u1", "name": "Alice", "avatar": "avatar.png"}]},
        ),
    )

    result = _run(service.get_person_detail("u1", as_model=True))

    assert isinstance(result, models.PersonDetail)
    assert result.uid == "u1"
    assert result.name == "Alice"


def test_oopz_sdk_get_person_infos_batch_returns_error_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_person_infos_batch(["u1", "u2"]))

    assert result == {"error": "批量获取用户信息失败: HTTP 503"}


def test_oopz_sdk_get_person_infos_batch_returns_error_on_failed_payload(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "person infos unavailable"},
        ),
    )

    result = _run(service.get_person_infos_batch(["u1", "u2"]))

    assert result == {"error": "批量获取用户信息失败: person infos unavailable"}


def test_oopz_sdk_get_person_infos_batch_returns_error_with_partial_result_when_later_batch_fails(monkeypatch):
    service = Member(None, _make_config())
    calls = {"count": 0}

    def _fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse(
                200,
                payload={"status": True, "data": [{"uid": "u1", "name": "Alice"}]},
            )
        return _FakeResponse(503, text="gateway error")

    monkeypatch.setattr(service, "_post", _fake_post)

    result = _run(service.get_person_infos_batch([f"u{i}" for i in range(31)]))

    assert result["error"] == "批量获取用户信息失败: HTTP 503"
    assert result["partial_results"] == {"u1": {"uid": "u1", "name": "Alice"}}


def test_oopz_sdk_get_person_infos_batch_returns_rate_limit_with_partial_result_when_later_batch_hits_429(
    monkeypatch,
):
    service = Member(None, _make_config())
    calls = {"count": 0}

    def _fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse(
                200,
                payload={"status": True, "data": [{"uid": "u1", "name": "Alice"}]},
            )
        return _FakeResponse(429, text="too fast", headers={"Retry-After": "7"})

    monkeypatch.setattr(service, "_post", _fake_post)

    result = _run(service.get_person_infos_batch([f"u{i}" for i in range(31)]))

    assert result["error"] == "批量获取用户信息失败: HTTP 429"
    assert result["status_code"] == 429
    assert result["retry_after"] == 7
    assert result["partial_results"] == {"u1": {"uid": "u1", "name": "Alice"}}


def test_oopz_sdk_person_detail_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_person_detail("u1", as_model=True))

    assert isinstance(result, models.PersonDetail)
    assert result.payload == {"error": "HTTP 503"}


def test_oopz_sdk_person_detail_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"uid": "u1"}},
        ),
    )

    result = _run(service.get_person_detail("u1", as_model=True))

    assert isinstance(result, models.PersonDetail)
    assert result.payload == {"error": "person detail响应格式异常"}


def test_oopz_sdk_person_detail_as_model_returns_result_object_on_malformed_member_entry(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ["bad"]},
        ),
    )

    result = _run(service.get_person_detail("u1", as_model=True))

    assert isinstance(result, models.PersonDetail)
    assert result.payload == {"error": "person detail响应格式异常"}


def test_oopz_sdk_get_assignable_roles_returns_error_dict_on_malformed_role_entry(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"roles": [{"roleID": 1}, "broken-role"]}},
        ),
    )

    result = _run(service.get_assignable_roles("target-1"))

    assert result["error"] == "assignable roles响应格式异常"
    assert result["invalid_index"] == 1


def test_oopz_sdk_edit_user_role_returns_error_on_malformed_detail_shape(monkeypatch):
    service = Member(None, _make_config())

    async def _fake_get_user_area_detail(*args, **kwargs):
        return []

    monkeypatch.setattr(service, "get_user_area_detail", _fake_get_user_area_detail)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应继续修改身份组")),
    )

    result = _run(service.edit_user_role("target-1", 1, True))

    assert result == {"error": "user area detail响应格式异常"}


def test_oopz_sdk_self_detail_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_self_detail(as_model=True))

    assert isinstance(result, models.SelfDetail)
    assert result.payload == {"error": "HTTP 503"}


def test_oopz_sdk_area_blocks_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": "bad"},
        ),
    )

    result = _run(service.get_area_blocks(as_model=True))

    assert isinstance(result, models.AreaBlocksResult)
    assert result.payload == {"error": "area blocks响应格式异常"}


def test_oopz_sdk_area_blocks_as_model_returns_result_object_on_malformed_block_list(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"blocks": "bad"}},
        ),
    )

    result = _run(service.get_area_blocks(as_model=True))

    assert isinstance(result, models.AreaBlocksResult)
    assert result.payload == {"error": "area blocks响应格式异常"}


def test_oopz_sdk_area_blocks_as_model_returns_result_object_on_malformed_block_entry(
    monkeypatch,
):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"blocks": [{"uid": "u1"}, "broken-block"]}},
        ),
    )

    result = _run(service.get_area_blocks(as_model=True))

    assert isinstance(result, models.AreaBlocksResult)
    assert result.payload["error"] == "area blocks响应格式异常"
    assert result.payload["invalid_index"] == 1


def test_oopz_sdk_get_area_blocks_returns_error_dict_on_malformed_block_entry(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"blocks": [{"uid": "u1"}, "broken-block"]}},
        ),
    )

    result = _run(service.get_area_blocks())

    assert result["error"] == "area blocks响应格式异常"
    assert result["invalid_index"] == 1


def test_oopz_sdk_search_area_members_as_model_raises_api_error_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(service.search_area_members(keyword="alice", as_model=True))

    assert str(exc_info.value) == "HTTP 503"
    assert exc_info.value.response == {"error": "HTTP 503"}


def test_oopz_sdk_search_area_members_returns_error_dict_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.search_area_members(keyword="alice"))

    assert result == {"error": "HTTP 503"}


def test_oopz_sdk_search_area_members_as_model_raises_api_error_on_malformed_success(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"members": "bad"}},
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(service.search_area_members(keyword="alice", as_model=True))

    assert str(exc_info.value) == "search area members响应格式异常"
    assert exc_info.value.response == {"error": "search area members响应格式异常"}


def test_oopz_sdk_search_area_members_as_model_raises_api_error_on_malformed_member_entry(
    monkeypatch,
):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"members": [{"uid": "u1"}, "broken-member"]}},
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(service.search_area_members(keyword="alice", as_model=True))

    assert str(exc_info.value) == "search area members响应格式异常"
    assert exc_info.value.response["invalid_index"] == 1


def test_oopz_sdk_search_area_members_returns_error_dict_on_malformed_success(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"members": "bad"}},
        ),
    )

    result = _run(service.search_area_members(keyword="alice"))

    assert result == {"error": "search area members响应格式异常"}


def test_oopz_sdk_get_assignable_roles_returns_error_dict_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_assignable_roles("target-1"))

    assert result == {"error": "HTTP 503"}


def test_oopz_sdk_self_detail_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ["bad"]},
        ),
    )

    result = _run(service.get_self_detail(as_model=True))

    assert isinstance(result, models.SelfDetail)
    assert result.payload == {"error": "self detail响应格式异常"}


def test_oopz_sdk_local_image_segment_uses_injected_media(monkeypatch, tmp_path):
    sender = OopzRESTClient(_make_config())
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"not-an-image")

    monkeypatch.setattr(
        "oopz_sdk.services.message.get_image_info",
        lambda path: (32, 24, 128),
    )
    monkeypatch.setattr(
        "oopz_sdk.services.media.get_image_info",
        lambda path: (32, 24, 128),
    )

    captured = {}

    def _fail_upload(file_path, *, file_type, ext):
        captured["file_path"] = file_path
        captured["file_type"] = file_type
        captured["ext"] = ext
        raise OopzApiError("upload failed")

    monkeypatch.setattr(sender.media, "upload_file", _fail_upload)

    class _UnexpectedMedia:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Message 不应在内部重新创建 Media")

    monkeypatch.setattr("oopz_sdk.services.media.Media", _UnexpectedMedia)

    with pytest.raises(OopzApiError, match="upload failed"):
        _run(sender.messages.send_message(ImageSegment.from_file(str(sample)), auto_recall=False))

    assert captured == {
        "file_path": str(sample),
        "file_type": "IMAGE",
        "ext": ".png",
    }


def test_oopz_sdk_local_image_segment_requires_injected_media(monkeypatch, tmp_path):
    service = Message(_make_config())
    sample = tmp_path / "sample.png"
    sample.write_bytes(b"not-an-image")

    monkeypatch.setattr(
        "oopz_sdk.services.message.get_image_info",
        lambda path: (32, 24, 128),
    )

    class _UnexpectedMedia:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Message 不应在内部重新创建 Media")

    monkeypatch.setattr("oopz_sdk.services.media.Media", _UnexpectedMedia)

    with pytest.raises(RuntimeError, match="media"):
        _run(service.send_message(ImageSegment.from_file(str(sample)), auto_recall=False))


def test_oopz_sdk_dispatcher_message_handler_receives_message_then_context():
    registry = EventRegistry()
    captured = {}

    @registry.on("message")
    def _handler(message, ctx):
        captured["message"] = message
        captured["ctx"] = ctx

    dispatcher = EventDispatcher(registry)
    ctx = EventContext(bot=None, config=_make_config())
    event = MessageEvent(
        name="message",
        event_type=9,
        message=models.Message(message_id="msg-1", content="hello", text="hello"),
    )

    asyncio.run(dispatcher.dispatch("message", event, ctx))

    assert isinstance(captured["message"], models.Message)
    assert captured["message"].message_id == "msg-1"
    assert captured["ctx"] is ctx


def test_oopz_sdk_dispatcher_does_not_swallow_handler_error():
    registry = EventRegistry()

    @registry.on("message")
    def _handler(message, ctx):
        raise RuntimeError("handler boom")

    dispatcher = EventDispatcher(registry)
    ctx = EventContext(bot=None, config=_make_config())
    event = MessageEvent(
        name="message",
        event_type=9,
        message=models.Message(message_id="msg-1", content="hello", text="hello"),
    )

    with pytest.raises(RuntimeError, match="handler boom"):
        asyncio.run(dispatcher.dispatch("message", event, ctx))


def test_oopz_sdk_ws_client_does_not_reconnect_on_callback_error():
    errors = []

    class _FakeTransport:
        def __init__(self):
            self.connect_calls = 0
            self.close_calls = 0
            self.sent = []
            self.closed = True

        async def connect(self):
            self.connect_calls += 1
            self.closed = False

        async def recv(self):
            return "raw-message"

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.close_calls += 1
            self.closed = True

    async def _on_message(raw):
        raise RuntimeError("handler boom")

    async def _on_error(error):
        errors.append(str(error))

    client = OopzWSClient(
        _make_config(),
        on_message=_on_message,
        on_error=_on_error,
    )
    client.transport = _FakeTransport()

    with pytest.raises(RuntimeError, match="handler boom"):
        _run(client.start())

    assert client.transport.connect_calls == 1
    assert errors == ["handler boom"]


def test_oopz_sdk_bot_ws_parse_error_is_not_swallowed():
    errors = []

    class _FakeTransport:
        def __init__(self):
            self.connect_calls = 0
            self.close_calls = 0
            self.sent = []
            self.closed = True

        async def connect(self):
            self.connect_calls += 1
            self.closed = False

        async def recv(self):
            return "not-json"

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.close_calls += 1
            self.closed = True

    bot = OopzBot(_make_config())

    @bot.on_error
    async def _on_error(ctx, error):
        errors.append(str(error))

    bot.ws.transport = _FakeTransport()

    with pytest.raises(OopzParseError, match="Invalid event payload"):
        _run(bot.ws.start())

    assert bot.ws.transport.connect_calls == 1
    assert errors == ["Invalid event payload"]


def test_oopz_sdk_event_registry_deduplicates_same_handler():
    registry = EventRegistry()

    def handler(ctx):
        return ctx

    registry.on("ready", handler)
    registry.on("ready", handler)

    assert registry.get_handlers("ready") == [handler]


def test_oopz_sdk_bot_named_hooks_share_one_registration_path():
    bot = OopzBot(_make_config())

    def handler(ctx):
        return ctx

    bot.on("ready")(handler)
    bot.on_ready(handler)

    assert bot.registry.get_handlers("ready") == [handler]


def test_oopz_sdk_bot_convenience_methods_allow_config_defaults():
    bot = OopzBot(_make_config())
    send_calls = []
    recall_calls = []

    class _Messages:
        async def send_message(
            self,
            *texts,
            area=None,
            channel=None,
            reference_message_id=None,
        ):
            payload = {
                "texts": texts,
                "area": area,
                "channel": channel,
                "reference_message_id": reference_message_id,
            }
            send_calls.append(payload)
            return payload

        async def recall_message(self, message_id, area=None, channel=None, **kwargs):
            payload = {
                "message_id": message_id,
                "area": area,
                "channel": channel,
                **kwargs,
            }
            recall_calls.append(payload)
            return payload

    bot.messages = _Messages()

    send_result = _run(bot.send("hello"))
    reply_result = _run(bot.reply("pong", reference_message_id="msg-1"))
    recall_result = _run(bot.recall("msg-2"))

    assert send_result["texts"] == ("hello",)
    assert send_calls[0]["area"] is None
    assert send_calls[0]["channel"] is None

    assert reply_result["texts"] == ("pong",)
    assert reply_result["reference_message_id"] == "msg-1"
    assert reply_result["area"] is None
    assert reply_result["channel"] is None

    assert recall_result["message_id"] == "msg-2"
    assert recall_result["area"] is None
    assert recall_result["channel"] is None
    assert recall_calls[0]["area"] is None
    assert recall_calls[0]["channel"] is None


def test_oopz_sdk_http_transport_wraps_timeout_as_connection_error(monkeypatch):
    config = _make_config(rate_limit_interval=0)
    transport = HttpTransport(config, signer=object())

    monkeypatch.setattr(oopz_http_transport, "build_oopz_headers", lambda *args, **kwargs: {})

    class _TimeoutContext:
        async def __aenter__(self):
            raise asyncio.TimeoutError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _Session:
        closed = False

        def request(self, *args, **kwargs):
            return _TimeoutContext()

    transport._client_session = _Session()

    with pytest.raises(OopzConnectionError, match="request failed: boom"):
        _run(transport.request("GET", "/timeout"))


def test_oopz_sdk_event_context_has_single_send_definition():
    source = Path("oopz_sdk/events/context.py").read_text(encoding="utf-8")

    assert source.count("async def send(") == 1


@pytest.mark.parametrize(
    ("method_name", "event"),
    [
        ("send", MessageEvent(name="message", event_type=9, message=models.Message.from_dict({"id": "msg-1", "area": "area-1", "channel": "channel-1"}))),
        ("reply", MessageEvent(name="message", event_type=9, message=models.Message.from_dict({"id": "msg-1", "area": "area-1", "channel": "channel-1"}))),
        ("recall", MessageEvent(name="message", event_type=9, message=models.Message.from_dict({"id": "msg-1", "area": "area-1", "channel": "channel-1"}))),
    ],
)
def test_oopz_sdk_event_context_async_methods_do_not_block_event_loop(method_name, event):
    order = []

    class _Messages:
        async def send_message(self, *args, **kwargs):
            await asyncio.sleep(0.05)
            order.append("send_message")
            return kwargs

        async def send_private_message(self, *args, **kwargs):
            await asyncio.sleep(0.05)
            order.append("send_private_message")
            return kwargs

        async def recall_message(self, **kwargs):
            await asyncio.sleep(0.05)
            order.append("recall_message")
            return kwargs

    class _Bot:
        def __init__(self):
            self.messages = _Messages()

    ctx = EventContext(bot=_Bot(), config=_make_config(), event=event)

    async def _marker():
        await asyncio.sleep(0.01)
        order.append("tick")

    async def _invoke():
        if method_name == "send":
            await ctx.send("hello", area="area-1", channel="channel-1")
            return
        if method_name == "reply":
            await ctx.reply("hello")
            return
        await ctx.recall()

    async def _run():
        await asyncio.gather(_invoke(), _marker())

    asyncio.run(_run())

    assert order[0] == "tick"


def test_oopz_sdk_message_from_dict_accepts_legacy_id_field():
    message = models.Message.from_dict(
        {
            "id": "msg-legacy",
            "area": "area-1",
            "channel": "channel-1",
            "content": "hello",
        }
    )

    assert message.message_id == "msg-legacy"
    assert message.content == "hello"


def test_oopz_sdk_chat_event_parser_rejects_invalid_body():
    parser = EventParser()

    with pytest.raises(OopzParseError):
        parser.parse({"event": 9, "body": "not-json"})


def test_oopz_sdk_chat_event_parser_rejects_invalid_message_data():
    parser = EventParser()

    with pytest.raises(OopzParseError):
        parser.parse({"event": 9, "body": '{"data":"not-json"}'})


def test_oopz_sdk_private_event_parser_rejects_invalid_body():
    parser = EventParser()

    with pytest.raises(OopzParseError):
        parser.parse({"event": EVENT_PRIVATE_MESSAGE, "body": "not-json"})


def test_oopz_sdk_private_event_parser_rejects_invalid_message_data():
    parser = EventParser()

    with pytest.raises(OopzParseError):
        parser.parse({"event": EVENT_PRIVATE_MESSAGE, "body": '{"data":"not-json"}'})


def test_oopz_sdk_event_context_private_recall_raises_not_implemented_error():
    event = MessageEvent(
        name="message.private",
        event_type=EVENT_PRIVATE_MESSAGE,
        message=models.Message.from_dict(
            {
                "id": "msg-private-1",
                "channel": "dm-1",
                "person": "user-1",
            }
        ),
        is_private=True,
    )
    ctx = EventContext(
        bot=SimpleNamespace(messages=Message(None, _make_config())),
        config=_make_config(),
        event=event,
    )

    with pytest.raises(NotImplementedError, match="暂不支持撤回私信消息"):
        asyncio.run(ctx.recall())


def test_oopz_sdk_event_context_reply_uses_message_id_from_legacy_id():
    class _Messages:
        def __init__(self):
            self.calls = []

        async def send_message(self, *texts, **kwargs):
            self.calls.append(kwargs)
            return kwargs

    class _Bot:
        def __init__(self):
            self.messages = _Messages()

    bot = _Bot()
    event = MessageEvent(
        name="message",
        event_type=9,
        message=models.Message.from_dict(
            {
                "id": "msg-legacy",
                "area": "area-1",
                "channel": "channel-1",
                "content": "hello",
            }
        ),
    )
    ctx = EventContext(bot=bot, config=_make_config(), event=event)

    result = asyncio.run(ctx.reply("pong"))

    assert result["reference_message_id"] == "msg-legacy"
    assert bot.messages.calls[0]["reference_message_id"] == "msg-legacy"


def test_oopz_sdk_message_service_has_single_upload_local_image_segment_definition():
    source = Path("oopz_sdk/services/message.py").read_text(encoding="utf-8")

    assert source.count("def _upload_local_image_segment(") == 1


def test_oopz_sdk_client_optional_dependency_message_uses_real_missing_module_name():
    exc = ModuleNotFoundError("No module named 'aiohttp'")
    exc.name = "aiohttp"

    assert oopz_client._optional_dependency_message(exc, feature="WebSocket features") == (
        "aiohttp is required for WebSocket features"
    )


def test_oopz_sdk_client_optional_dependency_message_re_raises_internal_missing_module():
    exc = ModuleNotFoundError("No module named 'oopz_sdk.events'")
    exc.name = "oopz_sdk.events"

    with pytest.raises(ModuleNotFoundError) as exc_info:
        oopz_client._optional_dependency_message(exc, feature="WebSocket features")

    assert exc_info.value is exc


def test_oopz_sdk_package_optional_dependency_message_uses_real_missing_module_name():
    exc = ModuleNotFoundError("No module named 'PIL'")
    exc.name = "PIL"

    assert oopz_sdk._optional_dependency_message(exc, feature="image helpers") == (
        "PIL is required for image helpers"
    )


def test_oopz_sdk_version_matches_package_version():
    from oopz_sdk import __version__

    assert __version__ == "0.5.0"
