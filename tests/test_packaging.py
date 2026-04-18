from __future__ import annotations

from pathlib import Path


def test_pyproject_ships_only_oopz_sdk_packages() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    assert 'include = ["oopz_sdk", "oopz_sdk.*"]' in text
    assert 'oopz_sdk = ["py.typed"]' in text


def test_manifest_includes_py_typed_from_oopz_sdk_package() -> None:
    manifest = Path(__file__).resolve().parents[1] / "MANIFEST.in"
    lines = manifest.read_text(encoding="utf-8").splitlines()

    assert "include oopz_sdk/py.typed" in lines
