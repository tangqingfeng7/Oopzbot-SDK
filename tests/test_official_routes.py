"""官方备用线路的配置与传输回归测试，全程使用离线替身。"""

import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from oopz_sdk import OopzConfig
from oopz_sdk.transport.ws import WebSocketTransport


class OfficialRouteConfigTest(unittest.TestCase):
    def test_default_route_is_unchanged(self):
        self.assertEqual(OopzConfig().ws_url, "wss://ws.oopz.cn")

    def test_known_gateways_select_matching_websocket(self):
        for suffix in ("", "1", "2", "-web1"):
            with self.subTest(suffix=suffix):
                config = OopzConfig(base_url=f" https://gateway{suffix}.oopz.cn/ ")
                self.assertEqual(config.base_url, f"https://gateway{suffix}.oopz.cn")
                self.assertEqual(config.ws_url, f"wss://ws{suffix}.oopz.cn")

    def test_explicit_websocket_route_wins(self):
        config = OopzConfig(
            base_url="https://gateway1.oopz.cn",
            ws_url=" wss://custom.example/ws ",
        )
        self.assertEqual(config.ws_url, "wss://custom.example/ws")

    def test_explicit_primary_websocket_is_not_rewritten(self):
        config = OopzConfig(
            base_url="https://gateway1.oopz.cn", ws_url="wss://ws.oopz.cn",
        )
        self.assertEqual(config.ws_url, "wss://ws.oopz.cn")

    def test_unknown_gateway_does_not_invent_a_hostname(self):
        for base_url in (
            "https://custom.example", "https://gateway1.oopz.cn.evil.example",
            "https://gateway1.oopz.cn/custom", "http://gateway1.oopz.cn",
        ):
            with self.subTest(base_url=base_url):
                self.assertEqual(OopzConfig(base_url=base_url).ws_url, "wss://ws.oopz.cn")

    def test_environment_route_applies_to_existing_credentials(self):
        with patch.dict(os.environ, {
            "OOPZ_LOGIN_METHOD": "credentials",
            "OOPZ_DEVICE_ID": "test-device", "OOPZ_PERSON_UID": "test-person",
            "OOPZ_JWT_TOKEN": "test-token", "OOPZ_PRIVATE_KEY": "test-key",
            "OOPZ_BASE_URL": " https://gateway1.oopz.cn/ ",
        }, clear=True):
            config = OopzConfig.from_env()
        self.assertEqual(config.ws_url, "wss://ws1.oopz.cn")

    def test_environment_route_supports_custom_prefix_and_explicit_ws(self):
        with patch.dict(os.environ, {
            "OOPZ_LOGIN_METHOD": "credentials",
            "TEST_DEVICE_ID": "test-device", "TEST_PERSON_UID": "test-person",
            "TEST_JWT_TOKEN": "test-token", "TEST_PRIVATE_KEY": "test-key",
            "TEST_BASE_URL": "https://gateway1.oopz.cn",
            "TEST_WS_URL": " wss://custom.example/ws ",
        }, clear=True):
            config = OopzConfig.from_env(prefix="TEST_")
        self.assertEqual(config.ws_url, "wss://custom.example/ws")

    def test_keyword_overrides_win_over_environment(self):
        with patch.dict(os.environ, {
            "OOPZ_LOGIN_METHOD": "credentials",
            "OOPZ_DEVICE_ID": "test-device", "OOPZ_PERSON_UID": "test-person",
            "OOPZ_JWT_TOKEN": "test-token", "OOPZ_PRIVATE_KEY": "test-key",
            "OOPZ_BASE_URL": "https://gateway1.oopz.cn",
            "OOPZ_WS_URL": "wss://ws1.oopz.cn",
        }, clear=True):
            config = OopzConfig.from_env(base_url="https://gateway2.oopz.cn", ws_url="")
        self.assertEqual(config.ws_url, "wss://ws2.oopz.cn")

    def test_environment_route_applies_after_password_login(self):
        credentials = SimpleNamespace(
            device_id="test-device", person_uid="test-person", jwt_token="test-token",
            private_key_pem="test-key", app_version="",
        )
        with (
            patch.dict(os.environ, {
                "OOPZ_LOGIN_METHOD": "password",
                "OOPZ_LOGIN_PHONE": "test-phone", "OOPZ_LOGIN_PASSWORD": "test-password",
                "OOPZ_BASE_URL": "https://gateway1.oopz.cn",
            }, clear=True),
            patch.object(OopzConfig, "_resolve_login_credentials",
                         AsyncMock(return_value=credentials)),
        ):
            config = asyncio.run(OopzConfig.from_env_async())
        self.assertEqual(config.ws_url, "wss://ws1.oopz.cn")


class OfficialRouteTransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_transport_connects_to_paired_route(self):
        config = OopzConfig(base_url="https://gateway1.oopz.cn")
        session = Mock(closed=False)
        session.ws_connect = AsyncMock(return_value=Mock(closed=False))
        transport = WebSocketTransport(config)
        with patch("oopz_sdk.transport.ws.aiohttp.ClientSession", return_value=session):
            await transport.connect()
        self.assertEqual(session.ws_connect.call_args.args[0], "wss://ws1.oopz.cn")


if __name__ == "__main__":
    unittest.main()
