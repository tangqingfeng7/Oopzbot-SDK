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

from tests._oopz_sdk_test_support import (
    _FakeResponse,
    _make_config,
    _make_message_service,
    _make_private_key,
    _run,
)

def test_oopz_sdk_send_message_returns_result_model(monkeypatch):
    service = _make_message_service()
    captured = {}

    async def fake_request_json(method, path, params=None, body=None):
        captured.update({"method": method, "path": path, "params": params, "body": body})
        return {"messageId": "msg-1", "timestamp": "123"}

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    result = _run(service.send_message("hello", area="area", channel="channel", auto_recall=False))

    assert isinstance(result, models.MessageSendResult)
    assert result.message_id == "msg-1"
    assert captured["method"] == "POST"
    assert captured["path"] == "/im/session/v2/sendGimMessage"
    assert captured["body"]["message"]["area"] == "area"
    assert captured["body"]["message"]["channel"] == "channel"


def test_oopz_sdk_send_message_rejects_explicit_failure_payload(monkeypatch):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        raise OopzApiError("denied")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(OopzApiError, match="denied"):
        _run(service.send_message("hello", area="area", channel="channel", auto_recall=False))


def test_oopz_sdk_send_message_requires_area_before_request(monkeypatch):
    service = _make_message_service(default_area="area-default", default_channel="channel-default")

    with pytest.raises(TypeError, match="required keyword-only argument: 'area'"):
        _run(service.send_message("hello", channel="channel-1", auto_recall=False))


def test_oopz_sdk_recall_message_returns_operation_result(monkeypatch):
    service = _make_message_service()
    captured = {}

    async def fake_request_json(method, path, params=None, body=None):
        captured.update({"method": method, "path": path, "params": params, "body": body})
        return True

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    result = _run(service.recall_message("msg-1", area="area", channel="channel"))

    assert result.ok is True
    assert captured["method"] == "POST"
    assert captured["path"] == "/im/session/v1/recallGim"
    assert captured["params"] is None
    assert captured["body"]["messageId"] == "msg-1"
    assert captured["body"]["channel"] == "channel"


def test_oopz_sdk_recall_message_rejects_explicit_failure_payload(monkeypatch):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        raise OopzApiError("denied")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(OopzApiError, match="denied"):
        _run(service.recall_message("msg-1", area="area", channel="channel"))


def test_oopz_sdk_recall_message_returns_operation_result_on_http_failure(monkeypatch):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        raise OopzApiError("HTTP 503")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(OopzApiError, match="HTTP 503"):
        _run(service.recall_message("msg-1", area="area", channel="channel"))


def test_oopz_sdk_recall_message_returns_operation_result_on_non_json_response(monkeypatch):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        raise OopzApiError("response is not valid JSON: no json")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(OopzApiError, match="response is not valid JSON"):
        _run(service.recall_message("msg-1", area="area", channel="channel"))


def test_oopz_sdk_open_private_session_rejects_explicit_failure_payload(monkeypatch):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        raise OopzApiError("denied")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(OopzApiError, match="denied"):
        _run(service.open_private_session("target-1"))


def test_oopz_sdk_get_channel_messages_returns_error_dict_on_http_failure(monkeypatch):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        raise OopzApiError("HTTP 503")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(OopzApiError, match="HTTP 503"):
        _run(service.get_channel_messages(area="area", channel="channel"))


def test_oopz_sdk_get_channel_messages_requires_channel_before_request(monkeypatch):
    service = _make_message_service(default_area="area-default", default_channel="channel-default")

    with pytest.raises(TypeError, match="missing 1 required positional argument: 'channel'"):
        _run(service.get_channel_messages(area="area-1"))


def test_oopz_sdk_recall_private_message_returns_operation_result(monkeypatch):
    service = _make_message_service()
    captured = {}

    async def fake_request_json(method, path, params=None, body=None):
        captured.update({"method": method, "path": path, "params": params, "body": body})
        return True

    monkeypatch.setattr(service.transport, "request_json", fake_request_json)

    result = _run(service.recall_private_message("msg-1", channel="dm-1", target="user-1"))

    assert result.ok is True
    assert captured["method"] == "POST"
    assert captured["path"] == "/im/session/v1/recallIm"
    assert captured["params"] is None
    assert captured["body"]["messageId"] == "msg-1"
    assert captured["body"]["channel"] == "dm-1"
    assert captured["body"]["target"] == "user-1"


def test_oopz_sdk_get_channel_messages_returns_error_dict_when_message_item_is_invalid(
    monkeypatch,
):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        return {
            "messages": [
                {"messageId": "msg-1", "content": "hello"},
                "broken-message-item",
            ]
        }

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(OopzApiError, match="invalid message payload: expected dict"):
        _run(service.get_channel_messages(area="area", channel="channel"))


def test_oopz_sdk_get_channel_messages_returns_error_dict_on_failed_status(monkeypatch):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        raise OopzApiError("status is not True")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(OopzApiError, match="status is not True"):
        _run(service.get_channel_messages(area="area", channel="channel"))


def test_oopz_sdk_get_channel_messages_returns_error_dict_when_root_payload_is_invalid(
    monkeypatch,
):
    service = _make_message_service()

    async def fake_request_json(method, path, params=None, body=None):
        return ["bad-root"]

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    with pytest.raises(AttributeError, match="'list' object has no attribute 'get'"):
        _run(service.get_channel_messages(area="area", channel="channel"))


def test_oopz_sdk_private_message_returns_result_model(monkeypatch):
    service = _make_message_service()
    dm_channel = "DM12345678901234567890"
    calls = []

    async def fake_request_json(method, path, params=None, body=None):
        calls.append({"method": method, "path": path, "params": params, "body": body})
        if path == "/client/v1/chat/v1/to":
            return {"sessionId": dm_channel}
        if path == "/im/session/v2/sendImMessage":
            return {"messageId": "dm-1", "timestamp": "123"}
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(service, "_request_json", fake_request_json)

    result = _run(service.send_private_message("hello", target="target-1"))

    assert isinstance(result, models.MessageSendResult)
    assert result.message_id == "dm-1"
    assert [call["method"] for call in calls] == ["PATCH", "POST"]
    assert calls[0]["params"] == {"target": "target-1"}
    assert calls[1]["path"] == "/im/session/v2/sendImMessage"
    assert calls[1]["body"]["message"]["channel"] == dm_channel
    assert calls[1]["body"]["message"]["target"] == "target-1"


@pytest.mark.parametrize(
    ("method_name", "event"),
    [
        ("send", MessageEvent(name="message", event_type=9, message=models.Message(message_id="msg-1", area="area-1", channel="channel-1"))),
        ("reply", MessageEvent(name="message", event_type=9, message=models.Message(message_id="msg-1", area="area-1", channel="channel-1"))),
        ("recall", MessageEvent(name="message", event_type=9, message=models.Message(message_id="msg-1", area="area-1", channel="channel-1"))),
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


def test_oopz_sdk_message_model_accepts_message_id_field():
    message = models.Message(
        message_id="msg-1",
        area="area-1",
        channel="channel-1",
        content="hello",
    )

    assert message.message_id == "msg-1"
    assert message.content == "hello"


def test_oopz_sdk_event_context_private_recall_raises_runtime_error():
    event = MessageEvent(
        name="message.private",
        event_type=EVENT_PRIVATE_MESSAGE,
        message=models.Message(
            message_id="msg-private-1",
            channel="dm-1",
            sender_id="user-1",
        ),
        is_private=True,
    )
    ctx = EventContext(
        bot=SimpleNamespace(messages=_make_message_service()),
        config=_make_config(),
        event=event,
    )

    with pytest.raises(RuntimeError, match="recall\\(\\) is not supported for private messages"):
        asyncio.run(ctx.recall())


def test_oopz_sdk_event_context_reply_uses_message_id_from_model():
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
        message=models.Message(
            message_id="msg-1",
            area="area-1",
            channel="channel-1",
            content="hello",
        ),
    )
    ctx = EventContext(bot=bot, config=_make_config(), event=event)

    result = asyncio.run(ctx.reply("pong"))

    assert result["reference_message_id"] == "msg-1"
    assert bot.messages.calls[0]["reference_message_id"] == "msg-1"
