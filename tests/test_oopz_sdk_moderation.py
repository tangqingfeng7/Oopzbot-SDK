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

from tests._oopz_sdk_test_support import _FakeResponse, _make_config, _make_private_key, _run

def test_oopz_sdk_mute_user_requires_area_before_request(monkeypatch):
    service = Moderation(None, _make_config(default_area="area-default"))

    async def _fake_request(*args, **kwargs):
        raise AssertionError("不应在缺少 area 时继续禁言用户")

    monkeypatch.setattr(service, "_request", _fake_request)

    with pytest.raises(ValueError, match="缺少 area"):
        _run(service.mute_user("target-1"))


def test_oopz_sdk_mute_user_returns_operation_result_on_http_failure(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_request",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.mute_user("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "HTTP 503 | gateway error"


def test_oopz_sdk_remove_from_area_returns_operation_result_on_non_json_response(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(200, payload=None, text="<html>bad gateway</html>"),
    )

    result = _run(service.remove_from_area("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "响应非 JSON: <html>bad gateway</html>"
    assert result.payload == {"area": "area", "target": "target-1"}


def test_oopz_sdk_remove_from_area_returns_request_payload_on_http_failure(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.remove_from_area("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "HTTP 503 | gateway error"
    assert result.payload == {"area": "area", "target": "target-1"}


def test_oopz_sdk_remove_from_area_returns_request_payload_on_request_error(monkeypatch):
    service = Moderation(None, _make_config())

    async def _fake_post(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(service, "_post", _fake_post)

    result = _run(service.remove_from_area("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "network down"
    assert result.payload == {"area": "area", "target": "target-1"}


def test_oopz_sdk_remove_from_area_returns_request_payload_on_failed_payload(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "remove rejected"},
        ),
    )

    result = _run(service.remove_from_area("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "remove rejected"
    assert result.payload["area"] == "area"
    assert result.payload["target"] == "target-1"
    assert result.payload["status"] is False
    assert result.payload["message"] == "remove rejected"


@pytest.mark.parametrize(
    ("method_name", "call_kwargs", "expected_payload"),
    [
        (
            "unmute_user",
            {"uid": "target-1", "area": "area"},
            {"area": "area", "target": "target-1"},
        ),
        (
            "mute_mic",
            {"uid": "target-1", "area": "area", "duration": 10},
            {"area": "area", "target": "target-1", "intervalId": "9"},
        ),
        (
            "unmute_mic",
            {"uid": "target-1", "area": "area"},
            {"area": "area", "target": "target-1"},
        ),
        (
            "unblock_user_in_area",
            {"uid": "target-1", "area": "area"},
            {"area": "area", "target": "target-1"},
        ),
    ],
)
def test_oopz_sdk_manage_patch_actions_return_request_payload_on_http_failure(
    monkeypatch,
    method_name,
    call_kwargs,
    expected_payload,
):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_request",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    method = getattr(service, method_name)
    result = _run(method(**call_kwargs))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "HTTP 503 | gateway error"
    assert result.payload == expected_payload


@pytest.mark.parametrize(
    ("method_name", "call_kwargs", "expected_payload"),
    [
        (
            "unmute_user",
            {"uid": "target-1", "area": "area"},
            {"area": "area", "target": "target-1"},
        ),
        (
            "mute_mic",
            {"uid": "target-1", "area": "area", "duration": 10},
            {"area": "area", "target": "target-1", "intervalId": "9"},
        ),
    ],
)
def test_oopz_sdk_manage_patch_actions_return_request_payload_on_non_json_response(
    monkeypatch,
    method_name,
    call_kwargs,
    expected_payload,
):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_request",
        lambda *args, **kwargs: _FakeResponse(200, payload=None, text="<html>bad gateway</html>"),
    )

    method = getattr(service, method_name)
    result = _run(method(**call_kwargs))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "响应非 JSON: <html>bad gateway</html>"
    assert result.payload == expected_payload


def test_oopz_sdk_manage_patch_actions_return_request_payload_on_failed_payload(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_request",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "patch rejected"},
        ),
    )

    result = _run(service.unmute_user(uid="target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "patch rejected"
    assert result.payload["area"] == "area"
    assert result.payload["target"] == "target-1"
    assert result.payload["status"] is False
    assert result.payload["message"] == "patch rejected"


def test_oopz_sdk_block_user_in_area_returns_operation_result_on_http_failure(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_delete",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.block_user_in_area("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "HTTP 503 | gateway error"
    assert result.payload == {"area": "area", "target": "target-1"}


def test_oopz_sdk_block_user_in_area_returns_request_payload_on_request_error(monkeypatch):
    service = Moderation(None, _make_config())

    async def _fake_delete(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(service, "_delete", _fake_delete)

    result = _run(service.block_user_in_area("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "network down"
    assert result.payload == {"area": "area", "target": "target-1"}


def test_oopz_sdk_block_user_in_area_returns_request_payload_on_failed_payload(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_delete",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "block rejected"},
        ),
    )

    result = _run(service.block_user_in_area("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "block rejected"
    assert result.payload["area"] == "area"
    assert result.payload["target"] == "target-1"
    assert result.payload["status"] is False
    assert result.payload["message"] == "block rejected"


def test_oopz_sdk_block_user_in_area_returns_request_payload_on_non_json_response(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_delete",
        lambda *args, **kwargs: _FakeResponse(200, payload=None, text="<html>bad gateway</html>"),
    )

    result = _run(service.block_user_in_area("target-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "响应非 JSON: <html>bad gateway</html>"
    assert result.payload == {"area": "area", "target": "target-1"}
