import asyncio
import io
import oopz_sdk
import oopz_sdk.client as oopz_client
import oopz_sdk.services.media as oopz_media_service
import oopz_sdk.transport.http as oopz_http_transport
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from PIL import Image
from pydantic import ValidationError

from oopz_sdk import OopzRESTClient, models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.client.bot import OopzBot
from oopz_sdk.client.ws import OopzWSClient
from oopz_sdk.config import OopzConfig
from oopz_sdk.config.constants import EVENT_PRIVATE_MESSAGE
from oopz_sdk.exceptions import OopzApiError, OopzConnectionError, OopzParseError, OopzRateLimitError
from oopz_sdk.events.context import EventContext
from oopz_sdk.events.dispatcher import EventDispatcher
from oopz_sdk.events.parser import EventParser
from oopz_sdk.events.registry import EventRegistry
from oopz_sdk.models.event import MessageEvent
from oopz_sdk.models.segment import Image as ImageSegment
from oopz_sdk.services import BaseService
from oopz_sdk.services.area import AreaService
from oopz_sdk.services.channel import Channel
from oopz_sdk.services.media import Media
from oopz_sdk.services.member import Member
from oopz_sdk.services.message import Message
from oopz_sdk.services.moderation import Moderation
from oopz_sdk.transport.http import HttpTransport

from tests._oopz_sdk_test_support import _FakeResponse, _make_config, _make_private_key, _run

def test_oopz_sdk_config_requires_private_key():
    with pytest.raises(ValueError):
        OopzConfig(
            device_id="device",
            person_uid="person",
            jwt_token="jwt",
            private_key=None,
        )


def test_oopz_sdk_signer_from_pem_does_not_mutate_original_config():
    original_key = _make_private_key()
    replacement_key = _make_private_key()
    pem = replacement_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    config = _make_config(private_key=original_key)

    signer = Signer.from_pem(pem, config)

    assert config.private_key is original_key
    assert signer.private_key is not original_key


def test_oopz_sdk_response_helper_treats_explicit_failure_as_failure():
    assert oopz_sdk.is_success_payload({"status": False, "code": 0}) is False

    with pytest.raises(OopzApiError, match="helper rejected"):
        oopz_sdk.ensure_success_payload(
            _FakeResponse(200, payload={"status": False, "code": 0, "message": "helper rejected"}),
            "fallback message",
        )


def test_oopz_sdk_model_error_supports_models_without_response_field():
    service = BaseService(
        _make_config(),
        SimpleNamespace(session=None),
        signer=None,
    )

    class _ModelWithoutResponse:
        def __init__(self, *, payload):
            self.payload = payload

    result = service._model_error(_ModelWithoutResponse, "boom", response=_FakeResponse(500))

    assert result.payload == {"error": "boom"}


def test_oopz_sdk_model_error_does_not_swallow_other_type_errors():
    service = BaseService(
        _make_config(),
        SimpleNamespace(session=None),
        signer=None,
    )

    class _ModelRaisesTypeError:
        def __init__(self, *, payload, response=None):
            if response is not None:
                raise TypeError("bad constructor")
            self.payload = payload

    with pytest.raises(TypeError, match="bad constructor"):
        service._model_error(_ModelRaisesTypeError, "boom", response=_FakeResponse(500))


def test_oopz_sdk_version_matches_package_version():
    from oopz_sdk import __version__

    assert __version__ == "0.5.0"
