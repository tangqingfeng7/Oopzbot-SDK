from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

from oopz_sdk.version import __version__


def _pyproject() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))


def test_voice_browser_html_is_declared_as_package_data() -> None:
    package_data = _pyproject()["tool"]["setuptools"]["package-data"]["oopz_sdk"]

    assert "assets/voice/agora_player.html" in package_data


def test_version_matches_pyproject() -> None:
    # 两处版本号曾经跑偏六个小版本：发版只改了 pyproject，version.py 停在 0.9.0，
    # 导致 oopz_sdk.__version__ 一直报告过时版本。
    assert __version__ == _pyproject()["project"]["version"]
