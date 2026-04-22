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

def test_oopz_sdk_area_members_retries_after_429(monkeypatch):
    service = AreaService(_make_config())
    captured = {}

    async def _fake_request_data_with_retry(method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["kwargs"] = kwargs
        return {
            "members": [{"uid": "u1", "online": 1}],
            "roleCount": [],
            "totalCount": 1,
        }

    monkeypatch.setattr(service, "_request_data_with_retry", _fake_request_data_with_retry)

    result = _run(service.get_area_members(area="area"))

    assert isinstance(result, models.AreaMembersPage)
    assert result.members[0].uid == "u1"
    assert captured["method"] == "GET"
    assert captured["path"] == "/area/v3/members"
    assert captured["kwargs"]["retry_on_429"] is True
    assert captured["kwargs"]["max_attempts"] == 3


def test_oopz_sdk_area_members_does_not_fallback_to_stale_cache_on_http_failure(monkeypatch):
    service = AreaService(_make_config())
    cache_key = ("area", 0, 49)
    service._area_members_cache = {
        cache_key: {
            "ts": 0,
            "data": {
                "members": [{"uid": "stale-user", "name": "Stale", "online": 1}],
                "onlineCount": 1,
                "totalCount": 1,
                "userCount": 1,
                "fetchedCount": 1,
            },
        }
    }

    async def _fake_request_data_with_retry(*args, **kwargs):
        raise OopzApiError("HTTP 503")

    monkeypatch.setattr(service, "_request_data_with_retry", _fake_request_data_with_retry)

    with pytest.raises(OopzApiError, match="HTTP 503"):
        _run(service.get_area_members(area="area"))


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

    result = _run(service.get_area_members(area="area"))

    assert isinstance(result, models.AreaMembersPage)
    assert result.members[0].uid == "u1"
    assert result.total_count == 1
    assert result.from_cache is True


def test_oopz_sdk_area_members_as_model_returns_result_object_when_response_missing(monkeypatch):
    service = AreaService(_make_config())

    async def _fake_request_data_with_retry(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "_request_data_with_retry", _fake_request_data_with_retry)

    with pytest.raises(OopzApiError, match="invalid area members payload: expected dict"):
        _run(service.get_area_members(area="area"))


def test_oopz_sdk_area_members_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = AreaService(_make_config())
    async def _fake_request_data_with_retry(*args, **kwargs):
        return ["bad"]

    monkeypatch.setattr(service, "_request_data_with_retry", _fake_request_data_with_retry)

    with pytest.raises(OopzApiError, match="invalid area members payload: expected dict"):
        _run(service.get_area_members(area="area"))


def test_oopz_sdk_area_members_as_model_returns_result_object_on_malformed_member_entry(
    monkeypatch,
):
    service = AreaService(_make_config())
    async def _fake_request_data_with_retry(*args, **kwargs):
        return {
            "members": [{"uid": "u1"}, "broken-member"],
            "roleCount": [],
            "totalCount": 2,
        }

    monkeypatch.setattr(service, "_request_data_with_retry", _fake_request_data_with_retry)

    with pytest.raises(ValidationError, match="members.1"):
        _run(service.get_area_members(area="area"))


def test_oopz_sdk_joined_areas_as_model(monkeypatch):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        return [{"id": "area-1", "name": "测试域", "owner": "owner-1"}]

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    result = _run(service.get_joined_areas())

    assert isinstance(result, list)
    assert isinstance(result[0], models.JoinedAreaInfo)
    assert result[0].area_id == "area-1"
    assert result[0].name == "测试域"


def test_oopz_sdk_joined_areas_as_model_returns_result_object_on_malformed_entry(
    monkeypatch,
):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        return [{"id": "area-1", "name": "测试域", "owner": "owner-1"}, "broken-area"]

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(OopzApiError, match="invalid area payload: expected dict"):
        _run(service.get_joined_areas())


def test_oopz_sdk_joined_areas_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        raise OopzApiError("HTTP 503")

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(OopzApiError, match="HTTP 503"):
        _run(service.get_joined_areas())


def test_oopz_sdk_joined_areas_returns_error_dict_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        raise OopzApiError("HTTP 503")

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(OopzApiError, match="HTTP 503"):
        _run(service.get_joined_areas())


def test_oopz_sdk_joined_areas_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        return {"id": "area-1"}

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(OopzApiError, match="invalid area payload: expected dict"):
        _run(service.get_joined_areas())


def test_oopz_sdk_area_info_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        raise OopzApiError("HTTP 503")

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(OopzApiError, match="HTTP 503"):
        _run(service.get_area_info("area"))


def test_oopz_sdk_get_area_members_requires_area_before_request(monkeypatch):
    service = AreaService(None, _make_config(default_area="area-default"))

    async def _fake_request_data_with_retry(*args, **kwargs):
        raise AssertionError("不应在缺少 area 时继续请求域成员")

    monkeypatch.setattr(service, "_request_data_with_retry", _fake_request_data_with_retry)

    with pytest.raises(ValueError, match="缺少 area"):
        _run(service.get_area_members())


def test_oopz_sdk_get_area_info_requires_area_before_request(monkeypatch):
    service = AreaService(None, _make_config(default_area="area-default"))

    async def _fake_request_data(*args, **kwargs):
        raise AssertionError("不应在缺少 area 时继续请求域信息")

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(ValueError, match="缺少 area"):
        _run(service.get_area_info(""))


def test_oopz_sdk_area_info_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        return ["bad"]

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(OopzApiError, match="invalid area detail payload: expected dict"):
        _run(service.get_area_info("area"))


def test_oopz_sdk_area_service_get_area_channels_returns_error_dict_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        raise OopzApiError("HTTP 503")

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(OopzApiError, match="HTTP 503"):
        _run(service.get_area_channels(area="area"))


def test_oopz_sdk_area_service_get_area_channels_returns_format_error_on_malformed_group(
    monkeypatch,
):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        return ["broken-group"]

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(OopzApiError, match="invalid channel group payload: expected dict"):
        _run(service.get_area_channels(area="area"))


def test_oopz_sdk_area_service_get_area_channels_returns_format_error_on_falsey_channels_value(
    monkeypatch,
):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        return [
            {
                "id": "group-1",
                "channels": "",
            }
        ]

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    with pytest.raises(ValidationError, match="channels"):
        _run(service.get_area_channels(area="area"))


def test_oopz_sdk_area_service_get_area_channels_returns_format_error_on_falsey_data(
    monkeypatch,
):
    service = AreaService(None, _make_config())
    async def _fake_request_data(*args, **kwargs):
        return ""

    monkeypatch.setattr(service, "_request_data", _fake_request_data)

    result = _run(service.get_area_channels(area="area"))

    assert result == []


def test_oopz_sdk_populate_names_propagates_joined_area_error(monkeypatch):
    service = AreaService(None, _make_config())

    async def _fake_get_joined_areas(*args, **kwargs):
        raise OopzApiError("joined areas unavailable")

    monkeypatch.setattr(service, "get_joined_areas", _fake_get_joined_areas)

    with pytest.raises(OopzApiError, match="joined areas unavailable"):
        _run(service.populate_names())


def test_oopz_sdk_populate_names_propagates_channel_group_error(monkeypatch):
    service = AreaService(None, _make_config())

    async def _fake_get_joined_areas(*args, **kwargs):
        return [models.JoinedAreaInfo.from_api({"id": "area-1", "name": "测试域", "owner": "owner-1"})]

    async def _fake_get_area_channels(*args, **kwargs):
        raise OopzApiError("channel groups unavailable")

    monkeypatch.setattr(service, "get_joined_areas", _fake_get_joined_areas)
    monkeypatch.setattr(service, "get_area_channels", _fake_get_area_channels)

    with pytest.raises(OopzApiError, match="channel groups unavailable"):
        _run(service.populate_names())


def test_oopz_sdk_populate_names_does_not_commit_partial_names_before_failure(monkeypatch):
    service = AreaService(None, _make_config())
    named_areas = []
    named_channels = []

    async def _fake_get_joined_areas(*args, **kwargs):
        return [
            models.JoinedAreaInfo.from_api({"id": "area-1", "name": "测试域1", "owner": "owner-1"}),
            models.JoinedAreaInfo.from_api({"id": "area-2", "name": "测试域2", "owner": "owner-2"}),
        ]

    async def _fake_get_area_channels(area_id, *args, **kwargs):
        if area_id == "area-1":
            return [
                models.ChannelGroupInfo.from_api(
                    {
                        "id": "group-1",
                        "name": "分组1",
                        "channels": [{"id": "channel-1", "name": "大厅"}],
                    }
                )
            ]
        raise OopzApiError("channel groups unavailable")

    monkeypatch.setattr(service, "get_joined_areas", _fake_get_joined_areas)
    monkeypatch.setattr(service, "get_area_channels", _fake_get_area_channels)

    with pytest.raises(OopzApiError, match="channel groups unavailable"):
        _run(
            service.populate_names(
            set_area=lambda area_id, area_name: named_areas.append((area_id, area_name)),
            set_channel=lambda channel_id, channel_name: named_channels.append((channel_id, channel_name)),
        )
        )

    assert named_areas == [("area-1", "测试域1"), ("area-2", "测试域2")]
    assert named_channels == [("channel-1", "大厅")]


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

    result = _run(service.get_area_channels(area="area"))

    assert result["error"] == "channel groups响应格式异常"
    assert result["area"] == "area"
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

    result = _run(service.get_area_channels(area="area"))

    assert result == {"error": "channel groups响应格式异常", "area": "area"}


def test_oopz_sdk_get_area_channels_returns_error_dict_on_http_failure(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_area_channels(area="area"))

    assert result == {"error": "HTTP 503", "area": "area"}


def test_oopz_sdk_get_area_channels_returns_error_dict_on_failed_payload(monkeypatch):
    service = Channel(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "group list rejected"},
        ),
    )

    result = _run(service.get_area_channels(area="area"))

    assert result == {
        "error": "group list rejected",
        "area": "area",
        "status": False,
        "message": "group list rejected",
    }


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

    result = _run(service.get_area_blocks(area="area", as_model=True))

    assert isinstance(result, models.AreaBlocksResult)
    assert result.payload == {"error": "area blocks响应格式异常"}


def test_oopz_sdk_area_blocks_as_model_returns_result_object_on_success(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "status": True,
                "data": {
                    "blocks": [
                        {"uid": "u1", "name": "Alice", "reason": "spam"},
                        {"id": "u2", "nickname": "Bob"},
                    ]
                },
            },
        ),
    )

    result = _run(service.get_area_blocks(area="area", as_model=True))

    assert isinstance(result, models.AreaBlocksResult)
    assert [block.uid for block in result.blocks] == ["u1", "u2"]
    assert [block.name for block in result.blocks] == ["Alice", "Bob"]
    assert [block.reason for block in result.blocks] == ["spam", ""]
    assert result.payload["status"] is True


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

    result = _run(service.get_area_blocks(area="area", as_model=True))

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

    result = _run(service.get_area_blocks(area="area", as_model=True))

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

    result = _run(service.get_area_blocks(area="area"))

    assert result["error"] == "area blocks响应格式异常"
    assert result["area"] == "area"
    assert result["invalid_index"] == 1


def test_oopz_sdk_get_area_blocks_returns_error_dict_on_http_failure(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_area_blocks(area="area", name="alice"))

    assert result == {"error": "HTTP 503", "area": "area", "name": "alice"}


def test_oopz_sdk_get_area_blocks_returns_error_dict_on_failed_payload(monkeypatch):
    service = Moderation(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "blocks rejected"},
        ),
    )

    result = _run(service.get_area_blocks(area="area", name="alice"))

    assert result == {
        "error": "blocks rejected",
        "area": "area",
        "name": "alice",
        "status": False,
        "message": "blocks rejected",
    }


def test_oopz_sdk_search_area_members_as_model_raises_api_error_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    with pytest.raises(OopzApiError) as exc_info:
        _run(service.search_area_members(area="area", keyword="alice", as_model=True))

    assert str(exc_info.value) == "HTTP 503"
    assert exc_info.value.response == {"error": "HTTP 503"}


def test_oopz_sdk_search_area_members_returns_error_dict_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.search_area_members(area="area", keyword="alice"))

    assert result == {
        "error": "HTTP 503",
        "area": "area",
        "name": "alice",
        "offset": 0,
        "limit": 50,
    }


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
        _run(service.search_area_members(area="area", keyword="alice", as_model=True))

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
        _run(service.search_area_members(area="area", keyword="alice", as_model=True))

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

    result = _run(service.search_area_members(area="area", keyword="alice"))

    assert result == {
        "error": "search area members响应格式异常",
        "area": "area",
        "name": "alice",
        "offset": 0,
        "limit": 50,
    }


def test_oopz_sdk_search_area_members_returns_error_dict_on_malformed_member_entry(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"members": [{"uid": "u1"}, "broken-member"]}},
        ),
    )

    result = _run(service.search_area_members(area="area", keyword="alice"))

    assert result["error"] == "search area members响应格式异常"
    assert result["area"] == "area"
    assert result["name"] == "alice"
    assert result["invalid_index"] == 1
