import asyncio
import io
import logging
from aiohttp import WSMessage, WSMsgType
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
from oopz_sdk.client.ws import CloseInfo, OopzWSClient
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
from oopz_sdk.transport.ws import WebSocketClosedError, WebSocketTransport

from tests._oopz_sdk_test_support import _FakeResponse, _make_config, _make_private_key, _run

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


def test_oopz_sdk_dispatcher_forwards_handler_error_to_error_event_without_raising():
    registry = EventRegistry()
    captured = {}

    @registry.on("message")
    def _handler(message, ctx):
        raise RuntimeError("handler boom")

    @registry.on("error")
    def _on_error(ctx, error):
        captured["ctx"] = ctx
        captured["error"] = error

    dispatcher = EventDispatcher(registry)
    ctx = EventContext(bot=None, config=_make_config())
    event = MessageEvent(
        name="message",
        event_type=9,
        message=models.Message(message_id="msg-1", content="hello", text="hello"),
    )

    asyncio.run(dispatcher.dispatch("message", event, ctx))

    assert isinstance(captured["error"], RuntimeError)
    assert str(captured["error"]) == "handler boom"
    assert captured["ctx"].event is captured["error"]


def test_oopz_sdk_dispatcher_keeps_running_when_message_handler_raises():
    registry = EventRegistry()
    steps = []

    @registry.on("message")
    def _handler(message, ctx):
        steps.append("message")
        raise RuntimeError("handler boom")

    @registry.on("error")
    def _on_error(ctx, error):
        steps.append("error")

    dispatcher = EventDispatcher(registry)
    ctx = EventContext(bot=None, config=_make_config())
    event = MessageEvent(
        name="message",
        event_type=9,
        message=models.Message(message_id="msg-2", content="hello", text="hello"),
    )

    asyncio.run(dispatcher.dispatch("message", event, ctx))

    assert steps == ["message", "error"]


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


def test_oopz_sdk_ws_client_calls_on_close_after_connected_receive_failure():
    close_infos = []

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
            raise ConnectionError("socket closed")

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.close_calls += 1
            self.closed = True

    async def _on_close(close_info):
        close_infos.append(close_info)
        client._running = False

    config = _make_config()
    config.heartbeat.reconnect_interval = 0.01
    config.heartbeat.max_reconnect_interval = 0.01
    client = OopzWSClient(config, on_close=_on_close)
    client.transport = _FakeTransport()

    async def _exercise():
        task = asyncio.create_task(client.start())
        await asyncio.sleep(0.05)
        if task.done():
            await task
            return
        client._running = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    _run(_exercise())

    assert client.transport.connect_calls >= 1
    assert client.transport.close_calls >= 1
    assert len(close_infos) == 1
    assert isinstance(close_infos[0], CloseInfo)
    assert close_infos[0].reason == "connection closed"
    assert close_infos[0].reconnecting is True


def test_oopz_sdk_ws_transport_close_message_preserves_code_and_reason():
    transport = WebSocketTransport(_make_config())

    class _WS:
        close_code = None

        async def receive(self):
            return WSMessage(WSMsgType.CLOSE, 4001, "remote closed")

    transport._ws = _WS()

    with pytest.raises(WebSocketClosedError) as exc_info:
        _run(transport.recv())

    assert exc_info.value.code == 4001
    assert exc_info.value.reason == "remote closed"


def test_oopz_sdk_ws_transport_closed_message_uses_close_code_and_default_reason():
    transport = WebSocketTransport(_make_config())

    class _WS:
        close_code = 4002

        async def receive(self):
            return WSMessage(WSMsgType.CLOSED, None, None)

    transport._ws = _WS()

    with pytest.raises(WebSocketClosedError) as exc_info:
        _run(transport.recv())

    assert exc_info.value.code == 4002
    assert exc_info.value.reason == "connection closed"


def test_oopz_sdk_ws_client_calls_on_close_with_stopped_reason():
    close_infos = []

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
            await asyncio.sleep(0.01)
            raise WebSocketClosedError(code=4003, reason="server shutdown")

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.close_calls += 1
            self.closed = True

    async def _on_open():
        asyncio.create_task(client.stop())

    async def _on_close(close_info):
        close_infos.append(close_info)

    client = OopzWSClient(_make_config(), on_open=_on_open, on_close=_on_close)
    client.transport = _FakeTransport()

    _run(client.start())

    assert client.transport.connect_calls == 1
    assert client.transport.close_calls >= 1
    assert len(close_infos) == 1
    assert close_infos[0].code == 4003
    assert close_infos[0].reason == "stopped"
    assert close_infos[0].reconnecting is False


def test_oopz_sdk_ws_client_stop_does_not_report_normal_close_as_error(caplog):
    close_infos = []
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
            await asyncio.sleep(0.01)
            raise WebSocketClosedError(code=4004, reason="client stop")

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.close_calls += 1
            self.closed = True

    async def _on_open():
        asyncio.create_task(client.stop())

    async def _on_close(close_info):
        close_infos.append(close_info)

    async def _on_error(error):
        errors.append(error)

    client = OopzWSClient(
        _make_config(),
        on_open=_on_open,
        on_close=_on_close,
        on_error=_on_error,
    )
    client.transport = _FakeTransport()

    with caplog.at_level(logging.ERROR, logger="oopz_sdk.client.ws"):
        _run(client.start())

    assert client.transport.connect_calls == 1
    assert client.transport.close_calls >= 1
    assert errors == []
    assert len(close_infos) == 1
    assert close_infos[0].code == 4004
    assert close_infos[0].reason == "stopped"
    assert not any("WebSocket 运行异常" in record.message for record in caplog.records)


def test_oopz_sdk_ws_client_close_info_uses_real_close_reason_and_code():
    close_infos = []

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
            raise WebSocketClosedError(code=4010, reason="remote shutdown")

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.close_calls += 1
            self.closed = True

    async def _on_close(close_info):
        close_infos.append(close_info)
        client._running = False

    config = _make_config()
    config.heartbeat.reconnect_interval = 0.01
    config.heartbeat.max_reconnect_interval = 0.01
    client = OopzWSClient(config, on_close=_on_close)
    client.transport = _FakeTransport()

    _run(client.start())

    assert len(close_infos) == 1
    assert close_infos[0].code == 4010
    assert close_infos[0].reason == "remote shutdown"
    assert close_infos[0].reconnecting is True


def test_oopz_sdk_ws_client_reports_receive_failure_while_running():
    errors = []
    close_infos = []

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
            raise ConnectionError("socket closed")

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.close_calls += 1
            self.closed = True

    async def _on_error(error):
        errors.append(error)

    async def _on_close(close_info):
        close_infos.append(close_info)
        client._running = False

    config = _make_config()
    config.heartbeat.reconnect_interval = 0.01
    config.heartbeat.max_reconnect_interval = 0.01
    client = OopzWSClient(config, on_error=_on_error, on_close=_on_close)
    client.transport = _FakeTransport()

    _run(client.start())

    assert client.transport.connect_calls >= 1
    assert client.transport.close_calls >= 1
    assert len(errors) == 1
    assert isinstance(errors[0], ConnectionError)
    assert str(errors[0]) == "socket closed"
    assert len(close_infos) == 1
    assert close_infos[0].reason == "connection closed"
    assert close_infos[0].reconnecting is True


def test_oopz_sdk_bot_close_handler_receives_payload_from_close_info():
    seen = {}

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
            await asyncio.sleep(0.01)
            raise WebSocketClosedError(code=4999, reason="remote bye")

        async def send_json(self, data):
            self.sent.append(data)

        async def close(self):
            self.close_calls += 1
            self.closed = True

    bot = OopzBot(_make_config())

    @bot.on_close
    async def _on_close(ctx, event):
        seen["ctx"] = ctx
        seen["event"] = event

    async def _on_open():
        asyncio.create_task(bot.ws.stop())

    bot.ws.on_open = _on_open
    bot.ws.transport = _FakeTransport()

    _run(bot.ws.start())

    assert bot.ws.transport.connect_calls == 1
    assert isinstance(seen["ctx"], EventContext)
    assert seen["event"]["code"] == 4999
    assert seen["event"]["reason"] == "stopped"
    assert seen["event"]["error"] is not None
    assert seen["event"]["reconnecting"] is False


def test_oopz_sdk_bot_start_closes_rest_when_ws_start_fails():
    bot = OopzBot(_make_config())
    calls = []

    class _Rest:
        async def start(self):
            calls.append("rest.start")

        async def close(self):
            calls.append("rest.close")

    class _Ws:
        async def start(self):
            calls.append("ws.start")
            raise RuntimeError("ws boom")

    bot.rest = _Rest()
    bot.ws = _Ws()

    with pytest.raises(RuntimeError, match="ws boom"):
        _run(bot.start())

    assert calls == ["rest.start", "ws.start", "rest.close"]


def test_oopz_sdk_bot_start_closes_rest_when_ws_start_is_cancelled():
    bot = OopzBot(_make_config())
    calls = []

    class _Rest:
        async def start(self):
            calls.append("rest.start")

        async def close(self):
            calls.append("rest.close")

    class _Ws:
        async def start(self):
            calls.append("ws.start")
            raise asyncio.CancelledError()

    bot.rest = _Rest()
    bot.ws = _Ws()

    with pytest.raises(asyncio.CancelledError):
        _run(bot.start())

    assert calls == ["rest.start", "ws.start", "rest.close"]


def test_oopz_sdk_bot_start_keeps_original_error_when_rest_close_also_fails(caplog):
    bot = OopzBot(_make_config())
    calls = []

    class _Rest:
        async def start(self):
            calls.append("rest.start")

        async def close(self):
            calls.append("rest.close")
            raise RuntimeError("rest close boom")

    class _Ws:
        async def start(self):
            calls.append("ws.start")
            raise RuntimeError("ws boom")

    bot.rest = _Rest()
    bot.ws = _Ws()

    with caplog.at_level(logging.ERROR, logger="oopz_sdk.client.bot"):
        with pytest.raises(RuntimeError, match="ws boom"):
            _run(bot.start())

    assert calls == ["rest.start", "ws.start", "rest.close"]
    assert any(
        "Failed to close REST client after start failure" in record.message
        for record in caplog.records
    )


def test_oopz_sdk_bot_stop_closes_rest_when_ws_stop_fails():
    bot = OopzBot(_make_config())
    calls = []

    class _Rest:
        async def close(self):
            calls.append("rest.close")

    class _Ws:
        async def stop(self):
            calls.append("ws.stop")
            raise RuntimeError("ws stop boom")

    bot.rest = _Rest()
    bot.ws = _Ws()

    with pytest.raises(RuntimeError, match="ws stop boom"):
        _run(bot.stop())

    assert calls == ["ws.stop", "rest.close"]


def test_oopz_sdk_bot_stop_closes_rest_when_ws_stop_is_cancelled():
    bot = OopzBot(_make_config())
    calls = []

    class _Rest:
        async def close(self):
            calls.append("rest.close")

    class _Ws:
        async def stop(self):
            calls.append("ws.stop")
            raise asyncio.CancelledError()

    bot.rest = _Rest()
    bot.ws = _Ws()

    with pytest.raises(asyncio.CancelledError):
        _run(bot.stop())

    assert calls == ["ws.stop", "rest.close"]


def test_oopz_sdk_bot_stop_keeps_original_error_when_rest_close_also_fails(caplog):
    bot = OopzBot(_make_config())
    calls = []

    class _Rest:
        async def close(self):
            calls.append("rest.close")
            raise RuntimeError("rest close boom")

    class _Ws:
        async def stop(self):
            calls.append("ws.stop")
            raise RuntimeError("ws stop boom")

    bot.rest = _Rest()
    bot.ws = _Ws()

    with caplog.at_level(logging.ERROR, logger="oopz_sdk.client.bot"):
        with pytest.raises(RuntimeError, match="ws stop boom"):
            _run(bot.stop())

    assert calls == ["ws.stop", "rest.close"]
    assert any(
        "Failed to close REST client after stop failure" in record.message
        for record in caplog.records
    )


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


def test_oopz_sdk_http_transport_request_json_with_retry_requires_positive_attempts():
    config = _make_config(rate_limit_interval=0)
    transport = HttpTransport(config, signer=object())

    with pytest.raises(ValueError, match="max_attempts must be at least 1"):
        _run(transport.request_data_with_retry("GET", "/test", max_attempts=0))


def test_oopz_sdk_event_context_has_single_send_definition():
    source = Path("oopz_sdk/events/context.py").read_text(encoding="utf-8")

    assert source.count("async def send(") == 1


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
