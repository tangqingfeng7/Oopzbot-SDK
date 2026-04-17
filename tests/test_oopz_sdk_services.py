import asyncio

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from oopz_sdk import OopzClient, OopzSender, models
from oopz_sdk.config import OopzConfig
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.events.context import EventContext
from oopz_sdk.events.dispatcher import EventDispatcher
from oopz_sdk.events.registry import EventRegistry
from oopz_sdk.models.event import MessageEvent
from oopz_sdk.models.segment import Image as ImageSegment
from oopz_sdk.services.area import AreaService
from oopz_sdk.services.channel import Channel
from oopz_sdk.services.media import Media
from oopz_sdk.services.member import Member
from oopz_sdk.services.message import Message
from oopz_sdk.services.privatemessage import PrivateMessage


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8") if text else b"{}"

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []
        self.sock = type("Sock", (), {"connected": True})()

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def close(self) -> None:
        self.sock.connected = False


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


def test_oopz_sdk_config_requires_private_key():
    with pytest.raises(ValueError):
        OopzConfig(
            device_id="device",
            person_uid="person",
            jwt_token="jwt",
            private_key=None,
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

    result = service.send_message("hello", auto_recall=False)

    assert isinstance(result, models.MessageSendResult)
    assert result.message_id == "msg-1"
    assert result.area == "area"
    assert result.channel == "channel"


def test_oopz_sdk_send_message_accepts_legacy_text_keyword(monkeypatch):
    service = Message(_make_config())
    captured = {}
    monkeypatch.setattr(
        service,
        "_post",
        lambda url_path, body: captured.update({"url_path": url_path, "body": body}) or _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "msg-legacy-text"}},
        ),
    )

    result = service.send_message(text="hello", auto_recall=False)

    assert result.message_id == "msg-legacy-text"
    assert captured["url_path"] == "/im/session/v1/sendGimMessage"
    assert captured["body"]["text"] == "hello"


def test_oopz_sdk_recall_message_returns_operation_result(monkeypatch):
    service = Message(None, _make_config())
    captured = {}
    monkeypatch.setattr(
        service.session,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("session.post should not be used")),
    )
    monkeypatch.setattr(
        service.transport,
        "request",
        lambda method, url_path, body=None, params=None: captured.update(
            {"method": method, "url_path": url_path, "body": body, "params": params}
        ) or _FakeResponse(200, payload={"status": True, "message": "ok"}),
    )

    result = service.recall_message("msg-1")

    assert isinstance(result, models.OperationResult)
    assert result.ok is True
    assert result.message == "ok"
    assert captured["method"] == "POST"
    assert captured["url_path"] == "/im/session/v1/recallGim"
    assert captured["params"]["messageId"] == "msg-1"
    assert captured["params"]["channel"] == "channel"


def test_oopz_sdk_private_message_returns_result_model(monkeypatch):
    service = PrivateMessage(None, _make_config())
    dm_channel = "DM12345678901234567890"
    calls = []
    monkeypatch.setattr(
        service.session,
        "patch",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("session.patch should not be used")),
    )
    monkeypatch.setattr(
        service.session,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("session.post should not be used")),
    )
    monkeypatch.setattr(
        service.transport,
        "request",
        lambda method, url_path, body=None, params=None: calls.append(
            {"method": method, "url_path": url_path, "body": body, "params": params}
        ) or (
            _FakeResponse(200, payload={"status": True, "data": {"channel": dm_channel}})
            if method == "PATCH"
            else _FakeResponse(200, payload={"status": True, "data": {"messageId": "dm-1"}})
        ),
    )

    result = service.send_private_message("target-1", "hello")

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

    monkeypatch.setattr(service.session, "put", lambda *args, **kwargs: _UploadResp())

    result = service.upload_file(str(sample), file_type="IMAGE", ext=".bin")

    assert isinstance(result, models.UploadResult)
    assert result.attachment.file_key == "file-key"
    assert result.attachment.url == "https://cdn.example.com/file-key"


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
    monkeypatch.setattr("oopz_sdk.services.area.time.sleep", lambda *_: None)

    result = service.get_area_members()

    assert calls["count"] == 3
    assert result["members"][0]["uid"] == "u1"


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

    result = service.get_joined_areas(as_model=True)

    assert isinstance(result, models.JoinedAreasResult)
    assert result.areas[0].id == "area-1"
    assert result.areas[0].name == "测试域"


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

    result = service.get_area_channels(as_model=True)

    assert isinstance(result, models.ChannelGroupsResult)
    assert result.groups[0].channels[0].id == "channel-1"
    assert result.groups[0].channels[0].name == "大厅"


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

    result = service.get_person_detail("u1", as_model=True)

    assert isinstance(result, models.PersonDetail)
    assert result.uid == "u1"
    assert result.name == "Alice"


def test_oopz_sdk_event_context_send_allows_explicit_channel_without_message():
    class _Messages:
        def __init__(self):
            self.calls = []

        def send_message(self, **kwargs):
            self.calls.append(kwargs)
            return kwargs

    class _Bot:
        def __init__(self):
            self.message = _Messages()

    bot = _Bot()
    ctx = EventContext(bot=bot, config=_make_config(), message=_Messages(message_id="msg-1", content="hello", area="area-1",  channel="channel-1"))

    result = asyncio.run(ctx.send("hello", area="area-1", channel="channel-1"))

    assert result == {"text": "hello", "area": "area-1", "channel": "channel-1"}
    assert bot.message.calls == [{"text": "hello", "area": "area-1", "channel": "channel-1"}]


def test_oopz_sdk_local_image_segment_preserves_upload_error(monkeypatch, tmp_path):
    service = Message(_make_config())
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
    monkeypatch.setattr(
        service.transport,
        "put",
        lambda *args, **kwargs: (_ for _ in ()).throw(OopzApiError("upload failed")),
    )

    with pytest.raises(OopzApiError, match="upload failed"):
        service.send_message(ImageSegment.from_file(str(sample)), auto_recall=False)


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


def test_oopz_sdk_event_context_reply_uses_message_id_from_legacy_id():
    class _Messages:
        def __init__(self):
            self.calls = []

        def send_message(self, **kwargs):
            self.calls.append(kwargs)
            return kwargs

    class _Bot:
        def __init__(self):
            self.messages = _Messages()

    bot = _Bot()
    message = models.Message.from_dict(
        {
            "id": "msg-legacy",
            "area": "area-1",
            "channel": "channel-1",
            "content": "hello",
        }
    )
    ctx = EventContext(bot=bot, config=_make_config(), message=message)

    result = asyncio.run(ctx.reply("pong"))

    assert result["referenceMessageId"] == "msg-legacy"
    assert bot.messages.calls[0]["referenceMessageId"] == "msg-legacy"


def test_oopz_sdk_sender_send_message_v2_builds_wrapped_payload(monkeypatch):
    sender = OopzSender(_make_config())
    captured = {}

    monkeypatch.setattr(
        sender,
        "_post",
        lambda url_path, body: captured.update({"url_path": url_path, "body": body}) or _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "msg-v2"}},
        ),
    )

    result = sender.send_message_v2("hello", mentionList=["user-1"], auto_recall=False)

    assert captured["url_path"] == "/im/session/v2/sendGimMessage"
    assert captured["body"]["message"]["channel"] == "channel"
    assert captured["body"]["message"]["mentionList"] == [
        {"person": "user-1", "isBot": False, "botType": "", "offset": -1}
    ]
    assert "(met)user-1(met)" in captured["body"]["message"]["content"]
    assert result.message_id == "msg-v2"


def test_oopz_sdk_sender_list_sessions_returns_dict_list(monkeypatch):
    sender = OopzSender(_make_config())
    captured = {}

    monkeypatch.setattr(
        sender,
        "_post",
        lambda url_path, body: captured.update({"url_path": url_path, "body": body}) or _FakeResponse(
            200,
            payload={"status": True, "data": [{"channel": "DM123", "lastTime": "123456"}]},
        ),
    )

    result = sender.list_sessions(last_time="123456")

    assert captured["url_path"] == "/im/session/v1/sessions"
    assert captured["body"] == {"lastTime": "123456"}
    assert result[0]["channel"] == "DM123"


def test_oopz_sdk_sender_get_area_channels_returns_compat_models(monkeypatch):
    sender = OopzSender(_make_config())
    monkeypatch.setattr(
        sender.channels,
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

    result = sender.get_area_channels()

    assert isinstance(result, models.ChannelGroupsResult)
    assert result.groups[0]["id"] == "group-1"
    assert result.groups[0]["channels"][0]["id"] == "channel-1"


def test_oopz_sdk_client_emits_typed_chat_event_and_auth_lifecycle():
    lifecycle_states = []
    chat_events = []
    client = OopzClient(
        _make_config(),
        on_chat_message=chat_events.append,
        on_lifecycle_event=lambda event: lifecycle_states.append(event.state),
    )

    ws = _FakeWebSocket()
    client._running = True
    client._on_open(ws)
    client._on_message(
        ws,
        '{"event":253,"body":"{\\"status\\": true, \\"code\\": 0}"}',
    )
    client._on_message(
        ws,
        '{"event":9,"body":"{\\"data\\": {\\"messageId\\": \\"msg-1\\", \\"person\\": \\"other\\", \\"channel\\": \\"channel-1\\", \\"area\\": \\"area-1\\", \\"content\\": \\"hello\\"}}"}',
    )
    client.stop()

    assert "connected" in lifecycle_states
    assert "auth_sent" in lifecycle_states
    assert "auth_ok" in lifecycle_states
    assert len(chat_events) == 1
    assert isinstance(chat_events[0], models.ChatMessageEvent)
    assert chat_events[0].content == "hello"


def test_oopz_sdk_version_matches_package_version():
    from oopz_sdk import __version__

    assert __version__ == "0.4.3"
