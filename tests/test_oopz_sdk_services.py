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
from pydantic import ValidationError

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

from tests._oopz_sdk_test_support import _FakeResponse, _make_config, _make_message_service, _make_private_key, _run

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


def test_oopz_sdk_rest_client_exposes_single_public_config_reference():
    config = _make_config()
    sender = OopzRESTClient(config)

    assert sender.config is config
    assert hasattr(sender, "_config") is False


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
        _run(sender.messages.send_message(ImageSegment.from_file(str(sample)), area="area", channel="channel", auto_recall=False))

    assert captured == {
        "file_path": str(sample),
        "file_type": "IMAGE",
        "ext": ".png",
    }


def test_oopz_sdk_local_image_segment_requires_injected_media(monkeypatch, tmp_path):
    service = _make_message_service()
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
        _run(service.send_message(ImageSegment.from_file(str(sample)), area="area", channel="channel", auto_recall=False))


def test_oopz_sdk_message_service_has_single_upload_local_image_segment_definition():
    source = Path("oopz_sdk/services/message.py").read_text(encoding="utf-8")

    assert source.count("def _upload_local_image_segment(") == 1
