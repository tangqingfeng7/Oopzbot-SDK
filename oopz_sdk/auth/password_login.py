"""通过 OOPZ 账号密码登录并提取 SDK 所需凭据。"""

from __future__ import annotations

import argparse
import asyncio
import base64
import getpass
import json
import logging
import os
import shlex
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from oopz_sdk.config.settings import OopzConfig, ProxyConfig
from oopz_sdk.exceptions.auth import OopzPasswordLoginError

logger = logging.getLogger(__name__)

OOPZ_WEB_LOGIN_URL = "https://web.oopz.cn/#/login"
LOGIN_API_PATH = "/client/v1/login/v2/login"
WS_EVENT_AUTH = 253

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on", "y", "t"})


def truthy_env(value: str | None) -> bool:
    """常见的「真值」环境变量判断：`1` / `true` / `yes` / `on` 都视为 True。"""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_ENV_VALUES


_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--autoplay-policy=no-user-gesture-required",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-crash-reporter",
    "--disable-crashpad",
]


@dataclass(frozen=True, slots=True)
class OopzLoginCredentials:
    """一次 OOPZ 登录后提取到的 SDK 凭据。"""

    device_id: str
    person_uid: str
    jwt_token: str
    private_key_pem: str
    app_version: str = ""
    expires_at: str = ""
    expires_in_seconds: int | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "OopzLoginCredentials":
        """从字典创建凭据对象，兼容 `private_key` 和 `private_key_pem` 两种键名。"""
        private_key = data.get("private_key_pem") or data.get("private_key")
        payload = _jwt_exp_info(str(data.get("jwt_token") or ""))
        return cls(
            device_id=_required_text(data.get("device_id"), "device_id"),
            person_uid=_required_text(data.get("person_uid"), "person_uid"),
            jwt_token=_required_text(data.get("jwt_token"), "jwt_token"),
            private_key_pem=_required_text(private_key, "private_key"),
            app_version=str(data.get("app_version") or ""),
            expires_at=str(payload.get("expires_at") or ""),
            expires_in_seconds=payload.get("expires_in_seconds"),
        )

    def to_config(self, **overrides: Any) -> OopzConfig:
        """转换为 `OopzConfig`，可通过关键字参数覆盖默认配置。"""
        values: dict[str, Any] = {
            "device_id": self.device_id,
            "person_uid": self.person_uid,
            "jwt_token": self.jwt_token,
            "private_key": self.private_key_pem,
        }
        if self.app_version:
            values["app_version"] = self.app_version
        values.update(overrides)
        return OopzConfig(**values)

    @classmethod
    def from_env(cls, prefix: str = "OOPZ_") -> "OopzLoginCredentials":
        """从环境变量读取凭据。"""
        return cls.from_mapping(
            {
                "device_id": os.environ.get(f"{prefix}DEVICE_ID"),
                "person_uid": os.environ.get(f"{prefix}PERSON_UID"),
                "jwt_token": os.environ.get(f"{prefix}JWT_TOKEN"),
                "private_key": os.environ.get(f"{prefix}PRIVATE_KEY"),
                "app_version": os.environ.get(f"{prefix}APP_VERSION", ""),
            }
        )

    def to_dict(self, *, include_private_key: bool = True) -> dict[str, Any]:
        """转换为适合保存的字典。"""
        data: dict[str, Any] = {
            "device_id": self.device_id,
            "person_uid": self.person_uid,
            "jwt_token": self.jwt_token,
            "app_version": self.app_version,
        }
        if include_private_key:
            data["private_key"] = self.private_key_pem
        if self.expires_at:
            data["expires_at"] = self.expires_at
        if self.expires_in_seconds is not None:
            data["expires_in_seconds"] = self.expires_in_seconds
        return data

    def to_env(self, prefix: str = "OOPZ_") -> dict[str, str]:
        """转换为环境变量字典。"""
        data = {
            f"{prefix}DEVICE_ID": self.device_id,
            f"{prefix}PERSON_UID": self.person_uid,
            f"{prefix}JWT_TOKEN": self.jwt_token,
            f"{prefix}PRIVATE_KEY": self.private_key_pem,
        }
        if self.app_version:
            data[f"{prefix}APP_VERSION"] = self.app_version
        return data

    def masked(self) -> dict[str, Any]:
        """返回脱敏摘要，便于日志或界面展示。"""
        return {
            "device_id": _mask(self.device_id),
            "person_uid": _mask(self.person_uid),
            "jwt_token": _mask(self.jwt_token, keep=10),
            "private_key": bool(self.private_key_pem),
            "app_version": self.app_version,
            "expires_at": self.expires_at,
            "expires_in_seconds": self.expires_in_seconds,
        }

    def __repr__(self) -> str:
        # 默认 dataclass __repr__ 会把 jwt_token / private_key_pem 完整打出来，
        # 走脱敏摘要避免凭据泄漏到日志或异常回溯。
        masked = self.masked()
        fields = ", ".join(f"{k}={v!r}" for k, v in masked.items())
        return f"OopzLoginCredentials({fields})"


def save_credentials_json(credentials: OopzLoginCredentials, path: str | os.PathLike[str]) -> Path:
    """把凭据保存为 UTF-8 JSON 文件。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(credentials.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def load_credentials_json(path: str | os.PathLike[str]) -> OopzLoginCredentials:
    """从 UTF-8 JSON 文件读取凭据。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise OopzPasswordLoginError("凭据 JSON 必须是对象")
    return OopzLoginCredentials.from_mapping(data)


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise OopzPasswordLoginError(f"{field_name} is required")
    return text


def _mask(value: str | None, keep: int = 4) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= keep * 2:
        return text[:keep] + "***"
    return f"{text[:keep]}***{text[-keep:]}"


def _jwt_payload(token: str) -> dict[str, Any]:
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode("utf-8")))
    except Exception:
        return {}


def _jwt_exp_info(token: str) -> dict[str, Any]:
    payload = _jwt_payload(token)
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return {"expires_at": "", "expires_in_seconds": None, "expired": False}
    now = time.time()
    return {
        "expires_at": datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(),
        "expires_in_seconds": max(0, int(exp - now)),
        "expired": exp <= now,
    }


def _extract_error_code(payload: Any) -> int | str | None:
    if not isinstance(payload, dict):
        return None
    code = payload.get("code")
    if code in (None, ""):
        data = payload.get("data")
        if isinstance(data, dict):
            code = data.get("code")
    if code in (None, ""):
        return None
    return code


def _safe_response_error(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "登录接口返回异常"
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    for source in (payload, data):
        for key in ("message", "msg", "error", "errorMessage"):
            value = source.get(key)
            if value:
                return str(value)
    code = _extract_error_code(payload)
    if code not in (None, ""):
        return f"登录失败，错误码：{code}"
    return "登录失败，请检查账号密码或风控验证"


def _update_from_headers(credentials: dict[str, Any], headers: Mapping[str, str]) -> None:
    if headers.get("oopz-person") and not credentials.get("person_uid"):
        credentials["person_uid"] = headers["oopz-person"]
    if headers.get("oopz-device-id") and not credentials.get("device_id"):
        credentials["device_id"] = headers["oopz-device-id"]
    if headers.get("oopz-signature") and not credentials.get("jwt_token"):
        credentials["jwt_token"] = headers["oopz-signature"]
    if headers.get("oopz-app-version-number"):
        credentials["app_version"] = headers["oopz-app-version-number"]


def _update_from_login_body(credentials: dict[str, Any], post_data: str | None) -> None:
    if not post_data:
        return
    try:
        body = json.loads(post_data)
    except Exception:
        return
    if isinstance(body, dict) and body.get("deviceId") and not credentials.get("device_id"):
        credentials["device_id"] = body["deviceId"]


def _normalize_proxy(proxy: ProxyConfig | Mapping[str, Any] | str | None) -> dict[str, Any] | None:
    if proxy is None:
        return None
    if isinstance(proxy, str):
        return {"server": proxy} if proxy.strip() else None
    if isinstance(proxy, ProxyConfig):
        server = proxy.https or proxy.http or proxy.websocket
        return {"server": server} if server else None
    server = proxy.get("server") or proxy.get("https") or proxy.get("http") or proxy.get("websocket")
    if not server:
        return None
    normalized = {"server": str(server)}
    for key in ("username", "password", "bypass"):
        if proxy.get(key):
            normalized[key] = str(proxy[key])
    return normalized


def _resolve_chromium_executable_path(path: str | os.PathLike[str] | None) -> str | None:
    raw = str(path or os.environ.get("BOT_CHROMIUM_EXECUTABLE_PATH") or os.environ.get("CHROME_BIN") or "").strip()
    if not raw:
        return None
    if Path(raw).exists():
        return raw
    logger.warning("指定的 Chromium 路径不存在，回退到 Playwright 默认浏览器: %s", raw)
    return None


def _browser_args(crash_dir: Path, extra_args: list[str] | tuple[str, ...] | None) -> list[str]:
    args = list(_BROWSER_ARGS)
    crash_arg = f"--crash-dumps-dir={crash_dir}"
    if crash_arg not in args:
        args.append(crash_arg)
    for arg in extra_args or ():
        if arg not in args:
            args.append(arg)
    return args


def _credentials_complete(credentials: Mapping[str, Any]) -> bool:
    return all(credentials.get(key) for key in ("person_uid", "device_id", "jwt_token"))


def _coerce_credentials(credentials: Mapping[str, Any]) -> OopzLoginCredentials:
    missing = [
        key
        for key in ("person_uid", "device_id", "jwt_token", "private_key_pem")
        if not credentials.get(key)
    ]
    if missing:
        raise OopzPasswordLoginError("登录成功但未捕获完整凭据: " + ", ".join(missing))
    return OopzLoginCredentials.from_mapping(
        {
            "person_uid": credentials.get("person_uid"),
            "device_id": credentials.get("device_id"),
            "jwt_token": credentials.get("jwt_token"),
            "private_key": credentials.get("private_key_pem"),
            "app_version": credentials.get("app_version") or "",
        }
    )


# 页面加载前注入：让 OOPZ Web 端生成或导入的签名私钥可导出。
JS_CRYPTO_HOOK = """
(() => {
    window.__oopz_captured_pem = null;
    window.__oopz_key_events = [];

    const _subtle = crypto.subtle;
    const _importKey   = _subtle.importKey.bind(_subtle);
    const _generateKey = _subtle.generateKey.bind(_subtle);
    const _sign        = _subtle.sign.bind(_subtle);
    const _exportKey   = _subtle.exportKey.bind(_subtle);

    async function exportAsPem(key) {
        try {
            const ab    = await _exportKey('pkcs8', key);
            const bytes = new Uint8Array(ab);
            let bin = '';
            for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
            const b64   = btoa(bin);
            const lines = b64.match(/.{1,64}/g) || [];
            return '-----BEGIN PRIVATE KEY-----\\n' + lines.join('\\n') + '\\n-----END PRIVATE KEY-----';
        } catch (e) {
            window.__oopz_key_events.push({action: 'export_failed', error: e.message});
            return null;
        }
    }

    crypto.subtle.importKey = async function(format, keyData, algorithm, extractable, keyUsages) {
        const isSignKey = keyUsages && (keyUsages.includes('sign'));
        if (isSignKey) extractable = true;

        const key = await _importKey(format, keyData, algorithm, extractable, keyUsages);

        if (key && key.type === 'private') {
            window.__oopz_key_events.push({action: 'importKey', format, extractable: key.extractable});
            if (!window.__oopz_captured_pem && key.extractable) {
                window.__oopz_captured_pem = await exportAsPem(key);
            }
        }
        return key;
    };

    crypto.subtle.generateKey = async function(algorithm, extractable, keyUsages) {
        const isSignKey = keyUsages && (keyUsages.includes('sign'));
        if (isSignKey) extractable = true;

        const result = await _generateKey(algorithm, extractable, keyUsages);
        const pk = result && result.privateKey ? result.privateKey
                 : (result && result.type === 'private') ? result : null;

        if (pk) {
            window.__oopz_key_events.push({action: 'generateKey', extractable: pk.extractable});
            if (!window.__oopz_captured_pem && pk.extractable) {
                window.__oopz_captured_pem = await exportAsPem(pk);
            }
        }
        return result;
    };

    crypto.subtle.sign = async function(algorithm, key, data) {
        if (key && key.type === 'private' && !window.__oopz_captured_pem) {
            window.__oopz_key_events.push({action: 'sign', extractable: key.extractable});
            if (key.extractable) {
                window.__oopz_captured_pem = await exportAsPem(key);
            }
        }
        return _sign(algorithm, key, data);
    };
})();
"""

JS_GET_CAPTURED = """
() => ({
    pem: window.__oopz_captured_pem || null,
    events: window.__oopz_key_events || [],
})
"""


# 当 Web Crypto 钩子未在本次会话期间被触发（例如 OOPZ 把 RSA 私钥缓存在 IndexedDB
# 里、reload 后没有再次走 importKey/generateKey），需要兜底扫一遍浏览器存储。
# 与 script/credential_tool.py 中的 JS_SCAN_STORAGE 保持等价能力。
JS_SCAN_STORAGE_FOR_KEY = """
async () => {
    const found = [];

    function tryExtractFromValue(value) {
        if (!value) return null;
        if (typeof value === 'string') {
            const m = value.match(
                /-----BEGIN[\\s\\S]*?PRIVATE KEY-----[\\s\\S]*?-----END[\\s\\S]*?PRIVATE KEY-----/
            );
            if (m) return m[0].replace(/\\\\n/g, '\\n');
        }
        if (typeof value === 'object') {
            if (value.kty === 'RSA' && value.d) {
                return {jwk: value};
            }
            for (const v of Object.values(value)) {
                const sub = tryExtractFromValue(v);
                if (sub) return sub;
            }
        }
        return null;
    }

    async function jwkToPem(jwk) {
        try {
            const key = await crypto.subtle.importKey(
                'jwk', jwk,
                {name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256'},
                true, ['sign']
            );
            const ab = await crypto.subtle.exportKey('pkcs8', key);
            const bytes = new Uint8Array(ab);
            let bin = '';
            for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
            const b64 = btoa(bin);
            const lines = b64.match(/.{1,64}/g) || [];
            return '-----BEGIN PRIVATE KEY-----\\n' + lines.join('\\n') + '\\n-----END PRIVATE KEY-----';
        } catch (e) {
            return null;
        }
    }

    async function consider(extracted) {
        if (!extracted) return;
        if (typeof extracted === 'string') {
            found.push(extracted);
        } else if (extracted.jwk) {
            const pem = await jwkToPem(extracted.jwk);
            if (pem) found.push(pem);
        }
    }

    // ---- IndexedDB ----
    let databases = [];
    try { databases = await indexedDB.databases(); } catch (e) {}
    for (const dbInfo of databases) {
        if (!dbInfo.name) continue;
        try {
            const db = await new Promise((resolve) => {
                const req = indexedDB.open(dbInfo.name);
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => resolve(null);
                req.onblocked = () => resolve(null);
            });
            if (!db) continue;
            for (const store of Array.from(db.objectStoreNames)) {
                try {
                    const tx = db.transaction(store, 'readonly');
                    const os = tx.objectStore(store);
                    const items = await new Promise((resolve) => {
                        const req = os.getAll();
                        req.onsuccess = () => resolve(req.result || []);
                        req.onerror = () => resolve([]);
                    });
                    for (const item of items) {
                        await consider(tryExtractFromValue(item));
                        if (found.length) break;
                    }
                } catch (e) {}
                if (found.length) break;
            }
            db.close();
        } catch (e) {}
        if (found.length) break;
    }

    // ---- localStorage / sessionStorage ----
    if (!found.length) {
        for (const storage of [localStorage, sessionStorage]) {
            for (let i = 0; i < storage.length; i++) {
                const key = storage.key(i);
                const raw = storage.getItem(key) || '';
                let parsed = null;
                try { parsed = JSON.parse(raw); } catch (e) { parsed = raw; }
                await consider(tryExtractFromValue(parsed));
                if (found.length) break;
            }
            if (found.length) break;
        }
    }

    return found[0] || null;
}
"""

JS_CLEAR_STORAGE = """
async () => {
    const deleted = [];
    try {
        try { localStorage.clear(); } catch (e) {}
        try { sessionStorage.clear(); } catch (e) {}
        const dbs = await indexedDB.databases();
        for (const db of dbs) {
            if (!db.name) continue;
            await new Promise((resolve) => {
                const req = indexedDB.deleteDatabase(db.name);
                req.onsuccess = () => resolve();
                req.onerror = () => resolve();
                req.onblocked = () => resolve();
            });
            deleted.push(db.name);
        }
    } catch (e) {}
    return deleted;
}
"""


async def _poll_private_key(page: Any, credentials: dict[str, Any], seconds: float) -> None:
    deadline = time.monotonic() + max(0.1, seconds)
    while time.monotonic() < deadline:
        try:
            captured = await page.evaluate(JS_GET_CAPTURED)
            pem = (captured or {}).get("pem")
            if pem:
                credentials["private_key_pem"] = pem
                return
        except Exception:
            logger.debug("读取 OOPZ 私钥捕获状态失败", exc_info=True)
        await asyncio.sleep(0.5)


async def _scan_storage_for_key(page: Any, credentials: dict[str, Any]) -> None:
    """Web Crypto 钩子未触发时，扫一遍 IndexedDB / localStorage 兜底。"""
    if credentials.get("private_key_pem"):
        return
    try:
        pem = await page.evaluate(JS_SCAN_STORAGE_FOR_KEY)
    except Exception:
        logger.debug("扫描 OOPZ 浏览器存储以提取私钥失败", exc_info=True)
        return
    if pem:
        credentials["private_key_pem"] = pem
        logger.info("OOPZ 登录私钥经存储扫描兜底捕获成功")


async def _clear_cached_keys_and_retry(page: Any, credentials: dict[str, Any]) -> None:
    try:
        deleted = await page.evaluate(JS_CLEAR_STORAGE)
        logger.info("OOPZ 登录私钥未捕获，已清理浏览器本地状态后重试: %s", deleted)
        await page.reload(wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await _poll_private_key(page, credentials, 8)
        await _scan_storage_for_key(page, credentials)
    except Exception:
        logger.debug("清理浏览器本地状态重试失败", exc_info=True)


async def _open_clean_login_page(context: Any, page: Any) -> None:
    """清理旧网页登录态，确保本次使用传入的账号密码。"""
    try:
        await context.clear_cookies()
    except Exception:
        logger.debug("清理 OOPZ Cookie 失败", exc_info=True)

    await page.goto(OOPZ_WEB_LOGIN_URL, wait_until="domcontentloaded")
    try:
        await page.evaluate(JS_CLEAR_STORAGE)
    except Exception:
        logger.debug("清理 OOPZ 本地登录状态失败", exc_info=True)
    await page.goto(OOPZ_WEB_LOGIN_URL, wait_until="domcontentloaded")


async def _fill_password_login(page: Any, phone: str, password: str) -> None:
    # OOPZ Web 是 Flutter Canvas，坐标点击比 DOM selector 更稳定。
    await page.mouse.click(880, 610)
    await page.wait_for_timeout(1000)
    await page.mouse.click(760, 354)
    await page.keyboard.press("Control+A")
    await page.keyboard.type(phone, delay=15)
    await page.mouse.click(760, 440)
    await page.keyboard.press("Control+A")
    await page.keyboard.type(password, delay=15)
    await page.mouse.click(882, 532)


async def login_with_password(
    phone: str,
    password: str,
    *,
    timeout: float = 90,
    headless: bool = True,
    browser_data_dir: str | os.PathLike[str] | None = None,
    chromium_executable_path: str | os.PathLike[str] | None = None,
    proxy: ProxyConfig | Mapping[str, Any] | str | None = None,
    extra_browser_args: list[str] | tuple[str, ...] | None = None,
) -> OopzLoginCredentials:
    """通过 Chromium 自动登录 OOPZ，并返回 SDK 可直接使用的凭据。"""
    phone = str(phone or "").strip()
    password = str(password or "")
    if not phone or not password:
        raise OopzPasswordLoginError("账号和密码不能为空")

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise OopzPasswordLoginError("当前环境缺少 Playwright，请先安装 oopz-sdk 的完整依赖") from exc

    credentials: dict[str, Any] = {
        "person_uid": None,
        "device_id": None,
        "jwt_token": None,
        "private_key_pem": None,
        "app_version": None,
    }
    login_done = asyncio.Event()
    login_error: dict[str, Any] = {}

    def mark_done_when_ready() -> None:
        if _credentials_complete(credentials):
            login_done.set()

    async def on_response(response: Any) -> None:
        if LOGIN_API_PATH not in response.url:
            return
        try:
            payload = await response.json()
        except Exception:
            payload = None
        if not isinstance(payload, dict) or not payload.get("status"):
            login_error["message"] = _safe_response_error(payload)
            login_error["code"] = _extract_error_code(payload)
            login_error["payload"] = payload
            login_done.set()
            return
        data = payload.get("data") or {}
        if isinstance(data, dict):
            if data.get("uid"):
                credentials["person_uid"] = data["uid"]
            if data.get("signature"):
                credentials["jwt_token"] = data["signature"]
        mark_done_when_ready()

    def on_request(request: Any) -> None:
        try:
            _update_from_headers(credentials, request.headers)
            if LOGIN_API_PATH in request.url:
                _update_from_login_body(credentials, request.post_data)
            mark_done_when_ready()
        except Exception:
            logger.debug("解析 OOPZ 登录请求失败", exc_info=True)

    def on_websocket(ws: Any) -> None:
        def on_frame(payload: str) -> None:
            try:
                data = json.loads(payload)
                if data.get("event") != WS_EVENT_AUTH:
                    return
                body = json.loads(data.get("body", "{}"))
                if body.get("person") and not credentials.get("person_uid"):
                    credentials["person_uid"] = body["person"]
                if body.get("deviceId") and not credentials.get("device_id"):
                    credentials["device_id"] = body["deviceId"]
                if body.get("signature") and not credentials.get("jwt_token"):
                    credentials["jwt_token"] = body["signature"]
                mark_done_when_ready()
            except Exception:
                logger.debug("解析 OOPZ WebSocket 鉴权帧失败", exc_info=True)

        ws.on("framesent", on_frame)

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    profile_path: Path
    if browser_data_dir is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="oopz-sdk-login-")
        profile_path = Path(temp_dir.name)
    else:
        profile_path = Path(browser_data_dir)
        profile_path.mkdir(parents=True, exist_ok=True)

    runtime_path = profile_path / ".runtime"
    crash_dir = runtime_path / "crashpad"
    crash_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with async_playwright() as p:
            launch_kwargs: dict[str, Any] = {
                "user_data_dir": str(profile_path),
                "headless": headless,
                "viewport": {"width": 1280, "height": 900},
                "locale": "zh-CN",
                "args": _browser_args(crash_dir, extra_browser_args),
            }
            executable_path = _resolve_chromium_executable_path(chromium_executable_path)
            if executable_path:
                launch_kwargs["executable_path"] = executable_path
            browser_proxy = _normalize_proxy(proxy)
            if browser_proxy:
                launch_kwargs["proxy"] = browser_proxy

            try:
                context = await p.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as exc:
                message = str(exc)
                if "Executable doesn't exist" in message or "playwright install" in message:
                    raise OopzPasswordLoginError("未找到 Playwright Chromium，请运行: python -m playwright install chromium") from exc
                raise

            try:
                page = context.pages[0] if context.pages else await context.new_page()
                page.set_default_timeout(30000)
                await page.add_init_script(JS_CRYPTO_HOOK)
                page.on("request", on_request)
                page.on("websocket", on_websocket)
                page.on("response", lambda response: asyncio.create_task(on_response(response)))

                await _open_clean_login_page(context, page)
                await page.wait_for_timeout(6500)
                await _fill_password_login(page, phone, password)

                try:
                    await asyncio.wait_for(login_done.wait(), timeout=timeout)
                except asyncio.TimeoutError as exc:
                    raise OopzPasswordLoginError("等待 OOPZ 登录响应超时") from exc

                if login_error.get("message"):
                    raise OopzPasswordLoginError(
                        login_error["message"],
                        code=login_error.get("code"),
                        payload=login_error.get("payload"),
                    )

                await _poll_private_key(page, credentials, 10)
                if not credentials.get("private_key_pem"):
                    await _scan_storage_for_key(page, credentials)
                if not credentials.get("private_key_pem"):
                    await _clear_cached_keys_and_retry(page, credentials)
            finally:
                await context.close()
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    return _coerce_credentials(credentials)


def login_with_password_sync(phone: str, password: str, **kwargs: Any) -> OopzLoginCredentials:
    """同步包装，便于脚本或一次性工具调用。"""
    return asyncio.run(login_with_password(phone, password, **kwargs))


def _powershell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell_env_lines(credentials: OopzLoginCredentials) -> str:
    env = credentials.to_env()
    lines = [
        f"$env:OOPZ_DEVICE_ID = {_powershell_single_quote(env['OOPZ_DEVICE_ID'])}",
        f"$env:OOPZ_PERSON_UID = {_powershell_single_quote(env['OOPZ_PERSON_UID'])}",
        f"$env:OOPZ_JWT_TOKEN = {_powershell_single_quote(env['OOPZ_JWT_TOKEN'])}",
    ]
    if env.get("OOPZ_APP_VERSION"):
        lines.append(f"$env:OOPZ_APP_VERSION = {_powershell_single_quote(env['OOPZ_APP_VERSION'])}")
    lines.append("$env:OOPZ_PRIVATE_KEY = @'\n" + env["OOPZ_PRIVATE_KEY"].strip() + "\n'@")
    return "\n".join(lines)


def _bash_env_lines(credentials: OopzLoginCredentials) -> str:
    return "\n".join(
        f"export {key}={shlex.quote(value)}"
        for key, value in credentials.to_env().items()
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="使用 OOPZ 账号密码登录并提取 SDK 凭据")
    parser.add_argument("--phone", default="", help="OOPZ 登录账号/手机号；不传则交互输入")
    parser.add_argument("--password", default="", help="OOPZ 登录密码；不传则安全输入，命令历史可能记录明文")
    parser.add_argument("--timeout", type=float, default=90, help="等待登录响应的秒数")
    parser.add_argument("--headful", action="store_true", help="显示浏览器窗口，便于处理验证或调试")
    parser.add_argument("--browser-data-dir", default="", help="自定义浏览器 profile 目录")
    parser.add_argument("--chromium-executable-path", default="", help="自定义 Chromium/Chrome 可执行文件路径")
    parser.add_argument("--proxy", default="", help="浏览器代理，例如 http://127.0.0.1:7890")
    parser.add_argument("--output", default="", help="保存原始凭据 JSON 的路径；文件含真实 token 和私钥")
    parser.add_argument("--print-env", choices=("powershell", "bash"), default="", help="打印可直接设置的环境变量")
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    phone = args.phone.strip() or input("OOPZ 账号/手机号: ").strip()
    password = args.password or getpass.getpass("OOPZ 密码: ")
    credentials = login_with_password_sync(
        phone,
        password,
        timeout=args.timeout,
        headless=not args.headful,
        browser_data_dir=args.browser_data_dir or None,
        chromium_executable_path=args.chromium_executable_path or None,
        proxy=args.proxy or None,
    )

    print(json.dumps(credentials.masked(), ensure_ascii=False, indent=2))
    if args.output:
        output = save_credentials_json(credentials, args.output)
        print(f"已保存凭据 JSON: {output}")
    if args.print_env == "powershell":
        print(_powershell_env_lines(credentials))
    elif args.print_env == "bash":
        print(_bash_env_lines(credentials))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
