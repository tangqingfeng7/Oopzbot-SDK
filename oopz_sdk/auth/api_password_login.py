from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Any, Mapping

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from oopz_sdk.auth._builtin_login_bundle import (
    get_client_password_modulus,
    get_client_signing_key,
)
from oopz_sdk.auth.password_login import OopzLoginCredentials
from oopz_sdk.exceptions.auth import OopzPasswordLoginError


BASE_URL = "https://gateway.oopz.cn"
LOGIN_PATH = "/client/v1/login/v2/login"
LOGIN_URL = BASE_URL + LOGIN_PATH

CLIENT_VERSION = "0.73.817"
APP_VERSION_NUMBER = "73817"
OOPZ_PLATFORM = "windows"
OOPZ_CHANNEL = "Web"
PUBLIC_E = "AQAB"


def _compact_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _now_ms() -> str:
    return str(int(time.time() * 1000))


def _normalize_private_key(pem: str) -> str:
    pem = pem.strip()

    if (pem.startswith("'") and pem.endswith("'")) or (
        pem.startswith('"') and pem.endswith('"')
    ):
        pem = pem[1:-1]

    pem = pem.replace("\\r\\n", "\n")
    pem = pem.replace("\\n", "\n")
    pem = pem.replace("\r\n", "\n")

    return pem.strip()


def _load_private_key(private_key_pem: str):
    private_key_pem = _normalize_private_key(private_key_pem)

    if not private_key_pem.startswith("-----BEGIN PRIVATE KEY-----"):
        raise OopzPasswordLoginError("内置登录签名私钥格式错误")

    if "-----END PRIVATE KEY-----" not in private_key_pem:
        raise OopzPasswordLoginError("内置登录签名私钥缺少 END PRIVATE KEY")

    try:
        return serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )
    except Exception as exc:
        raise OopzPasswordLoginError(f"无法加载内置登录签名私钥: {exc}") from exc


def _b64url_decode_int(value: str) -> int:
    value += "=" * ((4 - len(value) % 4) % 4)
    raw = base64.urlsafe_b64decode(value.encode("utf-8"))
    return int.from_bytes(raw, "big")


def _load_rsa_public_key_from_jwk(n: str, e: str = "AQAB"):
    public_numbers = rsa.RSAPublicNumbers(
        e=_b64url_decode_int(e),
        n=_b64url_decode_int(n),
    )
    return public_numbers.public_key()


def _encrypt_password_code(password: str, public_n: str) -> str:
    public_key = _load_rsa_public_key_from_jwk(public_n, PUBLIC_E)

    encrypted = public_key.encrypt(
        password.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    return base64.b64encode(encrypted).decode("utf-8")


def _build_oopz_sign(
    *,
    path: str,
    body: str,
    oopz_time: str,
    private_key_pem: str,
) -> str:
    digest = hashlib.md5((path + body).encode("utf-8")).hexdigest()
    sign_input = (digest + oopz_time).encode("utf-8")

    private_key = _load_private_key(private_key_pem)

    signature = private_key.sign(
        sign_input,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    return base64.b64encode(signature).decode("utf-8")


def _build_password_login_body(
    *,
    phone: str,
    password: str,
    device_id: str,
    public_n: str,
) -> str:
    code = _encrypt_password_code(password, public_n)

    payload = {
        "auto": True,
        "code": code,
        "loginType": "PASSWORD",
        "phone": phone,
        "autoRegister": True,
        "deviceId": device_id,
        "deviceRam": "TBD",
        "deviceProcessor": "0",
        "loggedIn": device_id,
        "osEdition": "web",
        "osVersion": "web/BrowserName.chrome",
        "resolution": "TBD",
        "graphics": "TBD",
        "clientVersion": CLIENT_VERSION,
    }

    return _compact_json(payload)


def _build_headers(
    *,
    device_id: str,
    body: str,
    private_key_pem: str,
) -> dict[str, str]:
    oopz_time = _now_ms()

    headers = {"Accept": "*/*", "Content-Type": "application/json;charset=utf-8",
               "Oopz-App-Version-Number": APP_VERSION_NUMBER, "Oopz-Channel": OOPZ_CHANNEL, "Oopz-Device-Id": device_id,
               "Oopz-Platform": OOPZ_PLATFORM, "Oopz-Request-Id": str(uuid.uuid4()), "Oopz-Time": oopz_time,
               "Oopz-Web": "true", "Origin": "https://web.oopz.cn", "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0.0.0 Safari/537.36"
        ), "Oopz-Sign": _build_oopz_sign(
            path=LOGIN_PATH,
            body=body,
            oopz_time=oopz_time,
            private_key_pem=private_key_pem,
        )}

    return headers


def _extract_login_error(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "登录接口返回异常"

    data = payload.get("data")
    if not isinstance(data, dict):
        data = {}

    for source in (payload, data):
        for key in ("message", "msg", "error", "errorMessage", "reason"):
            value = source.get(key)
            if value:
                return str(value)

    code = payload.get("code") or data.get("code")
    if code not in (None, ""):
        return f"登录失败，错误码：{code}"

    return "登录失败，请检查账号密码或风控验证"


def login_with_api_password(
    phone: str,
    password: str,
    *,
    device_id: str | None = None,
    timeout: float = 20,
) -> OopzLoginCredentials:
    phone = str(phone or "").strip()
    password = str(password or "")

    if not phone or not password:
        raise OopzPasswordLoginError("账号和密码不能为空")

    device_id = str(device_id or uuid.uuid4())

    public_n = get_client_password_modulus()
    private_key_pem = get_client_signing_key()

    body = _build_password_login_body(
        phone=phone,
        password=password,
        device_id=device_id,
        public_n=public_n,
    )

    headers = _build_headers(
        device_id=device_id,
        body=body,
        private_key_pem=private_key_pem,
    )

    try:
        response = requests.post(
            LOGIN_URL,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise OopzPasswordLoginError(f"OOPZ 登录请求失败: {exc}") from exc

    try:
        payload = response.json()
    except Exception as exc:
        raise OopzPasswordLoginError(
            f"OOPZ 登录接口返回非 JSON 响应: HTTP {response.status_code}"
        ) from exc

    if response.status_code >= 400 or not isinstance(payload, dict) or not payload.get("status"):
        raise OopzPasswordLoginError(
            _extract_login_error(payload),
            payload=payload,
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise OopzPasswordLoginError("登录成功但响应 data 格式异常", payload=payload)

    person_uid = data.get("uid")
    jwt_token = data.get("signature")

    if not person_uid:
        raise OopzPasswordLoginError("登录成功但未返回 uid", payload=payload)

    if not jwt_token:
        raise OopzPasswordLoginError("登录成功但未返回 signature", payload=payload)

    return OopzLoginCredentials.from_mapping(
        {
            "device_id": device_id,
            "person_uid": person_uid,
            "jwt_token": jwt_token,
            "private_key": private_key_pem,
            "app_version": APP_VERSION_NUMBER,
            "expires_at": data.get("signatureNearExpired")
        }
    )