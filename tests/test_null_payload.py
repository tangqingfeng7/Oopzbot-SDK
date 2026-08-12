"""测试接口返回显式 null 时不会把 SDK 弄崩
"""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import Field, ValidationError

from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.models.area import ChannelGroupInfo, ChannelInfo
from oopz_sdk.models.base import BaseModel
from oopz_sdk.services.area import AreaService
from oopz_sdk.state.cache import CacheStore
from oopz_sdk.testing.factories import make_config
from oopz_sdk.transport.http import HttpResponse, HttpTransport


class _Sample(BaseModel):
    required_field: str
    optional_list: list[str] = Field(default_factory=list)
    optional_mapping: dict[str, str] = Field(default_factory=dict)
    optional_name: str = ""
    aliased: int = Field(default=0, alias="aliasedKey")


# ---------------------------------------------------------------------------
# 模型层：可选字段收到 null 时回落到默认值
# ---------------------------------------------------------------------------


def test_channel_group_accepts_explicit_null_channels() -> None:
    group = ChannelGroupInfo.from_api({"id": "g1", "name": "空分组", "channels": None})

    assert group.channels == []
    assert group.group_id == "g1"
    assert group.name == "空分组"


def test_channel_group_missing_key_still_works() -> None:
    group = ChannelGroupInfo.from_api({"id": "g0", "name": "正常分组"})

    assert group.channels == []


def test_null_falls_back_for_various_default_kinds() -> None:
    sample = _Sample.model_validate(
        {
            "required_field": "x",
            "optional_list": None,
            "optional_mapping": None,
            "optional_name": None,
        }
    )

    assert sample.optional_list == []
    assert sample.optional_mapping == {}
    assert sample.optional_name == ""


def test_null_on_aliased_key_falls_back_to_default() -> None:
    sample = _Sample.model_validate({"required_field": "x", "aliasedKey": None})

    assert sample.aliased == 0


def test_null_on_camel_case_alias_falls_back_to_default() -> None:
    group = ChannelGroupInfo.from_api(
        {"id": "g1", "name": "分组", "tempChannelDefaultMaxMember": None}
    )

    assert group.temp_channel_default_max_member == 0


def test_null_on_alias_choices_field_falls_back_to_default() -> None:
    # is_enable_temp 同时接受 IsEnableTemp 和 isEnableTemp 两种写法
    for key in ("IsEnableTemp", "isEnableTemp"):
        group = ChannelGroupInfo.from_api({"id": "g1", "name": "分组", key: None})
        assert group.is_enable_temp is False


def test_null_on_nested_model_field_falls_back_to_default() -> None:
    channel = ChannelInfo.from_api({"id": "c1", "name": "频道", "settings": None})

    assert channel.settings is not None


def test_required_field_with_null_still_fails() -> None:
    # 只对有默认值的字段兜底，必填字段收到 null 仍应报错，不能把真问题吞掉
    with pytest.raises(ValidationError):
        _Sample.model_validate({"required_field": None})


def test_non_mapping_payload_still_rejected() -> None:
    with pytest.raises(OopzApiError):
        ChannelGroupInfo.from_api(["not", "a", "dict"])


# ---------------------------------------------------------------------------
# populate_names：单个空分组不应中断整个流程
# ---------------------------------------------------------------------------


class _FakeAreaTransport:
    def __init__(self, areas, channels_by_area):
        self._areas = areas
        self._channels_by_area = channels_by_area

    async def request_data(self, method, path, *, params=None, body=None):
        if path.endswith("/userSubscribeArea/v1/list"):
            return self._areas
        if path.endswith("/detail/v1/channels"):
            return self._channels_by_area[params["area"]]
        raise AssertionError(f"unexpected path: {path}")


def _area(area_id: str, name: str) -> dict:
    return {"id": area_id, "name": name, "owner": "owner-1"}


def test_populate_names_survives_empty_channel_group() -> None:
    config = make_config()
    transport = _FakeAreaTransport(
        areas=[_area("area-1", "第一个域"), _area("area-2", "第二个域")],
        channels_by_area={
            "area-1": [
                {"id": "g1", "name": "分组", "channels": [{"id": "c1", "name": "频道一"}]}
            ],
            # 第二个域里有一个空分组，接口返回的是显式 null
            "area-2": [
                {"id": "g2", "name": "空分组", "channels": None},
                {"id": "g3", "name": "分组", "channels": [{"id": "c2", "name": "频道二"}]},
            ],
        },
    )
    service = AreaService(object(), config, transport, object(), CacheStore(config))

    areas: list[tuple[str, str]] = []
    channels: list[tuple[str, str]] = []
    result = asyncio.run(
        service.populate_names(
            set_area=lambda i, n: areas.append((i, n)),
            set_channel=lambda i, n: channels.append((i, n)),
        )
    )

    assert result.areas_named == 2
    assert result.channels_named == 2
    assert areas == [("area-1", "第一个域"), ("area-2", "第二个域")]
    assert channels == [("c1", "频道一"), ("c2", "频道二")]


# ---------------------------------------------------------------------------
# 传输层：错误响应里 message 为 null
# ---------------------------------------------------------------------------


def _transport_returning(status_code: int, payload: dict) -> HttpTransport:
    transport = HttpTransport(make_config(), object())
    text = json.dumps(payload)

    async def fake_request(*args, **kwargs):
        return HttpResponse(
            status_code=status_code, headers={}, content=text.encode(), text=text
        )

    transport.request = fake_request
    return transport


def test_error_message_handles_null_message() -> None:
    assert HttpTransport._error_message({"message": None, "error": "boom"}) == "boom"
    assert HttpTransport._error_message({"message": None}) == "未知错误"


def test_error_message_falls_back_to_other_keys_when_message_null() -> None:
    # message 为 null 不应妨碍后面的 msg / reason 兜底
    assert HttpTransport._error_message({"message": None, "msg": "有可用信息"}) == "有可用信息"


def test_error_message_keeps_combining_message_and_error() -> None:
    assert HttpTransport._error_message({"message": "ok", "error": "boom"}) == "ok: boom"


def test_request_json_reports_real_error_when_message_is_null() -> None:
    transport = _transport_returning(500, {"message": None, "error": "internal error"})

    with pytest.raises(OopzApiError) as excinfo:
        asyncio.run(transport.request_json("GET", "/x"))

    assert "internal error" in str(excinfo.value)
    assert excinfo.value.status_code == 500


def test_business_failure_reports_real_error_when_message_is_null() -> None:
    transport = _transport_returning(
        200, {"status": False, "message": None, "error": "biz failed"}
    )

    with pytest.raises(OopzApiError) as excinfo:
        asyncio.run(transport.request_json("GET", "/x"))

    assert "biz failed" in str(excinfo.value)
