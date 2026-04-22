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


def test_oopz_sdk_channel_group_model_rejects_falsey_non_list_channels():
    with pytest.raises(ValueError, match="channel groups响应格式异常"):
        Channel._to_channel_group_model({"id": "group-1", "channels": ""})



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

    assert result == {"error": "频道设置响应格式异常", "channel": "channel-1"}


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

    assert result == {"error": "频道设置响应格式异常", "channel": "channel-1"}


def test_oopz_sdk_get_channel_setting_info_returns_request_payload_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_channel_setting_info("channel-1"))

    assert result == {"error": "HTTP 503", "channel": "channel-1"}


def test_oopz_sdk_get_channel_setting_info_returns_request_payload_on_failed_payload(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "setting rejected"},
        ),
    )

    result = _run(service.get_channel_setting_info("channel-1"))

    assert result == {
        "error": "setting rejected",
        "channel": "channel-1",
        "status": False,
        "message": "setting rejected",
    }


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

    result = _run(service.create_channel(area="area", name="测试频道"))

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

    result = _run(service.create_channel(area="area", name="测试频道", group_id="group-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "创建频道响应格式异常"


def test_oopz_sdk_create_channel_returns_http_error_result(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="upstream timeout"),
    )

    result = _run(service.create_channel(area="area", name="测试频道", group_id="group-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "HTTP 503 | upstream timeout"
    assert result.payload["area"] == "area"
    assert result.payload["group"] == "group-1"
    assert result.payload["name"] == "测试频道"
    assert result.payload["type"] == "TEXT"


def test_oopz_sdk_create_channel_returns_request_payload_on_failed_payload(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "create rejected"},
        ),
    )

    result = _run(service.create_channel(area="area", name="测试频道", group_id="group-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "create rejected"
    assert result.payload["area"] == "area"
    assert result.payload["group"] == "group-1"
    assert result.payload["name"] == "测试频道"
    assert result.payload["type"] == "TEXT"
    assert result.payload["status"] is False
    assert result.payload["message"] == "create rejected"


def test_oopz_sdk_update_channel_returns_setting_error_when_role_fields_are_malformed(
    monkeypatch,
):
    service = Channel(None, _make_config())

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return {"error": "频道设置响应格式异常"}

    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)

    result = _run(service.update_channel(area="area", channel_id="channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "获取频道设置失败: 频道设置响应格式异常"
    assert result.payload == {"area": "area", "channel": "channel-1"}


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

    result = _run(service.update_channel(area="area", channel_id="channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "获取频道设置失败: 频道设置响应格式异常"
    assert result.payload == {"area": "area", "channel": "channel-1"}


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

    result = _run(service.update_channel(area="area", channel_id="channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "更新频道响应格式异常"


def test_oopz_sdk_update_channel_returns_http_error_result(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return models.ChannelSetting(channel="channel-1")

    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="upstream timeout"),
    )

    result = _run(service.update_channel(area="area", channel_id="channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "HTTP 503 | upstream timeout"
    assert result.payload["area"] == "area"
    assert result.payload["channel"] == "channel-1"


def test_oopz_sdk_update_channel_returns_request_payload_on_failed_payload(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_channel_setting_info(*args, **kwargs):
        return models.ChannelSetting(channel="channel-1", area="area")

    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "update rejected"},
        ),
    )

    result = _run(service.update_channel(area="area", channel_id="channel-1"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "update rejected"
    assert result.payload["area"] == "area"
    assert result.payload["channel"] == "channel-1"
    assert result.payload["status"] is False
    assert result.payload["message"] == "update rejected"


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

    result = _run(service.get_voice_channel_members(area="area", as_model=True))

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

    result = _run(service.get_voice_channel_members(area="area", as_model=True))

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

    result = _run(service.get_voice_channel_members(area="area", as_model=True))

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

    result = _run(service.get_voice_channel_members(area="area"))

    assert result == {"error": "HTTP 503", "area": "area", "channels": ["voice-1"]}


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

    result = _run(service.get_voice_channel_members(area="area"))

    assert result == {
        "error": "voice members rejected",
        "area": "area",
        "channels": ["voice-1"],
        "status": False,
        "message": "voice members rejected",
    }


def test_oopz_sdk_voice_channel_members_returns_error_dict_on_malformed_member_entry(monkeypatch):
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

    result = _run(service.get_voice_channel_members(area="area"))

    assert result["error"] == "voice channel members响应格式异常"
    assert result["area"] == "area"
    assert result["channels"] == ["voice-1"]
    assert result["invalid_index"] == 1
    assert result["list_key"] == "channelMembers.voice-1"


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

    result = _run(service.delete_channel("channel-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "删除频道响应格式异常"


def test_oopz_sdk_delete_channel_returns_http_error_result(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_delete",
        lambda *args, **kwargs: _FakeResponse(503, text="upstream timeout"),
    )

    result = _run(service.delete_channel("channel-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "HTTP 503 | upstream timeout"
    assert result.payload == {"channel": "channel-1", "area": "area"}


def test_oopz_sdk_delete_channel_returns_request_payload_on_failed_payload(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_delete",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "delete rejected"},
        ),
    )

    result = _run(service.delete_channel("channel-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "delete rejected"
    assert result.payload["channel"] == "channel-1"
    assert result.payload["area"] == "area"
    assert result.payload["status"] is False
    assert result.payload["message"] == "delete rejected"


def test_oopz_sdk_delete_channel_returns_request_payload_on_request_error(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_delete(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(service, "_delete", _fake_delete)

    result = _run(service.delete_channel("channel-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "network down"
    assert result.payload == {"channel": "channel-1", "area": "area"}


def test_oopz_sdk_delete_channel_returns_request_payload_on_non_json_response(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_delete",
        lambda *args, **kwargs: _FakeResponse(200, payload=None, text="<html>bad gateway</html>"),
    )

    result = _run(service.delete_channel("channel-1", area="area"))

    assert isinstance(result, models.OperationResult)
    assert result.ok is False
    assert result.message == "响应非 JSON: <html>bad gateway</html>"
    assert result.payload == {"channel": "channel-1", "area": "area"}


def test_oopz_sdk_voice_channel_members_returns_error_when_voice_ids_fetch_fails(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_get_voice_channel_ids(*args, **kwargs):
        return {"error": "group list unavailable"}

    monkeypatch.setattr(service, "_get_voice_channel_ids", _fake_get_voice_channel_ids)

    result = _run(service.get_voice_channel_members(area="area"))

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

    result = _run(service.create_restricted_text_channel("target-1", area="area"))

    assert result == {
        "error": "获取频道分组失败: group list unavailable",
        "area": "area",
        "target": "target-1",
    }


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

    assert result == {"error": "获取频道设置失败: setting unavailable", "area": "area-1", "target": "target-1"}
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

    assert result == {"error": "获取频道设置失败: 频道设置响应格式异常", "area": "area-1", "target": "target-1"}
    assert deleted == {"channel": "channel-1", "area": "area-1"}


def test_oopz_sdk_create_restricted_text_channel_returns_request_payload_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())

    async def _fake_pick_channel_group(*args, **kwargs):
        return "group-1"

    monkeypatch.setattr(service, "_pick_channel_group", _fake_pick_channel_group)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.create_restricted_text_channel("target-1", area="area-1", name="登录"))

    assert result == {
        "error": "HTTP 503 | gateway error",
        "area": "area-1",
        "group": "group-1",
        "name": "登录",
        "type": "TEXT",
        "secret": True,
        "target": "target-1",
    }


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
    service = Channel(None, _make_config(default_area="area-default"))

    async def _fake_get_channel_setting_info(*args, **kwargs):
        raise AssertionError("不应在缺少 area 时继续获取频道设置")

    monkeypatch.setattr(service, "get_channel_setting_info", _fake_get_channel_setting_info)

    with pytest.raises(ValueError, match="缺少 area"):
        _run(service.update_channel(channel_id="channel-1"))


def test_oopz_sdk_delete_channel_requires_area_before_request(monkeypatch):
    service = Channel(None, _make_config(default_area="area-default"))

    async def _fake_delete(*args, **kwargs):
        raise AssertionError("不应在缺少 area 时继续删除频道")

    monkeypatch.setattr(service, "_delete", _fake_delete)

    with pytest.raises(ValueError, match="缺少 area"):
        _run(service.delete_channel("channel-1"))


def test_oopz_sdk_enter_channel_returns_request_payload_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.enter_channel(channel="channel-1", area="area"))

    assert result == {
        "error": "HTTP 503",
        "type": "TEXT",
        "area": "area",
        "channel": "channel-1",
    }


def test_oopz_sdk_enter_channel_returns_request_payload_on_failed_payload(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "enter rejected"},
        ),
    )

    result = _run(service.enter_channel(channel="channel-1", area="area"))

    assert result == {
        "error": "enter rejected",
        "type": "TEXT",
        "area": "area",
        "channel": "channel-1",
        "status": False,
        "message": "enter rejected",
    }


def test_oopz_sdk_leave_voice_channel_returns_request_payload_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_request",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.leave_voice_channel("channel-1", area="area", target="target-1"))

    assert result == {
        "error": "HTTP 503 | gateway error",
        "area": "area",
        "channel": "channel-1",
        "target": "target-1",
    }


def test_oopz_sdk_leave_voice_channel_returns_request_payload_on_failed_payload(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_request",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "leave rejected"},
        ),
    )

    result = _run(service.leave_voice_channel("channel-1", area="area", target="target-1"))

    assert result == {
        "error": "leave rejected",
        "area": "area",
        "channel": "channel-1",
        "target": "target-1",
        "status": False,
        "message": "leave rejected",
    }
