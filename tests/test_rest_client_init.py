"""
对 OopzRESTClient 构造入参的校验测试。
"""

from __future__ import annotations

import pytest

from oopz_sdk import OopzRESTClient


def test_rest_client_rejects_non_config_first_arg_string() -> None:
    with pytest.raises(TypeError, match="OopzConfig"):
        OopzRESTClient("not a config")  # type: ignore[arg-type]


def test_rest_client_rejects_non_config_first_arg_none() -> None:
    with pytest.raises(TypeError, match="OopzConfig"):
        OopzRESTClient(None)  # type: ignore[arg-type]


def test_rest_client_rejects_legacy_positional_bot_signature() -> None:
    """模拟 v0.5 之前 `OopzRESTClient(bot, config)` 的误用：bot 不是 OopzConfig，
    应该直接被早期 TypeError 拦下，而不是走到 Signer 里抛出看不懂的 PEM 错误。"""

    class FakeBot:
        pass

    with pytest.raises(TypeError, match=r"OopzRESTClient\(config, \*, bot=None\)"):
        OopzRESTClient(FakeBot())  # type: ignore[arg-type]
