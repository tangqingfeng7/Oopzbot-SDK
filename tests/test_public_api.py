import json

import oopz.api as legacy_api_module
import oopz.client as legacy_client_module
import oopz.config as legacy_config_module
import oopz.models as legacy_models_module
import oopz.response as legacy_response_module
import oopz.sender as legacy_sender_module
import oopz.signer as legacy_signer_module
import oopz.upload as legacy_upload_module
import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import rsa

from oopz import (
    ChannelGroupsResult,
    ChannelMessage,
    ChatMessageEvent,
    MessageSendResult,
    OopzApiError,
    OopzAuthError,
    OopzClient,
    OopzConfig,
    OopzConnectionError,
    OopzRateLimitError,
    OopzSender,
    PersonDetail,
    PrivateSessionResult,
    SelfDetail,
    Signer,
    UploadResult,
    VoiceChannelMembersResult,
    __version__,
)
from oopz_sdk.auth import Signer as SdkSigner
from oopz_sdk.client import OopzClient as SdkOopzClient
from oopz_sdk.client import OopzRESTClient as SdkOopzRESTClient
from oopz_sdk.client import OopzSender as SdkOopzSender
from oopz_sdk.config import OopzConfig as SdkOopzConfig
from oopz_sdk.models import ChannelMessage as SdkChannelMessage
from oopz_sdk.services.media import UploadMixin as SdkUploadMixin


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


def test_version_is_exposed() -> None:
    assert __version__ == "0.4.3"


def test_config_requires_private_key() -> None:
    with pytest.raises(ValueError):
        OopzConfig(
            device_id="device",
            person_uid="person",
            jwt_token="jwt",
            private_key=None,
        )


def test_signer_invalid_private_key_raises_auth_error() -> None:
    config = _make_config(private_key=object())

    with pytest.raises(OopzAuthError):
        Signer(config)


def test_sender_context_manager_closes_session(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    state = {"closed": False}

    def _close() -> None:
        state["closed"] = True

    monkeypatch.setattr(sender.session, "close", _close)

    with sender as managed_sender:
        assert managed_sender is sender

    assert state["closed"] is True


def test_send_message_returns_result_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "msg-1"}},
        ),
    )

    result = sender.send_message("hello", auto_recall=False)

    assert isinstance(result, MessageSendResult)
    assert result.message_id == "msg-1"
    assert result.area == "area"
    assert result.channel == "channel"


def test_send_message_v2_builds_wrapped_payload(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": {"messageId": "msg-v2"}})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.send_message_v2("hello", mentionList=["user-1"], auto_recall=False)

    assert captured["url_path"] == "/im/session/v2/sendGimMessage"
    assert captured["body"]["message"]["channel"] == "channel"
    assert captured["body"]["message"]["mentionList"] == [
        {"person": "user-1", "isBot": False, "botType": "", "offset": -1}
    ]
    assert "(met)user-1(met)" in captured["body"]["message"]["content"]
    assert result.message_id == "msg-v2"


def test_send_message_raises_rate_limit_error(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_post",
        lambda url_path, body: _FakeResponse(
            429,
            payload={"message": "请求过快"},
            headers={"Retry-After": "3"},
        ),
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        sender.send_message("hello", auto_recall=False)

    assert exc_info.value.retry_after == 3
    assert exc_info.value.status_code == 429


def test_sender_get_translates_request_exception(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    def _raise(*args, **kwargs):
        raise requests.RequestException("network down")

    monkeypatch.setattr(sender.session, "request", _raise)

    with pytest.raises(OopzConnectionError):
        sender._get("/userSubscribeArea/v1/list")


def test_send_private_message_returns_result_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender.private,
        "open_private_session",
        lambda target: PrivateSessionResult(channel="DM12345678901234567890"),
    )
    monkeypatch.setattr(
        sender.private,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "dm-1"}},
        ),
    )

    result = sender.send_private_message("target-uid", "hello")

    assert isinstance(result, MessageSendResult)
    assert result.message_id == "dm-1"
    assert result.target == "target-uid"
    assert result.channel == "DM12345678901234567890"


def test_list_sessions_returns_dict_list(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(
            200,
            payload={"status": True, "data": [{"channel": "DM123", "lastTime": "123456"}]},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = sender.list_sessions(last_time="123456")

    assert captured["url_path"] == "/im/session/v1/sessions"
    assert captured["body"] == {"lastTime": "123456"}
    assert result[0]["channel"] == "DM123"


def test_upload_file_returns_upload_result(monkeypatch, tmp_path) -> None:
    sender = OopzSender(_make_config())
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"hello")

    monkeypatch.setattr(
        sender.media,
        "_put",
        lambda url_path, body: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "signedUrl": "https://upload.example.com",
                    "file": "file-key",
                    "url": "https://cdn.example.com/file-key",
                },
            },
        ),
    )

    class _UploadResp:
        status_code = 200
        text = ""

    monkeypatch.setattr(sender.session, "put", lambda *args, **kwargs: _UploadResp())

    result = sender.upload_file(str(sample), file_type="IMAGE", ext=".bin")

    assert isinstance(result, UploadResult)
    assert result.attachment.file_key == "file-key"
    assert result.attachment.url == "https://cdn.example.com/file-key"


def test_get_area_members_returns_stale_cache_on_rate_limit(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    cache_key = ("area", 0, 49)
    sender.areas._area_members_cache[cache_key] = {
        "ts": 10_000_000.0,
        "data": {"members": [{"uid": "u1", "online": 1}]},
    }

    monkeypatch.setattr("oopz_sdk.services.area.time.time", lambda: 10_000_010.0)
    monkeypatch.setattr("oopz_sdk.services.area.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        sender.areas,
        "_get",
        lambda url_path, params=None: _FakeResponse(429, payload={"message": "too fast"}),
    )

    result = sender.get_area_members()

    assert result["stale"] is True
    assert result["rateLimited"] is True
    assert result["members"][0]["uid"] == "u1"


def test_get_area_channels_returns_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender.channels,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": [
                    {
                        "id": "group-1",
                        "name": "group",
                        "channels": [{"id": "channel-1", "name": "hall", "type": "TEXT"}],
                    }
                ],
            },
        ),
    )

    result = sender.get_area_channels()

    assert isinstance(result, ChannelGroupsResult)
    assert result.groups[0]["id"] == "group-1"


def test_copy_channel_returns_operation_result(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(
            200,
            payload={"status": True, "data": {"channel": "channel-copy-1"}},
        )

    monkeypatch.setattr(sender, "_post", _fake_post)
    monkeypatch.setattr(sender.channels, "_extract_channel_id", lambda payload: payload.get("channel") if isinstance(payload, dict) else None)

    result = sender.copy_channel("channel-1", name="copied-channel")

    assert captured["url_path"] == "/area/v1/channel/v1/copy"
    assert captured["body"] == {"area": "area", "channel": "channel-1", "name": "copied-channel"}
    assert result.ok is True
    assert result.payload["channel"] == "channel-copy-1"


def test_get_self_detail_returns_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender.members,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": True, "data": {"uid": "person", "name": "bot"}},
        ),
    )

    result = sender.get_self_detail()

    assert isinstance(result, SelfDetail)
    assert result.name == "bot"


def test_get_person_detail_returns_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender.members,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": [{"uid": "u1", "name": "Alice"}]},
        ),
    )

    result = sender.get_person_detail("u1")

    assert isinstance(result, PersonDetail)
    assert result.uid == "u1"
    assert result.name == "Alice"


def test_get_novice_guide_returns_dict(monkeypatch) -> None:
    sender = OopzSender(_make_config())
    captured = {}

    def _fake_get(url_path: str, params=None):
        captured["url_path"] = url_path
        captured["params"] = params
        return _FakeResponse(200, payload={"status": True, "data": {"finished": False}})

    monkeypatch.setattr(sender, "_get", _fake_get)

    result = sender.get_novice_guide()

    assert captured["url_path"] == "/client/v1/person/v1/noviceGuide"
    assert captured["params"] is None
    assert result == {"finished": False}


def test_get_voice_channel_members_returns_model(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(sender.channels, "_get_voice_channel_ids", lambda area: ["voice-1"])
    monkeypatch.setattr(
        sender.channels,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"channelMembers": {"voice-1": [{"uid": "u1", "name": "Alice"}]}}},
        ),
    )

    result = sender.get_voice_channel_members()

    assert isinstance(result, VoiceChannelMembersResult)
    assert result.channels["voice-1"][0]["uid"] == "u1"


def test_get_channel_messages_returns_models(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "messages": [
                        {
                            "messageId": "msg-1",
                            "content": "hello",
                            "area": "area-1",
                            "channel": "channel-1",
                            "person": "user-1",
                        }
                    ]
                },
            },
        ),
    )

    result = sender.get_channel_messages()

    assert len(result) == 1
    assert isinstance(result[0], ChannelMessage)
    assert result[0].message_id == "msg-1"
    assert result[0].content == "hello"


def test_get_channel_messages_returns_empty_list_on_business_failure(monkeypatch) -> None:
    sender = OopzSender(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": False, "message": "business failed"},
        ),
    )

    assert sender.get_channel_messages() == []


def test_client_emits_typed_chat_event_and_auth_lifecycle() -> None:
    chat_events: list[ChatMessageEvent] = []
    lifecycle_states: list[str] = []
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
        json.dumps(
            {
                "event": 253,
                "body": json.dumps({"status": True, "code": 0}),
            }
        ),
    )
    client._on_message(
        ws,
        json.dumps(
            {
                "event": 9,
                "body": json.dumps(
                    {
                        "data": {
                            "messageId": "msg-1",
                            "person": "other",
                            "channel": "channel-1",
                            "area": "area-1",
                            "content": "hello",
                        }
                    }
                ),
            }
        ),
    )
    client.stop()

    assert "connected" in lifecycle_states
    assert "auth_sent" in lifecycle_states
    assert "auth_ok" in lifecycle_states
    assert len(chat_events) == 1
    assert chat_events[0].content == "hello"
    assert chat_events[0].message_id == "msg-1"


def test_client_emits_auth_failed_and_closes_socket() -> None:
    lifecycle = []
    client = OopzClient(
        _make_config(),
        on_lifecycle_event=lambda event: lifecycle.append((event.state, event.reason)),
    )

    ws = _FakeWebSocket()
    client._on_message(
        ws,
        json.dumps(
            {
                "event": 253,
                "body": json.dumps({"status": False, "code": 401, "message": "token invalid"}),
            }
        ),
    )

    assert ("auth_failed", "token invalid") in lifecycle
    assert ws.sock.connected is False


def test_legacy_modules_reexport_oopz_sdk_symbols() -> None:
    assert legacy_config_module.OopzConfig is SdkOopzConfig
    assert legacy_client_module.OopzClient is SdkOopzClient
    assert legacy_sender_module.OopzSender is SdkOopzSender
    assert legacy_signer_module.Signer is SdkSigner
    assert legacy_upload_module.UploadMixin is SdkUploadMixin
    assert legacy_models_module.ChannelMessage is SdkChannelMessage
    assert hasattr(legacy_api_module.OopzApiMixin, "get_area_members")
    assert legacy_response_module.is_success_payload({"status": True}) is True


def test_sender_is_now_rest_client_alias() -> None:
    assert SdkOopzSender is SdkOopzRESTClient
