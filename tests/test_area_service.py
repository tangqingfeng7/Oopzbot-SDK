from __future__ import annotations

import asyncio
from typing import Any

import pytest

from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.services.area import AreaService


class _FakeAreaService(AreaService):
    def __init__(self, response_data: Any) -> None:
        self._response_data = response_data

    async def _request_data(self, *args, **kwargs) -> Any:
        return self._response_data


def _run(coro):
    return asyncio.run(coro)


def test_get_area_can_give_list_accepts_roles_list() -> None:
    service = _FakeAreaService(
        {
            "roles": [
                {
                    "roleID": 123,
                    "name": "admin",
                    "description": "管理员",
                    "owned": True,
                    "sort": 1,
                }
            ]
        }
    )

    roles = _run(service.get_area_can_give_list("area-1", "uid-1"))

    assert len(roles) == 1
    assert roles[0].role_id == 123
    assert roles[0].name == "admin"


@pytest.mark.parametrize(
    "response_data",
    [
        [],
        {},
        {"roles": None},
        {"roles": {}},
        {"roles": "bad"},
    ],
)
def test_get_area_can_give_list_rejects_invalid_response_shape(response_data) -> None:
    service = _FakeAreaService(response_data)

    with pytest.raises(OopzApiError):
        _run(service.get_area_can_give_list("area-1", "uid-1"))


def test_get_user_area_nicknames_accepts_nickname_dict() -> None:
    service = _FakeAreaService({"nicknames": {"u1": "Alice", 2: "Bob"}})

    nicknames = _run(service.get_user_area_nicknames("area-1", ["u1", "2"]))

    assert nicknames == {"u1": "Alice", "2": "Bob"}


@pytest.mark.parametrize(
    "response_data",
    [
        [],
        {},
        {"nicknames": None},
        {"nicknames": []},
        {"nicknames": "bad"},
    ],
)
def test_get_user_area_nicknames_rejects_invalid_response_shape(response_data) -> None:
    service = _FakeAreaService(response_data)

    with pytest.raises(OopzApiError):
        _run(service.get_user_area_nicknames("area-1", ["u1"]))
