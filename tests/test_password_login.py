"""账号密码登录凭据模型的离线测试。"""

from __future__ import annotations

import asyncio
import base64
import json
import time

import pytest

import oopz_sdk.auth.password_login as password_login_module
from oopz_sdk import OopzConfig, OopzLoginCredentials, load_credentials_json, save_credentials_json


def _fake_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode("utf-8").rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{header}.{payload}.sig"


def test_login_credentials_from_mapping_accepts_private_key_alias() -> None:
    token = _fake_jwt(int(time.time()) + 3600)
    credentials = OopzLoginCredentials.from_mapping(
        {
            "device_id": "device-1",
            "person_uid": "person-1",
            "jwt_token": token,
            "private_key": "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----",
            "app_version": "70000",
        }
    )

    assert credentials.device_id == "device-1"
    assert credentials.person_uid == "person-1"
    assert credentials.jwt_token == token
    assert credentials.private_key_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert credentials.app_version == "70000"
    assert credentials.expires_in_seconds is not None


def test_login_credentials_to_config_uses_extracted_values() -> None:
    credentials = OopzLoginCredentials(
        device_id="device-1",
        person_uid="person-1",
        jwt_token="token",
        private_key_pem="pem",
        app_version="70000",
    )

    config = credentials.to_config(base_url="https://example.test")

    assert isinstance(config, OopzConfig)
    assert config.device_id == "device-1"
    assert config.person_uid == "person-1"
    assert config.jwt_token == "token"
    assert config.private_key == "pem"
    assert config.app_version == "70000"
    assert config.base_url == "https://example.test"


def test_oopz_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_DEVICE_ID", "device-1")
    monkeypatch.setenv("OOPZ_PERSON_UID", "person-1")
    monkeypatch.setenv("OOPZ_JWT_TOKEN", "token")
    monkeypatch.setenv("OOPZ_PRIVATE_KEY", "pem")
    monkeypatch.setenv("OOPZ_APP_VERSION", "70000")

    config = OopzConfig.from_env(base_url="https://example.test")

    assert config.device_id == "device-1"
    assert config.person_uid == "person-1"
    assert config.jwt_token == "token"
    assert config.private_key == "pem"
    assert config.app_version == "70000"
    assert config.base_url == "https://example.test"


def test_oopz_config_from_env_requires_missing_variable(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_DEVICE_ID", "device-1")
    monkeypatch.setenv("OOPZ_PERSON_UID", "person-1")
    monkeypatch.setenv("OOPZ_JWT_TOKEN", "token")
    monkeypatch.delenv("OOPZ_PRIVATE_KEY", raising=False)

    with pytest.raises(ValueError, match="OOPZ_PRIVATE_KEY"):
        OopzConfig.from_env()


def test_oopz_config_from_password_env(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_LOGIN_PHONE", "phone-1")
    monkeypatch.setenv("OOPZ_LOGIN_PASSWORD", "password-1")
    calls = {}

    async def fake_login_with_password(phone, password, **kwargs):
        calls["phone"] = phone
        calls["password"] = password
        calls["kwargs"] = kwargs
        return OopzLoginCredentials(
            device_id="device-1",
            person_uid="person-1",
            jwt_token="token",
            private_key_pem="pem",
            app_version="70000",
        )

    monkeypatch.setattr(password_login_module, "login_with_password", fake_login_with_password)

    config = asyncio.run(
        OopzConfig.from_password_env(
            headless=False,
            timeout=12,
            config_overrides={"base_url": "https://example.test"},
        )
    )

    assert calls == {
        "phone": "phone-1",
        "password": "password-1",
        "kwargs": {"headless": False, "timeout": 12},
    }
    assert config.device_id == "device-1"
    assert config.person_uid == "person-1"
    assert config.jwt_token == "token"
    assert config.private_key == "pem"
    assert config.app_version == "70000"
    assert config.base_url == "https://example.test"


def test_oopz_config_from_password_env_accepts_custom_env_names(monkeypatch) -> None:
    monkeypatch.setenv("BOT_ACCOUNT", "phone-2")
    monkeypatch.setenv("BOT_PASSWORD", "password-2")
    calls = {}

    async def fake_login_with_password(phone, password, **kwargs):
        calls["phone"] = phone
        calls["password"] = password
        calls["kwargs"] = kwargs
        return OopzLoginCredentials(
            device_id="device-2",
            person_uid="person-2",
            jwt_token="token-2",
            private_key_pem="pem-2",
        )

    monkeypatch.setattr(password_login_module, "login_with_password", fake_login_with_password)

    config = asyncio.run(
        OopzConfig.from_password_env(
            phone_env="BOT_ACCOUNT",
            password_env="BOT_PASSWORD",
            browser_data_dir=".oopz_sdk_login_profile",
        )
    )

    assert calls == {
        "phone": "phone-2",
        "password": "password-2",
        "kwargs": {"headless": True, "browser_data_dir": ".oopz_sdk_login_profile"},
    }
    assert config.device_id == "device-2"
    assert config.person_uid == "person-2"
    assert config.jwt_token == "token-2"
    assert config.private_key == "pem-2"


def test_oopz_config_from_password_env_requires_password_before_login(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_LOGIN_PHONE", "phone-1")
    monkeypatch.delenv("OOPZ_LOGIN_PASSWORD", raising=False)
    called = False

    async def fake_login_with_password(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("login should not be called when password env is missing")

    monkeypatch.setattr(password_login_module, "login_with_password", fake_login_with_password)

    with pytest.raises(ValueError, match="OOPZ_LOGIN_PASSWORD"):
        asyncio.run(OopzConfig.from_password_env())

    assert called is False


def test_oopz_config_from_password_env_sync(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_LOGIN_PHONE", "phone-1")
    monkeypatch.setenv("OOPZ_LOGIN_PASSWORD", "password-1")

    async def fake_login_with_password(phone, password, **kwargs):
        return OopzLoginCredentials(
            device_id=f"device-for-{phone}",
            person_uid="person-1",
            jwt_token=f"token-for-{password}",
            private_key_pem="pem",
        )

    monkeypatch.setattr(password_login_module, "login_with_password", fake_login_with_password)

    config = OopzConfig.from_password_env_sync()

    assert config.device_id == "device-for-phone-1"
    assert config.jwt_token == "token-for-password-1"


def test_save_and_load_credentials_json_round_trip(tmp_path) -> None:
    path = tmp_path / "oopz_credentials.json"
    credentials = OopzLoginCredentials(
        device_id="device-1",
        person_uid="person-1",
        jwt_token="token",
        private_key_pem="pem",
        app_version="70000",
    )

    saved_path = save_credentials_json(credentials, path)
    loaded = load_credentials_json(saved_path)

    assert loaded.to_dict() == credentials.to_dict()


def test_login_credentials_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_DEVICE_ID", "device-1")
    monkeypatch.setenv("OOPZ_PERSON_UID", "person-1")
    monkeypatch.setenv("OOPZ_JWT_TOKEN", "token")
    monkeypatch.setenv("OOPZ_PRIVATE_KEY", "pem")
    monkeypatch.setenv("OOPZ_APP_VERSION", "70000")

    credentials = OopzLoginCredentials.from_env()

    assert credentials.to_env() == {
        "OOPZ_DEVICE_ID": "device-1",
        "OOPZ_PERSON_UID": "person-1",
        "OOPZ_JWT_TOKEN": "token",
        "OOPZ_PRIVATE_KEY": "pem",
        "OOPZ_APP_VERSION": "70000",
    }


def test_masked_credentials_do_not_expose_full_secret() -> None:
    credentials = OopzLoginCredentials(
        device_id="device-abcdef",
        person_uid="person-abcdef",
        jwt_token="jwt-token-secret-value",
        private_key_pem="pem",
    )

    masked = credentials.masked()

    assert masked["private_key"] is True
    assert masked["jwt_token"] != credentials.jwt_token
    assert "secret" not in masked["jwt_token"]


def test_cli_env_lines_preserve_multiline_private_key() -> None:
    credentials = OopzLoginCredentials(
        device_id="device-1",
        person_uid="person-1",
        jwt_token="token",
        private_key_pem="-----BEGIN PRIVATE KEY-----\nkey-line\n-----END PRIVATE KEY-----",
        app_version="70000",
    )

    powershell = password_login_module._powershell_env_lines(credentials)
    bash = password_login_module._bash_env_lines(credentials)

    assert "$env:OOPZ_DEVICE_ID = 'device-1'" in powershell
    assert "$env:OOPZ_APP_VERSION = '70000'" in powershell
    assert "$env:OOPZ_PRIVATE_KEY = @'\n-----BEGIN PRIVATE KEY-----" in powershell
    assert "-----END PRIVATE KEY-----\n'@" in powershell
    assert "export OOPZ_DEVICE_ID=device-1" in bash
    assert "export OOPZ_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----\nkey-line\n-----END PRIVATE KEY-----'" in bash
