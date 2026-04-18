from __future__ import annotations

from pathlib import Path
import tomllib


def test_pyproject_ships_only_oopz_sdk_packages() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as fp:
        data = tomllib.load(fp)

    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    assert include == ["oopz_sdk", "oopz_sdk.*"]

    package_data = data["tool"]["setuptools"]["package-data"]
    assert package_data["oopz_sdk"] == ["py.typed"]


def test_manifest_includes_py_typed_from_oopz_sdk_package() -> None:
    manifest = Path(__file__).resolve().parents[1] / "MANIFEST.in"
    lines = manifest.read_text(encoding="utf-8").splitlines()

    assert "include oopz_sdk/py.typed" in lines
