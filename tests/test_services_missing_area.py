"""
service 层对必要参数缺失时行为的单元测试。
返回 `OperationResult` 的方法，在 `area` / `channel` / `channel_id` /
`uid` / `target` / `message_id` 缺失时应统一使用软失败
（`OperationResult(ok=False, message="缺少 xxx")`），
而不是抛 `ValueError` —— 以保持和同方法内其它缺参处理风格一致。
"""

from __future__ import annotations

import pytest

from oopz_sdk.services.channel import Channel
from oopz_sdk.services.message import Message
from oopz_sdk.services.moderation import Moderation


def _make_channel() -> Channel:
    return Channel(owner=object(), config=None, transport=None, signer=None)


def _make_moderation() -> Moderation:
    return Moderation(owner=object(), config=None, transport=None, signer=None)


def _make_message() -> Message:
    return Message(owner=object(), config=None, transport=None, signer=None)


@pytest.mark.asyncio
async def test_update_channel_missing_area_returns_soft_failure() -> None:
    svc = _make_channel()
    result = await svc.update_channel(area=None, channel_id="c-1")
    assert result.ok is False
    assert result.message == "缺少 area"


@pytest.mark.asyncio
async def test_update_channel_missing_channel_id_returns_soft_failure() -> None:
    svc = _make_channel()
    result = await svc.update_channel(area="a-1", channel_id="")
    assert result.ok is False
    assert result.message == "缺少 channel_id"


@pytest.mark.asyncio
async def test_delete_channel_missing_area_returns_soft_failure() -> None:
    svc = _make_channel()
    result = await svc.delete_channel(channel="c-1", area=None)
    assert result.ok is False
    assert result.message == "缺少 area"


@pytest.mark.asyncio
async def test_delete_channel_missing_channel_returns_soft_failure() -> None:
    svc = _make_channel()
    result = await svc.delete_channel(channel="", area="a-1")
    assert result.ok is False
    assert result.message == "缺少 channel"


@pytest.mark.asyncio
async def test_mute_user_missing_area_returns_soft_failure() -> None:
    svc = _make_moderation()
    result = await svc.mute_user(uid="u-1", area=None)
    assert result.ok is False
    assert result.message == "缺少 area"


@pytest.mark.asyncio
async def test_create_channel_missing_area_returns_soft_failure() -> None:
    svc = _make_channel()
    result = await svc.create_channel(area=None, name="n")
    assert result.ok is False
    assert result.message == "缺少 area"


@pytest.mark.parametrize(
    "method_name",
    [
        "unmute_user",
        "mute_mic",
        "unmute_mic",
        "remove_from_area",
        "block_user_in_area",
        "unblock_user_in_area",
    ],
)
@pytest.mark.asyncio
async def test_moderation_methods_missing_area_return_soft_failure(method_name: str) -> None:
    svc = _make_moderation()
    method = getattr(svc, method_name)
    result = await method(uid="u-1", area=None)
    assert result.ok is False
    assert result.message == "缺少 area"


@pytest.mark.parametrize(
    "method_name",
    [
        "mute_user",
        "unmute_user",
        "mute_mic",
        "unmute_mic",
        "remove_from_area",
        "block_user_in_area",
        "unblock_user_in_area",
    ],
)
@pytest.mark.asyncio
async def test_moderation_methods_missing_uid_return_soft_failure(method_name: str) -> None:
    svc = _make_moderation()
    method = getattr(svc, method_name)
    result = await method(uid="", area="a-1")
    assert result.ok is False
    assert result.message == "缺少 uid"


@pytest.mark.asyncio
async def test_recall_message_missing_area_returns_soft_failure() -> None:
    svc = _make_message()
    result = await svc.recall_message(message_id="m-1", area="", channel="ch-1")
    assert result.ok is False
    assert result.message == "缺少 area"


@pytest.mark.asyncio
async def test_recall_private_message_missing_target_returns_soft_failure() -> None:
    svc = _make_message()
    result = await svc.recall_private_message(message_id="m-1", channel="ch-1", target="")
    assert result.ok is False
    assert result.message == "缺少 target"
