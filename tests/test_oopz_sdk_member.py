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

    result = _run(service.get_person_detail("u1", as_model=True))

    assert isinstance(result, models.PersonDetail)
    assert result.uid == "u1"
    assert result.name == "Alice"


def test_oopz_sdk_get_person_infos_batch_returns_error_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_person_infos_batch(["u1", "u2"]))

    assert result == {"error": "批量获取用户信息失败: HTTP 503"}


def test_oopz_sdk_enter_area_returns_request_payload_on_http_failure(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.enter_area("area-1", recover=True))

    assert result == {"error": "HTTP 503", "area": "area-1", "recover": True}


def test_oopz_sdk_enter_area_returns_request_payload_on_failed_payload(monkeypatch):
    service = AreaService(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "enter area rejected"},
        ),
    )

    result = _run(service.enter_area("area-1", recover=True))

    assert result == {
        "error": "enter area rejected",
        "area": "area-1",
        "recover": True,
        "status": False,
        "message": "enter area rejected",
    }


def test_oopz_sdk_get_user_area_detail_requires_area_before_request(monkeypatch):
    service = Member(None, _make_config(default_area="area-default"))

    async def _fake_get(*args, **kwargs):
        raise AssertionError("不应在缺少 area 时继续获取用户域内详情")

    monkeypatch.setattr(service, "_get", _fake_get)

    with pytest.raises(ValueError, match="area cannot be empty"):
        _run(service.get_user_area_detail("target-1", ""))


def test_oopz_sdk_get_person_infos_batch_returns_error_on_failed_payload(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "person infos unavailable"},
        ),
    )

    result = _run(service.get_person_infos_batch(["u1", "u2"]))

    assert result == {"error": "批量获取用户信息失败: person infos unavailable"}


def test_oopz_sdk_get_person_infos_batch_returns_error_with_partial_result_when_later_batch_fails(monkeypatch):
    service = Member(None, _make_config())
    calls = {"count": 0}

    def _fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse(
                200,
                payload={"status": True, "data": [{"uid": "u1", "name": "Alice"}]},
            )
        return _FakeResponse(503, text="gateway error")

    monkeypatch.setattr(service, "_post", _fake_post)

    result = _run(service.get_person_infos_batch([f"u{i}" for i in range(31)]))

    assert result["error"] == "批量获取用户信息失败: HTTP 503"
    assert result["partial_results"] == {"u1": {"uid": "u1", "name": "Alice"}}


def test_oopz_sdk_get_person_infos_batch_returns_rate_limit_with_partial_result_when_later_batch_hits_429(
    monkeypatch,
):
    service = Member(None, _make_config())
    calls = {"count": 0}

    def _fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _FakeResponse(
                200,
                payload={"status": True, "data": [{"uid": "u1", "name": "Alice"}]},
            )
        return _FakeResponse(429, text="too fast", headers={"Retry-After": "7"})

    monkeypatch.setattr(service, "_post", _fake_post)

    result = _run(service.get_person_infos_batch([f"u{i}" for i in range(31)]))

    assert result["error"] == "批量获取用户信息失败: HTTP 429"
    assert result["status_code"] == 429
    assert result["retry_after"] == 7
    assert result["partial_results"] == {"u1": {"uid": "u1", "name": "Alice"}}


def test_oopz_sdk_person_detail_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_person_detail("u1", as_model=True))

    assert isinstance(result, models.PersonDetail)
    assert result.payload == {"error": "HTTP 503"}


def test_oopz_sdk_get_person_detail_returns_request_payload_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_person_detail("u1"))

    assert result == {"error": "HTTP 503", "uid": "u1"}


def test_oopz_sdk_get_person_detail_returns_request_payload_on_failed_payload(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "person detail rejected"},
        ),
    )

    result = _run(service.get_person_detail("u1"))

    assert result == {
        "error": "person detail rejected",
        "uid": "u1",
        "status": False,
        "message": "person detail rejected",
    }


def test_oopz_sdk_person_detail_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"uid": "u1"}},
        ),
    )

    result = _run(service.get_person_detail("u1", as_model=True))

    assert isinstance(result, models.PersonDetail)
    assert result.payload == {"error": "person detail响应格式异常"}


def test_oopz_sdk_person_detail_as_model_returns_result_object_on_malformed_member_entry(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ["bad"]},
        ),
    )

    result = _run(service.get_person_detail("u1", as_model=True))

    assert isinstance(result, models.PersonDetail)
    assert result.payload == {"error": "person detail响应格式异常"}


def test_oopz_sdk_get_person_detail_full_returns_request_payload_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_person_detail_full("u1"))

    assert result == {"error": "HTTP 503", "uid": "u1"}


def test_oopz_sdk_get_person_detail_full_returns_request_payload_on_failed_payload(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "person detail rejected"},
        ),
    )

    result = _run(service.get_person_detail_full("u1"))

    assert result == {
        "error": "person detail rejected",
        "uid": "u1",
        "status": False,
        "message": "person detail rejected",
    }


def test_oopz_sdk_get_assignable_roles_returns_error_dict_on_malformed_role_entry(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": {"roles": [{"roleID": 1}, "broken-role"]}},
        ),
    )

    result = _run(service.get_assignable_roles("target-1", area="area"))

    assert result["error"] == "assignable roles响应格式异常"
    assert result["target"] == "target-1"
    assert result["area"] == "area"
    assert result["invalid_index"] == 1


def test_oopz_sdk_edit_user_role_returns_error_on_malformed_detail_shape(monkeypatch):
    service = Member(None, _make_config())

    async def _fake_get_user_area_detail(*args, **kwargs):
        return []

    monkeypatch.setattr(service, "get_user_area_detail", _fake_get_user_area_detail)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应继续修改身份组")),
    )

    result = _run(service.edit_user_role("target-1", 1, True, area="area"))

    assert result == {
        "error": "user area detail响应格式异常",
        "area": "area",
        "target": "target-1",
        "targetRoleIDs": [],
    }


def test_oopz_sdk_edit_user_role_preserves_detail_error_payload(monkeypatch):
    service = Member(None, _make_config())

    async def _fake_get_user_area_detail(*args, **kwargs):
        return {"error": "detail unavailable", "area": "area", "target": "target-1"}

    monkeypatch.setattr(service, "get_user_area_detail", _fake_get_user_area_detail)

    result = _run(service.edit_user_role("target-1", 1, True, area="area"))

    assert result == {"error": "detail unavailable", "area": "area", "target": "target-1"}


def test_oopz_sdk_edit_user_role_returns_request_payload_on_http_failure(monkeypatch):
    service = Member(None, _make_config())

    async def _fake_get_user_area_detail(*args, **kwargs):
        return {"list": [{"roleID": 1}]}

    monkeypatch.setattr(service, "get_user_area_detail", _fake_get_user_area_detail)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.edit_user_role("target-1", 2, True, area="area"))

    assert result == {
        "error": "HTTP 503 | gateway error",
        "area": "area",
        "target": "target-1",
        "targetRoleIDs": [1, 2],
    }


def test_oopz_sdk_edit_user_role_returns_request_payload_on_failed_payload(monkeypatch):
    service = Member(None, _make_config())

    async def _fake_get_user_area_detail(*args, **kwargs):
        return {"list": [{"roleID": 1}]}

    monkeypatch.setattr(service, "get_user_area_detail", _fake_get_user_area_detail)
    monkeypatch.setattr(
        service,
        "_post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "role edit rejected"},
        ),
    )

    result = _run(service.edit_user_role("target-1", 2, True, area="area"))

    assert result == {
        "error": "role edit rejected",
        "area": "area",
        "target": "target-1",
        "targetRoleIDs": [1, 2],
        "status": False,
        "message": "role edit rejected",
    }


def test_oopz_sdk_self_detail_as_model_returns_result_object_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_self_detail(as_model=True))

    assert isinstance(result, models.SelfDetail)
    assert result.payload == {"error": "HTTP 503"}


def test_oopz_sdk_get_level_info_returns_error_dict_on_failed_payload(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "level rejected"},
        ),
    )

    result = _run(service.get_level_info())

    assert result == {
        "error": "level rejected",
        "status": False,
        "message": "level rejected",
    }


def test_oopz_sdk_get_self_detail_returns_request_payload_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_self_detail())

    assert result == {"error": "HTTP 503", "uid": "person"}


def test_oopz_sdk_get_assignable_roles_returns_error_dict_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_assignable_roles("target-1", area="area"))

    assert result == {"error": "HTTP 503", "area": "area", "target": "target-1"}


def test_oopz_sdk_get_user_area_detail_returns_request_payload_on_http_failure(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(503, text="gateway error"),
    )

    result = _run(service.get_user_area_detail("target-1", area="area"))

    assert result == {"error": "HTTP 503", "area": "area", "target": "target-1"}


def test_oopz_sdk_self_detail_as_model_returns_result_object_on_malformed_success(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": True, "data": ["bad"]},
        ),
    )

    result = _run(service.get_self_detail(as_model=True))

    assert isinstance(result, models.SelfDetail)
    assert result.payload == {"error": "self detail响应格式异常"}


def test_oopz_sdk_get_self_detail_returns_request_payload_on_failed_payload(monkeypatch):
    service = Member(None, _make_config())
    monkeypatch.setattr(
        service,
        "_get",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={"status": False, "message": "self detail rejected"},
        ),
    )

    result = _run(service.get_self_detail())

    assert result == {
        "error": "self detail rejected",
        "uid": "person",
        "status": False,
        "message": "self detail rejected",
    }
