from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


def test_voice_browser_html_is_declared_as_package_data() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    package_data = pyproject["tool"]["setuptools"]["package-data"]["oopz_sdk"]

    assert "assets/voice/agora_player.html" in package_data
