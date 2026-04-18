import asyncio
import json
from pathlib import Path

import aiohttp
import oopz_sdk.api as sdk_api_module
import oopz_sdk.client as sdk_client_module
import oopz_sdk.client.rest as rest_client_module
import oopz_sdk.config as sdk_config_module
import oopz_sdk.models as sdk_models_module
import oopz_sdk.response as sdk_response_module
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from requests.utils import DEFAULT_ACCEPT_ENCODING

from oopz_sdk import (
    ApiResponse,
    BaseModel,
    ChannelGroupsResult,
    ChannelMessage,
    ChatMessageEvent,
    JsonList,
    JsonObject,
    MessageEvent,
    MessageSendResult,
    OopzApiError,
    OopzApiMixin,
    OopzAuthError,
    OopzClient,
    OopzConfig,
    OopzConnectionError,
    OopzRateLimitError,
    OopzRESTClient,
    PersonDetail,
    PersonInfo,
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
from oopz_sdk.config import OopzConfig as SdkOopzConfig
from oopz_sdk.events.context import EventContext
from oopz_sdk.events.dispatcher import EventDispatcher
from oopz_sdk.events.registry import EventRegistry
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


def _run(awaitable):
    return asyncio.run(awaitable)


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
    sender = OopzRESTClient(_make_config())
    state = {"closed": False}

    async def _close() -> None:
        state["closed"] = True

    monkeypatch.setattr(sender.transport, "close", _close)

    async def _main():
        async with sender as managed_sender:
            assert managed_sender is sender

    _run(_main())

    assert state["closed"] is True


def test_send_message_returns_result_model(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "msg-1"}},
        ),
    )

    result = _run(sender.send_message("hello", auto_recall=False))

    assert isinstance(result, MessageSendResult)
    assert result.message_id == "msg-1"
    assert result.area == "area"
    assert result.channel == "channel"


def test_send_message_v2_builds_wrapped_payload(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())
    captured = {}

    def _fake_post(url_path: str, body: dict):
        captured["url_path"] = url_path
        captured["body"] = body
        return _FakeResponse(200, payload={"status": True, "data": {"messageId": "msg-v2"}})

    monkeypatch.setattr(sender, "_post", _fake_post)

    result = _run(sender.send_message_v2("hello", mentionList=["user-1"], auto_recall=False))

    assert captured["url_path"] == "/im/session/v2/sendGimMessage"
    assert captured["body"]["message"]["channel"] == "channel"
    assert captured["body"]["message"]["mentionList"] == [
        {"person": "user-1", "isBot": False, "botType": "", "offset": -1}
    ]
    assert "(met)user-1(met)" in captured["body"]["message"]["content"]
    assert result.message_id == "msg-v2"


def test_list_sessions_uses_shared_response_helpers(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())
    calls: list[tuple[str, object, str]] = []

    monkeypatch.setattr(
        sender,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": [{"channel": "DM123"}]},
        ),
    )

    def _fake_ensure_success_payload(response, default_message: str):
        calls.append(("ensure", response, default_message))
        return {"data": [{"channel": "DM123"}]}

    def _fake_require_list_data(payload, default_message: str):
        calls.append(("list", payload, default_message))
        return [{"channel": "DM123"}]

    monkeypatch.setattr(
        rest_client_module,
        "ensure_success_payload",
        _fake_ensure_success_payload,
    )
    monkeypatch.setattr(
        rest_client_module,
        "require_list_data",
        _fake_require_list_data,
    )

    result = _run(sender.list_sessions("123456"))

    assert result == [{"channel": "DM123"}]
    assert len(calls) == 2
    assert calls[0][0] == "ensure"
    assert calls[0][2] == "failed to list sessions"
    assert calls[1] == (
        "list",
        {"data": [{"channel": "DM123"}]},
        "failed to list sessions",
    )


def test_rest_client_does_not_keep_response_helper_wrappers() -> None:
    source = Path("oopz_sdk/client/rest.py").read_text(encoding="utf-8")

    assert "def _ensure_success_payload(" not in source
    assert "def _require_dict_data(" not in source
    assert "def _require_list_data(" not in source


def test_get_system_message_list_raises_api_error_when_entry_is_invalid(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "list": [
                        {"id": "sys-1"},
                        "broken-system-message",
                    ]
                },
            },
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_system_message_list())

    assert str(exc_info.value) == "failed to get system messages"
    assert exc_info.value.response["invalid_index"] == 1


def test_send_message_raises_rate_limit_error(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_post",
        lambda url_path, body: _FakeResponse(
            429,
            payload={"message": "too fast"},
            headers={"Retry-After": "3"},
        ),
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(sender.send_message("hello", auto_recall=False))

    assert exc_info.value.retry_after == 3
    assert exc_info.value.status_code == 429


def test_sender_get_translates_request_exception(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

    async def _raise(*args, **kwargs):
        raise aiohttp.ClientConnectionError("network down")

    monkeypatch.setattr(sender.session, "request", _raise)

    with pytest.raises(OopzConnectionError):
        _run(sender._get("/userSubscribeArea/v1/list"))


def test_send_private_message_returns_result_model(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

    async def _open_private_session(target):
        return PrivateSessionResult(channel="DM12345678901234567890")

    monkeypatch.setattr(
        sender.private,
        "open_private_session",
        _open_private_session,
    )
    monkeypatch.setattr(
        sender.private,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"messageId": "dm-1"}},
        ),
    )

    result = _run(sender.send_private_message("target-uid", "hello"))

    assert isinstance(result, MessageSendResult)
    assert result.message_id == "dm-1"
    assert result.target == "target-uid"
    assert result.channel == "DM12345678901234567890"


def test_upload_file_returns_upload_result(monkeypatch, tmp_path) -> None:
    sender = OopzRESTClient(_make_config())
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

    async def _upload_to_signed_url(*args, **kwargs):
        return _UploadResp()

    monkeypatch.setattr(sender.media, "_upload_to_signed_url", _upload_to_signed_url)

    result = _run(sender.upload_file(str(sample), file_type="IMAGE", ext=".bin"))

    assert isinstance(result, UploadResult)
    assert result.attachment.file_key == "file-key"
    assert result.attachment.url == "https://cdn.example.com/file-key"


def test_get_area_channels_returns_model(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

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

    result = _run(sender.get_area_channels())

    assert isinstance(result, ChannelGroupsResult)
    assert result.groups[0]["id"] == "group-1"


def test_get_self_detail_returns_model(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.members,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": True, "data": {"uid": "person", "name": "bot"}},
        ),
    )

    result = _run(sender.get_self_detail())

    assert isinstance(result, SelfDetail)
    assert result.name == "bot"


def test_get_person_detail_returns_model(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.members,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": [{"uid": "u1", "name": "Alice"}]},
        ),
    )

    result = _run(sender.get_person_detail("u1"))

    assert isinstance(result, PersonDetail)
    assert result.uid == "u1"
    assert result.name == "Alice"


def test_get_voice_channel_members_returns_model(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

    async def _get_voice_channel_ids(area):
        return ["voice-1"]

    monkeypatch.setattr(sender.channels, "_get_voice_channel_ids", _get_voice_channel_ids)
    monkeypatch.setattr(
        sender.channels,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={"status": True, "data": {"channelMembers": {"voice-1": [{"uid": "u1", "name": "Alice"}]}}},
        ),
    )

    result = _run(sender.get_voice_channel_members())

    assert isinstance(result, VoiceChannelMembersResult)
    assert result.channels["voice-1"][0]["uid"] == "u1"


def test_get_voice_channel_members_raises_api_error_when_model_payload_contains_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_voice_channel_members(*args, **kwargs):
        return VoiceChannelMembersResult(payload={"error": "voice members unavailable"})

    monkeypatch.setattr(
        sender.channels,
        "get_voice_channel_members",
        _fake_get_voice_channel_members,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_voice_channel_members())

    assert str(exc_info.value) == "voice members unavailable"
    assert exc_info.value.response == {"error": "voice members unavailable"}


def test_get_voice_channel_members_raises_api_error_when_model_payload_contains_failed_status(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_voice_channel_members(*args, **kwargs):
        return VoiceChannelMembersResult(
            payload={"status": False, "message": "voice members rejected"}
        )

    monkeypatch.setattr(
        sender.channels,
        "get_voice_channel_members",
        _fake_get_voice_channel_members,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_voice_channel_members())

    assert str(exc_info.value) == "voice members rejected"
    assert exc_info.value.response == {
        "status": False,
        "message": "voice members rejected",
    }


def test_get_voice_channel_members_raises_api_error_when_model_payload_reports_invalid_member(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _get_voice_channel_ids(area):
        return ["voice-1"]

    monkeypatch.setattr(sender.channels, "_get_voice_channel_ids", _get_voice_channel_ids)
    monkeypatch.setattr(
        sender.channels,
        "_post",
        lambda url_path, body: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {"channelMembers": {"voice-1": [{"uid": "u1"}, "broken-member"]}},
            },
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_voice_channel_members())

    assert str(exc_info.value) == "voice channel members响应格式异常"
    assert exc_info.value.response["list_key"] == "channelMembers.voice-1"
    assert exc_info.value.response["invalid_index"] == 1


def test_get_area_channels_raises_api_error_when_model_payload_contains_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_area_channels(*args, **kwargs):
        return sdk_models_module.ChannelGroupsResult(payload={"error": "area channels unavailable"})

    monkeypatch.setattr(
        sender.channels,
        "get_area_channels",
        _fake_get_area_channels,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_area_channels())

    assert str(exc_info.value) == "area channels unavailable"
    assert exc_info.value.response == {"error": "area channels unavailable"}


def test_get_area_channels_raises_api_error_when_model_payload_reports_invalid_group(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.channels,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": True, "data": [{"id": "group-1"}, "broken-group"]},
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_area_channels())

    assert str(exc_info.value) == "channel groups响应格式异常"
    assert exc_info.value.response["invalid_index"] == 1


def test_get_area_channels_raises_api_error_when_model_payload_reports_invalid_channel(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

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
                        "channels": [{"id": "channel-1"}, "broken-channel"],
                    }
                ],
            },
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_area_channels())

    assert str(exc_info.value) == "channel groups响应格式异常"
    assert exc_info.value.response["list_key"] == "channels"
    assert exc_info.value.response["invalid_index"] == 1


def test_get_area_channels_raises_api_error_when_model_payload_reports_falsey_data(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.channels,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": True, "data": ""},
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_area_channels())

    assert str(exc_info.value) == "channel groups响应格式异常"
    assert exc_info.value.response == {"error": "channel groups响应格式异常"}


def test_get_channel_setting_info_raises_api_error_when_model_payload_contains_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return sdk_models_module.ChannelSetting(
            channel="channel-1",
            payload={"error": "channel setting unavailable"},
        )

    monkeypatch.setattr(
        sender.channels,
        "get_channel_setting_info",
        _fake_get_channel_setting_info,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_channel_setting_info("channel-1"))

    assert str(exc_info.value) == "channel setting unavailable"
    assert exc_info.value.response == {"error": "channel setting unavailable"}


def test_get_channel_setting_info_raises_api_error_when_channel_missing() -> None:
    sender = OopzRESTClient(_make_config())

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_channel_setting_info(""))

    assert str(exc_info.value) == "缺少 channel"
    assert exc_info.value.response == {"error": "缺少 channel"}


def test_get_channel_setting_info_raises_api_error_when_model_payload_reports_malformed_roles(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.channels,
        "_get",
        lambda url_path, params=None: _FakeResponse(
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

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_channel_setting_info("channel-1"))

    assert str(exc_info.value) == "频道设置响应格式异常"
    assert exc_info.value.response == {"error": "频道设置响应格式异常"}


def test_get_channel_setting_info_raises_runtime_error_when_service_breaks_model_contract(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return {"error": "旧式字典返回"}

    monkeypatch.setattr(
        sender.channels,
        "get_channel_setting_info",
        _fake_get_channel_setting_info,
    )

    with pytest.raises(RuntimeError, match="模型接口返回了字典"):
        _run(sender.get_channel_setting_info("channel-1"))


def test_get_area_blocks_raises_api_error_when_model_payload_contains_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_area_blocks(*args, **kwargs):
        return sdk_models_module.AreaBlocksResult(payload={"error": "area blocks unavailable"})

    monkeypatch.setattr(
        sender.moderation,
        "get_area_blocks",
        _fake_get_area_blocks,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_area_blocks())

    assert str(exc_info.value) == "area blocks unavailable"
    assert exc_info.value.response == {"error": "area blocks unavailable"}


def test_get_area_blocks_raises_api_error_when_model_payload_reports_invalid_block(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.moderation,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": True, "data": {"blocks": [{"uid": "u1"}, "broken-block"]}},
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_area_blocks())

    assert str(exc_info.value) == "area blocks响应格式异常"
    assert exc_info.value.response["invalid_index"] == 1


def test_get_area_info_raises_api_error_when_model_payload_contains_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_area_info(*args, **kwargs):
        return sdk_models_module.Area(payload={"error": "area info unavailable"})

    monkeypatch.setattr(
        sender.areas,
        "get_area_info",
        _fake_get_area_info,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_area_info())

    assert str(exc_info.value) == "area info unavailable"
    assert exc_info.value.response == {"error": "area info unavailable"}


def test_get_area_info_preserves_status_code_when_model_http_error_occurs(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.areas,
        "_get",
        lambda url_path, params=None: _FakeResponse(503, text="gateway error"),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_area_info("area-1"))

    assert str(exc_info.value) == "HTTP 503"
    assert exc_info.value.status_code == 503
    assert exc_info.value.response == {"error": "HTTP 503"}


def test_get_joined_areas_raises_api_error_when_model_payload_contains_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_joined_areas(*args, **kwargs):
        return sdk_models_module.JoinedAreasResult(payload={"error": "joined areas unavailable"})

    monkeypatch.setattr(
        sender.areas,
        "get_joined_areas",
        _fake_get_joined_areas,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_joined_areas())

    assert str(exc_info.value) == "joined areas unavailable"
    assert exc_info.value.response == {"error": "joined areas unavailable"}


def test_get_joined_areas_raises_api_error_when_model_payload_reports_invalid_area(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.areas,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={"status": True, "data": [{"id": "area-1"}, "broken-area"]},
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_joined_areas())

    assert str(exc_info.value) == "joined areas响应格式异常"
    assert exc_info.value.response["invalid_index"] == 1


def test_populate_names_returns_failed_operation_result_when_service_reports_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_populate_names(*args, **kwargs):
        return {"error": "joined areas unavailable"}

    monkeypatch.setattr(
        sender.areas,
        "populate_names",
        _fake_populate_names,
    )

    result = _run(sender.populate_names())

    assert result.ok is False
    assert result.message == "joined areas unavailable"
    assert result.payload == {"error": "joined areas unavailable"}


def test_get_person_infos_batch_raises_api_error_when_service_reports_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_person_infos_batch(*args, **kwargs):
        return {"error": "批量获取用户信息失败: HTTP 503"}

    monkeypatch.setattr(
        sender.members,
        "get_person_infos_batch",
        _fake_get_person_infos_batch,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_person_infos_batch(["u1"]))

    assert str(exc_info.value) == "批量获取用户信息失败: HTTP 503"
    assert exc_info.value.response == {"error": "批量获取用户信息失败: HTTP 503"}


def test_get_person_infos_batch_raises_api_error_when_service_returns_invalid_entry(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_person_infos_batch(*args, **kwargs):
        return {"u1": {"uid": "u1"}, "u2": "broken-person"}

    monkeypatch.setattr(
        sender.members,
        "get_person_infos_batch",
        _fake_get_person_infos_batch,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_person_infos_batch(["u1", "u2"]))

    assert str(exc_info.value) == "failed to get person infos batch"
    assert exc_info.value.response["invalid_uid"] == "u2"


def test_get_person_infos_batch_raises_api_error_with_partial_result_when_service_reports_later_batch_failure(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_person_infos_batch(*args, **kwargs):
        return {
            "error": "批量获取用户信息失败: HTTP 503",
            "partial_results": {"u1": {"uid": "u1", "name": "Alice"}},
        }

    monkeypatch.setattr(
        sender.members,
        "get_person_infos_batch",
        _fake_get_person_infos_batch,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_person_infos_batch(["u1", "u2"]))

    assert str(exc_info.value) == "批量获取用户信息失败: HTTP 503"
    assert exc_info.value.response["partial_results"] == {
        "u1": {"uid": "u1", "name": "Alice"}
    }


def test_get_person_infos_batch_raises_rate_limit_error_with_partial_result_when_service_reports_later_batch_rate_limit(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_person_infos_batch(*args, **kwargs):
        return {
            "error": "批量获取用户信息失败: HTTP 429",
            "status_code": 429,
            "retry_after": 7,
            "partial_results": {"u1": {"uid": "u1", "name": "Alice"}},
        }

    monkeypatch.setattr(
        sender.members,
        "get_person_infos_batch",
        _fake_get_person_infos_batch,
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(sender.get_person_infos_batch(["u1", "u2"]))

    assert str(exc_info.value) == "批量获取用户信息失败: HTTP 429"
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 7
    assert exc_info.value.response["partial_results"] == {
        "u1": {"uid": "u1", "name": "Alice"}
    }


def test_get_assignable_roles_raises_api_error_when_service_reports_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_assignable_roles(*args, **kwargs):
        return {"error": "role list unavailable"}

    monkeypatch.setattr(
        sender.members,
        "get_assignable_roles",
        _fake_get_assignable_roles,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_assignable_roles("target-1"))

    assert str(exc_info.value) == "role list unavailable"
    assert exc_info.value.response == {"error": "role list unavailable"}


def test_get_assignable_roles_raises_rate_limit_error_on_http_429(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.members,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            429,
            payload={"message": "too fast"},
            headers={"Retry-After": "7"},
        ),
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(sender.get_assignable_roles("target-1"))

    assert str(exc_info.value) == "HTTP 429"
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 7
    assert exc_info.value.response == {
        "error": "HTTP 429",
        "status_code": 429,
        "retry_after": 7,
    }


def test_get_assignable_roles_raises_api_error_when_service_returns_invalid_entry(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_assignable_roles(*args, **kwargs):
        return [{"roleID": 1}, "broken-role"]

    monkeypatch.setattr(
        sender.members,
        "get_assignable_roles",
        _fake_get_assignable_roles,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_assignable_roles("target-1"))

    assert str(exc_info.value) == "failed to get assignable roles"
    assert exc_info.value.response["invalid_index"] == 1


def test_search_area_members_raises_api_error_when_service_reports_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_search_area_members(*args, **kwargs):
        return {"error": "search members unavailable"}

    monkeypatch.setattr(
        sender.members,
        "search_area_members",
        _fake_search_area_members,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.search_area_members(keyword="alice"))

    assert str(exc_info.value) == "search members unavailable"
    assert exc_info.value.response == {"error": "search members unavailable"}


def test_search_area_members_raises_rate_limit_error_on_http_429(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.members,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            429,
            payload={"message": "too fast"},
            headers={"Retry-After": "5"},
        ),
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(sender.search_area_members(keyword="alice"))

    assert str(exc_info.value) == "HTTP 429"
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 5
    assert exc_info.value.response == {
        "error": "HTTP 429",
        "status_code": 429,
        "retry_after": 5,
    }


def test_get_person_detail_raises_api_error_when_model_payload_contains_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_person_detail(*args, **kwargs):
        return sdk_models_module.PersonDetail(payload={"error": "person detail unavailable"})

    monkeypatch.setattr(
        sender.members,
        "get_person_detail",
        _fake_get_person_detail,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_person_detail("u1"))

    assert str(exc_info.value) == "person detail unavailable"
    assert exc_info.value.response == {"error": "person detail unavailable"}


def test_get_self_detail_raises_api_error_when_model_payload_contains_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_self_detail(*args, **kwargs):
        return sdk_models_module.SelfDetail(payload={"error": "self detail unavailable"})

    monkeypatch.setattr(
        sender.members,
        "get_self_detail",
        _fake_get_self_detail,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_self_detail())

    assert str(exc_info.value) == "self detail unavailable"
    assert exc_info.value.response == {"error": "self detail unavailable"}


def test_get_self_detail_preserves_status_code_when_model_payload_contains_http_error(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_self_detail(*args, **kwargs):
        return sdk_models_module.SelfDetail(
            payload={"error": "HTTP 503"},
            response=_FakeResponse(503, text="gateway error"),
        )

    monkeypatch.setattr(
        sender.members,
        "get_self_detail",
        _fake_get_self_detail,
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_self_detail())

    assert str(exc_info.value) == "HTTP 503"
    assert exc_info.value.status_code == 503
    assert exc_info.value.response == {"error": "HTTP 503"}


def test_get_self_detail_raises_rate_limit_error_when_model_response_is_429(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    async def _fake_get_self_detail(*args, **kwargs):
        return sdk_models_module.SelfDetail(
            payload={"error": "HTTP 429"},
            response=_FakeResponse(
                429,
                payload={"message": "too fast"},
                headers={"Retry-After": "7"},
            ),
        )

    monkeypatch.setattr(
        sender.members,
        "get_self_detail",
        _fake_get_self_detail,
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(sender.get_self_detail())

    assert str(exc_info.value) == "HTTP 429"
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 7
    assert exc_info.value.response == {"error": "HTTP 429"}


def test_get_channel_messages_returns_models(monkeypatch) -> None:
    sender = OopzRESTClient(_make_config())

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

    result = _run(sender.get_channel_messages())

    assert len(result) == 1
    assert isinstance(result[0], ChannelMessage)
    assert result[0].message_id == "msg-1"
    assert result[0].content == "hello"


def test_get_private_messages_raises_api_error_when_message_item_is_invalid(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "messages": [
                        {"messageId": "msg-1", "content": "hello"},
                        "broken-private-message",
                    ]
                },
            },
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_private_messages("DM123"))

    assert str(exc_info.value) == "failed to get private messages"
    assert exc_info.value.response["invalid_index"] == 1


def test_get_channel_messages_raises_api_error_with_debug_payload_on_http_failure(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_get",
        lambda url_path, params=None: _FakeResponse(503, text="upstream timeout"),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_channel_messages())

    assert exc_info.value.status_code == 503
    assert exc_info.value.response == {
        "error": "HTTP 503",
        "debug_reason": "get_channel_messages_http_error",
        "area": "area",
        "channel": "channel",
        "size": 50,
        "response_preview": "upstream timeout",
    }


def test_get_channel_messages_raises_rate_limit_error_on_http_429(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            429,
            payload={"message": "too fast"},
            headers={"Retry-After": "9"},
        ),
    )

    with pytest.raises(OopzRateLimitError) as exc_info:
        _run(sender.get_channel_messages())

    assert str(exc_info.value) == "HTTP 429"
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 9
    assert exc_info.value.response == {
        "error": "HTTP 429",
        "debug_reason": "get_channel_messages_http_error",
        "area": "area",
        "channel": "channel",
        "size": 50,
        "response_preview": "",
    }


def test_get_channel_messages_raises_api_error_when_message_item_is_invalid(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_get",
        lambda url_path, params=None: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "messages": [
                        {"messageId": "msg-1", "content": "hello"},
                        "broken-message-item",
                    ]
                },
            },
        ),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_channel_messages())

    assert str(exc_info.value) == "channel messages响应格式异常"
    assert exc_info.value.response["debug_reason"] == "get_channel_messages_malformed_message_item"


def test_get_channel_messages_raises_api_error_when_root_payload_is_invalid(
    monkeypatch,
) -> None:
    sender = OopzRESTClient(_make_config())

    monkeypatch.setattr(
        sender.messages,
        "_get",
        lambda url_path, params=None: _FakeResponse(200, payload=["bad-root"]),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(sender.get_channel_messages())

    assert str(exc_info.value) == "channel messages响应格式异常"
    assert exc_info.value.response == {
        "error": "channel messages响应格式异常",
        "debug_reason": "get_channel_messages_malformed_root",
        "area": "area",
        "channel": "channel",
        "size": 50,
        "payload": ["bad-root"],
    }


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


def test_public_modules_expose_sdk_symbols() -> None:
    assert sdk_config_module.OopzConfig is SdkOopzConfig
    assert sdk_client_module.OopzClient is SdkOopzClient
    assert not hasattr(sdk_client_module, "OopzSender")
    assert SdkSigner is sdk_client_module.Signer if hasattr(sdk_client_module, "Signer") else SdkSigner
    assert sdk_models_module.ChannelMessage is SdkChannelMessage
    assert sdk_api_module.OopzApiMixin is OopzApiMixin
    assert sdk_response_module.is_success_payload({"status": True}) is True


def test_top_level_sdk_exports_legacy_surface() -> None:
    assert BaseModel.__name__ == "BaseModel"
    assert ApiResponse.__name__ == "ApiResponse"
    assert PersonInfo is sdk_models_module.Member
    assert JsonObject == dict[str, object]
    assert JsonList == list[object]
    assert MessageEvent.__name__ == "MessageEvent"


def test_default_accept_encoding_matches_runtime_decoder_support() -> None:
    assert sdk_config_module.DEFAULT_HEADERS["Accept-Encoding"] == DEFAULT_ACCEPT_ENCODING


def test_dispatcher_passes_error_event_before_context() -> None:
    registry = EventRegistry()
    dispatcher = EventDispatcher(registry)
    config = _make_config()
    received = []

    @registry.on("error")
    def handle_error(event, ctx) -> None:
        received.append((event, ctx))

    error = ValueError("boom")
    context = EventContext(bot=None, config=config)

    dispatcher.dispatch_sync("error", error, context)

    assert received == [(error, context)]


def test_dispatcher_falls_back_for_single_argument_handlers() -> None:
    registry = EventRegistry()
    dispatcher = EventDispatcher(registry)
    config = _make_config()
    received = []

    @registry.on("error")
    def handle_error(event) -> None:
        received.append(event)

    error = ValueError("boom")
    context = EventContext(bot=None, config=config)

    dispatcher.dispatch_sync("error", error, context)

    assert received == [error]


def test_config_headers_merge_defaults_with_custom_values() -> None:
    config = _make_config()
    config.headers = {"X-Test": "1", "User-Agent": "custom-agent"}

    headers = config.get_headers()

    assert headers["X-Test"] == "1"
    assert headers["User-Agent"] == "custom-agent"
    assert headers["Origin"] == sdk_config_module.DEFAULT_HEADERS["Origin"]
