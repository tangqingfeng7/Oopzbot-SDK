from __future__ import annotations

from pathlib import Path
import tomllib


def test_pyproject_ships_compat_oopz_and_real_oopz_sdk_packages() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as fp:
        data = tomllib.load(fp)

    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    assert include == ["oopz", "oopz_sdk", "oopz_sdk.*"]

    package_data = data["tool"]["setuptools"]["package-data"]
    assert package_data["oopz"] == ["py.typed"]
    assert package_data["oopz_sdk"] == ["py.typed"]
