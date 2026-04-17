import asyncio

from oopz_sdk import models
from oopz_sdk.config import OopzConfig
from oopz_sdk.events.context import EventContext
from oopz_sdk.events.dispatcher import EventDispatcher
from oopz_sdk.events.registry import EventRegistry
from oopz_sdk.models.event import MessageEvent
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


def _make_config(**overrides) -> OopzConfig:
    config = OopzConfig(
        device_id="device",
        person_uid="person",
        jwt_token="jwt",
        private_key=None,
        default_area="area",
        default_channel="channel",
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


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


def test_oopz_sdk_recall_message_returns_operation_result(monkeypatch):
    service = Message(None, _make_config())
    monkeypatch.setattr(
        service.session,
        "post",
        lambda *args, **kwargs: _FakeResponse(200, payload={"status": True, "message": "ok"}),
    )

    result = service.recall_message("msg-1")

    assert isinstance(result, models.OperationResult)
    assert result.ok is True
    assert result.message == "ok"


def test_oopz_sdk_private_message_returns_result_model(monkeypatch):
    service = PrivateMessage(None, _make_config())
    dm_channel = "DM12345678901234567890"
    monkeypatch.setattr(
        service.session,
        "patch",
        lambda *args, **kwargs: _FakeResponse(200, payload={"status": True, "data": {"channel": dm_channel}}),
    )
    monkeypatch.setattr(
        service.session,
        "post",
        lambda *args, **kwargs: _FakeResponse(200, payload={"status": True, "data": {"messageId": "dm-1"}}),
    )

    result = service.send_private_message("target-1", "hello")

    assert isinstance(result, models.MessageSendResult)
    assert result.channel == dm_channel
    assert result.message_id == "dm-1"
    assert result.target == "target-1"


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
            self.messages = _Messages()

    bot = _Bot()
    ctx = EventContext(bot=bot, config=_make_config())

    result = asyncio.run(ctx.send("hello", area="area-1", channel="channel-1"))

    assert result == {"text": "hello", "area": "area-1", "channel": "channel-1"}
    assert bot.messages.calls == [{"text": "hello", "area": "area-1", "channel": "channel-1"}]


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
