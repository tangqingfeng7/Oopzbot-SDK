"""账号密码登录凭据模型的离线测试。"""

from __future__ import annotations

import asyncio
import base64
import json
import time

import pytest

import oopz_sdk.auth.password_login as password_login_module
from oopz_sdk import (
    OopzConfig,
    OopzLoginCredentials,
    OopzPasswordLoginError,
    ProxyConfig,
    load_credentials_json,
    save_credentials_json,
)
from oopz_sdk.exceptions import OopzPasswordLoginError as OopzPasswordLoginErrorFromExceptions


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
    monkeypatch.delenv("OOPZ_LOGIN_HEADFUL", raising=False)
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
    monkeypatch.delenv("OOPZ_LOGIN_HEADFUL", raising=False)
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
    monkeypatch.delenv("OOPZ_LOGIN_HEADFUL", raising=False)

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


# ---------------------------------------------------------------------------
# 安全相关
# ---------------------------------------------------------------------------


def test_password_login_error_is_exposed_from_exceptions() -> None:
    assert OopzPasswordLoginError is OopzPasswordLoginErrorFromExceptions


def test_password_login_error_carries_code_and_payload() -> None:
    payload = {"status": False, "code": 4001, "msg": "blocked"}
    error = OopzPasswordLoginError("blocked", code=4001, payload=payload)

    assert str(error) == "blocked"
    assert error.code == 4001
    assert error.payload is payload


def test_credentials_repr_does_not_leak_secrets() -> None:
    credentials = OopzLoginCredentials(
        device_id="device-abcdef",
        person_uid="person-abcdef",
        jwt_token="jwt-token-supersecret-1234567890",
        private_key_pem="-----BEGIN PRIVATE KEY-----\nVERY-SECRET\n-----END PRIVATE KEY-----",
    )

    rendered = repr(credentials)

    assert "supersecret" not in rendered
    assert "VERY-SECRET" not in rendered
    assert "OopzLoginCredentials" in rendered
    assert "device" in rendered  # 至少能看到一些上下文


def test_oopz_config_from_password_env_does_not_strip_password(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_LOGIN_PHONE", " phone-1 ")
    monkeypatch.setenv("OOPZ_LOGIN_PASSWORD", "  spaced-pass\n")
    monkeypatch.delenv("OOPZ_LOGIN_HEADFUL", raising=False)
    captured = {}

    async def fake_login_with_password(phone, password, **kwargs):
        captured["phone"] = phone
        captured["password"] = password
        return OopzLoginCredentials(
            device_id="device-1",
            person_uid="person-1",
            jwt_token="token",
            private_key_pem="pem",
        )

    monkeypatch.setattr(password_login_module, "login_with_password", fake_login_with_password)

    asyncio.run(OopzConfig.from_password_env())

    assert captured["phone"] == "phone-1", "phone 应该被 strip"
    assert captured["password"] == "  spaced-pass\n", "password 不应被 strip"


# ---------------------------------------------------------------------------
# truthy_env / OOPZ_LOGIN_HEADFUL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", True),
        ("true", True),
        ("True", True),
        ("YES", True),
        ("on", True),
        ("y", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("", False),
        (None, False),
        ("  true  ", True),
    ],
)
def test_truthy_env(value, expected) -> None:
    assert password_login_module.truthy_env(value) is expected


def test_oopz_config_from_password_env_uses_headful_env(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_LOGIN_PHONE", "phone-1")
    monkeypatch.setenv("OOPZ_LOGIN_PASSWORD", "password-1")
    monkeypatch.setenv("OOPZ_LOGIN_HEADFUL", "yes")
    captured = {}

    async def fake_login_with_password(phone, password, **kwargs):
        captured["headless"] = kwargs.get("headless")
        return OopzLoginCredentials(
            device_id="d",
            person_uid="p",
            jwt_token="t",
            private_key_pem="pem",
        )

    monkeypatch.setattr(password_login_module, "login_with_password", fake_login_with_password)

    asyncio.run(OopzConfig.from_password_env())

    assert captured["headless"] is False


def test_oopz_config_from_password_env_explicit_headless_overrides(monkeypatch) -> None:
    monkeypatch.setenv("OOPZ_LOGIN_PHONE", "phone-1")
    monkeypatch.setenv("OOPZ_LOGIN_PASSWORD", "password-1")
    monkeypatch.setenv("OOPZ_LOGIN_HEADFUL", "1")
    captured = {}

    async def fake_login_with_password(phone, password, **kwargs):
        captured["headless"] = kwargs.get("headless")
        return OopzLoginCredentials(
            device_id="d",
            person_uid="p",
            jwt_token="t",
            private_key_pem="pem",
        )

    monkeypatch.setattr(password_login_module, "login_with_password", fake_login_with_password)

    asyncio.run(OopzConfig.from_password_env(headless=True))

    assert captured["headless"] is True


# ---------------------------------------------------------------------------
# _safe_response_error / _extract_error_code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload,expected_substr",
    [
        ({"status": False, "msg": "账号或密码错误"}, "账号或密码错误"),
        ({"status": False, "message": "blocked"}, "blocked"),
        ({"status": False, "data": {"message": "from-data"}}, "from-data"),
        ({"status": False, "code": 4001}, "4001"),
        ({"status": False, "data": {"code": 5001}}, "5001"),
        ({"status": False}, "登录失败"),
        (None, "登录接口返回异常"),
        ("not-a-dict", "登录接口返回异常"),
    ],
)
def test_safe_response_error(payload, expected_substr) -> None:
    assert expected_substr in password_login_module._safe_response_error(payload)


def test_safe_response_error_prefers_message_over_code() -> None:
    payload = {"status": False, "code": 4001, "message": "human readable"}
    assert password_login_module._safe_response_error(payload) == "human readable"


def test_safe_response_error_with_only_code_includes_label() -> None:
    payload = {"status": False, "code": 4001}
    rendered = password_login_module._safe_response_error(payload)
    # 应该是 "登录失败，错误码：4001" 这种带文案的形式，而不是裸的 "4001"
    assert rendered != "4001"
    assert "4001" in rendered


def test_extract_error_code_handles_nested_data() -> None:
    assert password_login_module._extract_error_code({"code": 100}) == 100
    assert password_login_module._extract_error_code({"data": {"code": 200}}) == 200
    assert password_login_module._extract_error_code({"code": ""}) is None
    assert password_login_module._extract_error_code({}) is None
    assert password_login_module._extract_error_code(None) is None


# ---------------------------------------------------------------------------
# _normalize_proxy
# ---------------------------------------------------------------------------


def test_normalize_proxy_none() -> None:
    assert password_login_module._normalize_proxy(None) is None


def test_normalize_proxy_str() -> None:
    assert password_login_module._normalize_proxy("http://127.0.0.1:7890") == {
        "server": "http://127.0.0.1:7890"
    }
    assert password_login_module._normalize_proxy("   ") is None


def test_normalize_proxy_proxyconfig() -> None:
    proxy = ProxyConfig(http="http://h", https="http://s", websocket="ws://w")
    # 优先使用 https
    assert password_login_module._normalize_proxy(proxy) == {"server": "http://s"}

    proxy_http_only = ProxyConfig(http="http://only-http")
    assert password_login_module._normalize_proxy(proxy_http_only) == {"server": "http://only-http"}

    empty = ProxyConfig()
    assert password_login_module._normalize_proxy(empty) is None


def test_normalize_proxy_mapping() -> None:
    assert password_login_module._normalize_proxy(
        {"server": "http://s", "username": "u", "password": "p", "bypass": "*.example.com"}
    ) == {"server": "http://s", "username": "u", "password": "p", "bypass": "*.example.com"}

    # 兼容只给 http 字段
    assert password_login_module._normalize_proxy({"http": "http://h"}) == {"server": "http://h"}

    # 空字典 → None
    assert password_login_module._normalize_proxy({}) is None


# ---------------------------------------------------------------------------
# 头部 / 登录 body / WebSocket 帧解析
# ---------------------------------------------------------------------------


def test_update_from_headers_fills_missing_fields_only() -> None:
    credentials = {"person_uid": "existing", "device_id": None, "jwt_token": None}
    headers = {
        "oopz-person": "should-not-overwrite",
        "oopz-device-id": "device-from-header",
        "oopz-signature": "jwt-from-header",
        "oopz-app-version-number": "70001",
    }

    password_login_module._update_from_headers(credentials, headers)

    # 已有值不覆盖
    assert credentials["person_uid"] == "existing"
    assert credentials["device_id"] == "device-from-header"
    assert credentials["jwt_token"] == "jwt-from-header"
    # app_version 总是覆盖
    assert credentials["app_version"] == "70001"


def test_update_from_login_body_sets_device_id() -> None:
    credentials = {"device_id": None}
    password_login_module._update_from_login_body(
        credentials, json.dumps({"deviceId": "device-from-body"})
    )
    assert credentials["device_id"] == "device-from-body"


def test_update_from_login_body_handles_invalid_json() -> None:
    credentials = {"device_id": None}
    password_login_module._update_from_login_body(credentials, "not json")
    assert credentials["device_id"] is None

    password_login_module._update_from_login_body(credentials, None)
    assert credentials["device_id"] is None


# ---------------------------------------------------------------------------
# JWT 过期解析
# ---------------------------------------------------------------------------


def test_jwt_exp_info_for_valid_token() -> None:
    exp = int(time.time()) + 3600
    info = password_login_module._jwt_exp_info(_fake_jwt(exp))
    assert info["expires_in_seconds"] is not None
    assert info["expires_in_seconds"] > 0
    assert info["expired"] is False
    assert info["expires_at"]


def test_jwt_exp_info_for_expired_token() -> None:
    exp = int(time.time()) - 3600
    info = password_login_module._jwt_exp_info(_fake_jwt(exp))
    assert info["expires_in_seconds"] == 0
    assert info["expired"] is True


def test_jwt_exp_info_for_unparseable_token() -> None:
    info = password_login_module._jwt_exp_info("not-a-jwt")
    assert info == {"expires_at": "", "expires_in_seconds": None, "expired": False}


# ---------------------------------------------------------------------------
# _resolve_chromium_executable_path
# ---------------------------------------------------------------------------


def test_resolve_chromium_executable_path_returns_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("BOT_CHROMIUM_EXECUTABLE_PATH", raising=False)
    monkeypatch.delenv("CHROME_BIN", raising=False)
    assert password_login_module._resolve_chromium_executable_path(None) is None


def test_resolve_chromium_executable_path_falls_back_when_path_missing(monkeypatch) -> None:
    monkeypatch.delenv("BOT_CHROMIUM_EXECUTABLE_PATH", raising=False)
    monkeypatch.delenv("CHROME_BIN", raising=False)
    assert password_login_module._resolve_chromium_executable_path("/path/that/does/not/exist") is None


def test_resolve_chromium_executable_path_returns_existing_path(tmp_path) -> None:
    fake_exe = tmp_path / "chrome"
    fake_exe.write_text("not really chromium")
    assert (
        password_login_module._resolve_chromium_executable_path(str(fake_exe))
        == str(fake_exe)
    )
