import asyncio
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BROWSER_DATA_DIR = os.path.join(PROJECT_ROOT, ".oopz_capture_credentials")
OOPZ_WEB_URL = "https://web.oopz.cn"

WS_EVENT_AUTH = 253


def _is_jwt_expired(token: str) -> bool:
    """解码 JWT payload，检查 exp 是否已过期（不校验签名）"""
    try:
        import base64
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        exp = payload.get("exp")
        if exp is None:
            return False
        return exp <= time.time()
    except Exception:
        return False


def ensure_playwright():
    """确保 playwright 和 chromium 已安装"""
    try:
        from playwright.async_api import async_playwright  # noqa: F401
        return True
    except ImportError:
        print("[!] playwright 未安装，正在安装...")
        code1 = os.system(f'"{sys.executable}" -m pip install playwright')
        code2 = os.system(f'"{sys.executable}" -m playwright install chromium')
        print()
        if code1 != 0 or code2 != 0:
            print("[x] playwright 或 chromium 安装失败，请手动安装后重试。")
            return False
        try:
            from playwright.async_api import async_playwright  # noqa: F401
            return True
        except ImportError:
            print("[x] playwright 安装后仍不可用，请检查 Python 环境。")
            return False


# ---------------------------------------------------------------------------
# 页面加载前注入脚本：拦截 Web Crypto API，强制私钥可导出
# ---------------------------------------------------------------------------
# Oopz 网页端可能使用 Web Crypto API 生成/导入 RSA 密钥，
# 默认 extractable=false 导致无法从 IndexedDB 直接导出。
# 此脚本在页面加载前覆写 SubtleCrypto 原型方法，
# 将所有签名用途的密钥强制设为 extractable=true，
# 并在密钥生成/导入/首次签名时自动导出为 PKCS#8 PEM。
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# 从 IndexedDB / localStorage 搜索 RSA 私钥（全量扫描）
# ---------------------------------------------------------------------------

JS_SCAN_STORAGE = """
async () => {
    const results = [];

    // ---- IndexedDB ----
    let databases = [];
    try { databases = await indexedDB.databases(); } catch(e) {}

    for (const dbInfo of databases) {
        try {
            const db = await new Promise((resolve, reject) => {
                const req = indexedDB.open(dbInfo.name);
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => reject(req.error);
            });

            for (const storeName of db.objectStoreNames) {
                try {
                    const tx    = db.transaction(storeName, 'readonly');
                    const store = tx.objectStore(storeName);
                    const keys  = await new Promise((r, j) => {
                        const q = store.getAllKeys(); q.onsuccess = () => r(q.result); q.onerror = () => j(q.error);
                    });
                    const items = await new Promise((r, j) => {
                        const q = store.getAll(); q.onsuccess = () => r(q.result); q.onerror = () => j(q.error);
                    });

                    for (let i = 0; i < items.length; i++) {
                        const item = items[i];
                        const key  = keys[i];
                        const loc  = {db: dbInfo.name, store: storeName, key: String(key)};

                        if (!item) continue;

                        // --- CryptoKey / CryptoKeyPair ---
                        const pk = (item.privateKey instanceof CryptoKey) ? item.privateKey
                                 : (item instanceof CryptoKey && item.type === 'private') ? item
                                 : null;
                        if (pk) {
                            if (pk.extractable) {
                                try {
                                    const ab    = await crypto.subtle.exportKey('pkcs8', pk);
                                    const bytes = new Uint8Array(ab);
                                    let bin = '';
                                    for (let j = 0; j < bytes.length; j++) bin += String.fromCharCode(bytes[j]);
                                    const b64   = btoa(bin);
                                    const lines = b64.match(/.{1,64}/g) || [];
                                    const pem   = '-----BEGIN PRIVATE KEY-----\\n' + lines.join('\\n') + '\\n-----END PRIVATE KEY-----';
                                    results.push({type: 'CryptoKey-PKCS8', pem, ...loc});
                                } catch(e) {
                                    results.push({type: 'CryptoKey-ExportError', error: e.message, ...loc});
                                }
                            } else {
                                results.push({
                                    type: 'CryptoKey-NonExportable',
                                    algorithm: pk.algorithm ? pk.algorithm.name : 'unknown',
                                    usages: Array.from(pk.usages || []),
                                    ...loc
                                });
                            }
                            continue;
                        }

                        // --- PEM 明文字符串 ---
                        const str = typeof item === 'string' ? item : JSON.stringify(item || '');
                        if (str.includes('PRIVATE KEY')) {
                            const m = str.match(/-----BEGIN[\\s\\S]*?PRIVATE KEY-----[\\s\\S]*?-----END[\\s\\S]*?PRIVATE KEY-----/);
                            if (m) {
                                results.push({type: 'PEM-String', pem: m[0].replace(/\\\\n/g, '\\n'), ...loc});
                            }
                        }

                        // --- JWK 格式 ---
                        if (typeof item === 'object' && item.kty === 'RSA' && item.d) {
                            results.push({type: 'JWK', jwk: JSON.stringify(item), ...loc});
                        }

                        // --- 深层嵌套: 对象中可能包含 d/n/e 等 RSA 分量 ---
                        if (typeof item === 'object' && !Array.isArray(item)) {
                            for (const [vk, vv] of Object.entries(item)) {
                                if (vv && typeof vv === 'object' && vv.kty === 'RSA' && vv.d) {
                                    results.push({type: 'Nested-JWK', jwk: JSON.stringify(vv), field: vk, ...loc});
                                }
                                if (vv instanceof CryptoKey && vv.type === 'private') {
                                    if (vv.extractable) {
                                        try {
                                            const ab2 = await crypto.subtle.exportKey('pkcs8', vv);
                                            const b2  = new Uint8Array(ab2);
                                            let bin2 = '';
                                            for (let j = 0; j < b2.length; j++) bin2 += String.fromCharCode(b2[j]);
                                            const b642 = btoa(bin2);
                                            const l2   = b642.match(/.{1,64}/g) || [];
                                            const p2   = '-----BEGIN PRIVATE KEY-----\\n' + l2.join('\\n') + '\\n-----END PRIVATE KEY-----';
                                            results.push({type: 'Nested-CryptoKey', pem: p2, field: vk, ...loc});
                                        } catch(e) {}
                                    } else {
                                        results.push({type: 'Nested-CryptoKey-NonExportable', field: vk, ...loc});
                                    }
                                }
                            }
                        }
                    }
                } catch(e) {}
            }
            db.close();
        } catch(e) {}
    }

    // ---- localStorage + sessionStorage ----
    for (const storage of [localStorage, sessionStorage]) {
        const sName = storage === localStorage ? 'localStorage' : 'sessionStorage';
        for (let i = 0; i < storage.length; i++) {
            const lsKey = storage.key(i);
            const val   = storage.getItem(lsKey) || '';
            if (val.includes('PRIVATE KEY')) {
                const m = val.match(/-----BEGIN[\\s\\S]*?PRIVATE KEY-----[\\s\\S]*?-----END[\\s\\S]*?PRIVATE KEY-----/);
                if (m) results.push({type: sName + '-PEM', pem: m[0], key: lsKey});
            }
            try {
                const obj = JSON.parse(val);
                if (obj && obj.kty === 'RSA' && obj.d) {
                    results.push({type: sName + '-JWK', jwk: val, key: lsKey});
                }
            } catch(e) {}
        }
    }

    return results;
}
"""

# ---------------------------------------------------------------------------
# 获取注入钩子捕获的密钥 + 密钥事件日志
# ---------------------------------------------------------------------------

JS_GET_CAPTURED = """
() => ({
    pem: window.__oopz_captured_pem || null,
    events: window.__oopz_key_events || [],
})
"""


# ---------------------------------------------------------------------------
# JWK → PEM 转换
# ---------------------------------------------------------------------------

def jwk_to_pem(jwk_data):
    """将 JWK 格式的 RSA 私钥转换为 PEM"""
    try:
        from cryptography.hazmat.primitives.asymmetric.rsa import (
            RSAPrivateNumbers, RSAPublicNumbers,
            rsa_crt_dmp1, rsa_crt_dmq1, rsa_crt_iqmp,
        )
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        import base64

        jwk = json.loads(jwk_data) if isinstance(jwk_data, str) else jwk_data

        def b64url_to_int(data):
            data += "=" * (4 - len(data) % 4)
            return int.from_bytes(base64.urlsafe_b64decode(data), "big")

        n, e = b64url_to_int(jwk["n"]), b64url_to_int(jwk["e"])
        d    = b64url_to_int(jwk["d"])
        p, q = b64url_to_int(jwk["p"]), b64url_to_int(jwk["q"])
        dp = b64url_to_int(jwk["dp"]) if "dp" in jwk else rsa_crt_dmp1(d, p)
        dq = b64url_to_int(jwk["dq"]) if "dq" in jwk else rsa_crt_dmq1(d, q)
        qi = b64url_to_int(jwk["qi"]) if "qi" in jwk else rsa_crt_iqmp(p, q)

        private_key = RSAPrivateNumbers(
            p, q, d, dp, dq, qi, RSAPublicNumbers(e, n),
        ).private_key(default_backend())

        return private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
    except Exception as exc:
        print(f"  [!] JWK → PEM 转换失败: {exc}")
        return None


# ---------------------------------------------------------------------------
# 核心：浏览器捕获
# ---------------------------------------------------------------------------

async def capture_credentials():
    """启动浏览器，捕获 Oopz 凭据"""
    from playwright.async_api import async_playwright

    credentials = {
        "person_uid": None,
        "device_id": None,
        "jwt_token": None,
        "private_key_pem": None,
    }
    header_done = asyncio.Event()

    print("=" * 60)
    print("  Oopz 凭据获取工具")
    print("=" * 60)
    print()
    print("  即将打开浏览器，请在 Oopz 网页端登录你的账号。")
    print("  登录成功后工具将自动从请求中提取所需凭据。")
    print("  如果之前已登录，进入页面后将自动捕获。")
    print()
    print("-" * 60)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # 注入 Web Crypto 钩子（页面加载前生效）
        await page.add_init_script(JS_CRYPTO_HOOK)

        # ---------- HTTP 请求拦截 ----------
        def on_request(request):
            h = request.headers
            if h.get("oopz-person") and not credentials["person_uid"]:
                credentials["person_uid"] = h["oopz-person"]
                print(f"  [✓] 用户 UID:  {credentials['person_uid']}")
            if h.get("oopz-device-id") and not credentials["device_id"]:
                credentials["device_id"] = h["oopz-device-id"]
                print(f"  [✓] 设备 ID:   {credentials['device_id']}")
            sig = h.get("oopz-signature")
            if sig and not credentials["jwt_token"]:
                if _is_jwt_expired(sig):
                    if not getattr(on_request, "_warned_expired", False):
                        on_request._warned_expired = True
                        print(f"  [!] 检测到过期 JWT，已跳过。请在浏览器中重新登录以获取新 Token")
                else:
                    credentials["jwt_token"] = sig
                    preview = sig[:50] + "..." if len(sig) > 50 else sig
                    print(f"  [✓] JWT Token:  {preview}")

            if all(credentials[k] for k in ("person_uid", "device_id", "jwt_token")):
                header_done.set()

        page.on("request", on_request)

        # ---------- WebSocket 帧拦截（备用） ----------
        def on_websocket(ws):
            def on_frame(payload):
                try:
                    data = json.loads(payload)
                    if data.get("event") != WS_EVENT_AUTH:
                        return
                    body = json.loads(data.get("body", "{}"))
                    if body.get("person") and not credentials["person_uid"]:
                        credentials["person_uid"] = body["person"]
                        print(f"  [✓] 用户 UID (ws):  {credentials['person_uid']}")
                    if body.get("deviceId") and not credentials["device_id"]:
                        credentials["device_id"] = body["deviceId"]
                        print(f"  [✓] 设备 ID (ws):   {credentials['device_id']}")
                    ws_sig = body.get("signature")
                    if ws_sig and not credentials["jwt_token"]:
                        if _is_jwt_expired(ws_sig):
                            if not getattr(on_frame, "_warned_expired", False):
                                on_frame._warned_expired = True
                                print(f"  [!] 检测到过期 JWT (ws)，已跳过。请在浏览器中重新登录以获取新 Token")
                        else:
                            credentials["jwt_token"] = ws_sig
                            preview = ws_sig[:50] + "..." if len(ws_sig) > 50 else ws_sig
                            print(f"  [✓] JWT Token (ws):  {preview}")

                    if all(credentials[k] for k in ("person_uid", "device_id", "jwt_token")):
                        header_done.set()
                except Exception:
                    pass

            ws.on("framesent", on_frame)

        page.on("websocket", on_websocket)

        # ---------- 打开页面 ----------
        await page.goto(OOPZ_WEB_URL, wait_until="domcontentloaded")
        print(f"\n  浏览器已打开 {OOPZ_WEB_URL}")
        print("  正在等待捕获凭据（登录后自动获取）...\n")

        try:
            await asyncio.wait_for(header_done.wait(), timeout=300)
        except asyncio.TimeoutError:
            print("\n  [!] 等待超时（5 分钟），跳过请求头捕获")

        has_headers = all(credentials[k] for k in ("person_uid", "device_id", "jwt_token"))
        if has_headers:
            print("\n  请求头凭据已全部捕获！")

        # ---------- 提取 RSA 私钥 ----------
        # 等待页面完成 API 调用（触发 sign），给钩子时间捕获密钥
        print("  正在等待 RSA 密钥捕获...\n")
        await asyncio.sleep(3)

        credentials["private_key_pem"] = await _try_extract_key(page)

        # 如果钩子没捕获到（密钥已缓存在 IndexedDB 且未经 importKey），
        # 尝试清除浏览器存储后刷新，迫使页面重新 import/generate
        if not credentials["private_key_pem"]:
            credentials["private_key_pem"] = await _retry_with_clear(page)

        if not credentials["private_key_pem"]:
            print()
            print("  ╔══════════════════════════════════════════════════╗")
            print("  ║  未能自动提取 RSA 私钥，请手动获取：            ║")
            print("  ║                                                  ║")
            print("  ║  1. 在浏览器中按 F12 打开 DevTools               ║")
            print("  ║  2. 切到 Application → IndexedDB                 ║")
            print("  ║  3. 逐个展开数据库/存储，查找 CryptoKey 条目     ║")
            print("  ║  4. 或在 Console 中执行:                         ║")
            print("  ║     window.__oopz_key_events                     ║")
            print("  ║     查看密钥操作日志以定位问题                   ║")
            print("  ╚══════════════════════════════════════════════════╝")
            print()
            input("  按 Enter 关闭浏览器...")

        print("\n  正在关闭浏览器...")
        await context.close()

    return credentials


async def _try_extract_key(page) -> str | None:
    """尝试从注入钩子和存储扫描中提取 RSA 私钥"""

    # 策略 1：从注入钩子的全局变量获取（importKey/generateKey/sign 时自动捕获）
    try:
        captured = await page.evaluate(JS_GET_CAPTURED)
        events = captured.get("events", [])
        if events:
            print(f"  [i] 密钥操作日志 ({len(events)} 条):")
            for ev in events:
                print(f"      {ev}")

        pem = captured.get("pem")
        if pem:
            print(f"  [✓] RSA 私钥:  已通过 Crypto API 钩子捕获")
            return pem
    except Exception as exc:
        print(f"  [!] 读取钩子数据失败: {exc}")

    # 策略 2：全量扫描 IndexedDB / localStorage / sessionStorage
    print("  [i] 钩子未捕获密钥，尝试扫描浏览器存储...")
    try:
        scan_results = await page.evaluate(JS_SCAN_STORAGE)
        if scan_results:
            print(f"  [i] 存储扫描发现 {len(scan_results)} 条密钥相关数据:")
            for item in scan_results:
                loc = f"{item.get('db', item.get('key', '?'))}/{item.get('store', '')}"
                print(f"      类型={item['type']}  位置={loc}")

            for item in scan_results:
                pem = item.get("pem")
                if pem:
                    pem = pem.replace("\\n", "\n")
                    print(f"  [✓] RSA 私钥:  已从 {item['type']} 提取")
                    return pem

                jwk = item.get("jwk")
                if jwk:
                    pem = jwk_to_pem(jwk)
                    if pem:
                        print(f"  [✓] RSA 私钥:  已从 JWK 转换为 PEM")
                        return pem
        else:
            print("  [i] 存储扫描未发现任何密钥数据")
    except Exception as exc:
        print(f"  [!] 存储扫描出错: {exc}")

    return None


async def _retry_with_clear(page) -> str | None:
    """
    清除 IndexedDB 中的 CryptoKey 缓存后刷新页面，
    迫使 Oopz 网页端重新 import/generate 密钥，
    此时注入的钩子可以强制 extractable=true 并捕获。
    """
    print()
    print("  密钥可能以不可导出的 CryptoKey 形式缓存在 IndexedDB 中。")
    print("  需要清除缓存并刷新页面，让钩子在密钥重新生成时拦截。")
    print("  （不会影响登录状态，密钥会自动重新生成并注册）")
    print()
    choice = input("  输入 y 清除密钥缓存并刷新，其他键跳过: ").strip().lower()
    if choice != "y":
        return None

    print("\n  正在清除 IndexedDB 密钥缓存...")

    # 删除所有 IndexedDB 数据库（保留 cookie/localStorage 以维持登录）
    try:
        deleted = await page.evaluate("""
            async () => {
                const deleted = [];
                try {
                    const dbs = await indexedDB.databases();
                    for (const db of dbs) {
                        try {
                            await new Promise((resolve, reject) => {
                                const req = indexedDB.deleteDatabase(db.name);
                                req.onsuccess = () => resolve();
                                req.onerror = () => reject(req.error);
                                req.onblocked = () => resolve();
                            });
                            deleted.push(db.name);
                        } catch(e) {}
                    }
                } catch(e) {}
                return deleted;
            }
        """)
        if deleted:
            print(f"  [i] 已删除 {len(deleted)} 个 IndexedDB 数据库: {', '.join(deleted)}")
        else:
            print("  [i] 没有找到可删除的 IndexedDB 数据库")
    except Exception as exc:
        print(f"  [!] 清除失败: {exc}")

    # 刷新页面（init_script 会自动重新注入）
    print("  正在刷新页面...")
    await page.reload(wait_until="domcontentloaded")
    print("  页面已刷新，等待密钥重新生成...\n")

    # 等待 Oopz 客户端完成初始化和首次 API 调用
    for i in range(15):
        await asyncio.sleep(2)
        try:
            captured = await page.evaluate(JS_GET_CAPTURED)
            pem = captured.get("pem")
            if pem:
                print(f"  [✓] RSA 私钥:  刷新后通过钩子成功捕获！")
                return pem
            events = captured.get("events", [])
            if events and i % 3 == 0:
                print(f"  [i] 等待中... 已记录 {len(events)} 条密钥操作")
        except Exception:
            pass

    print("  [!] 刷新后仍未捕获到密钥")
    return None


# ---------------------------------------------------------------------------
# 结果展示 & 保存
# ---------------------------------------------------------------------------

def display_results(credentials):
    """格式化显示捕获结果"""
    print("\n" + "=" * 60)
    print("  捕获结果")
    print("=" * 60)

    items = [
        ("用户 UID (person_uid)", credentials.get("person_uid")),
        ("设备 ID  (device_id)", credentials.get("device_id")),
        ("JWT Token (jwt_token)", credentials.get("jwt_token")),
    ]
    for label, value in items:
        ok = "✓" if value else "✗"
        display = value or "未获取"
        if "jwt_token" in label and value and len(value) > 60:
            display = value[:60] + "..."
        print(f"  [{ok}] {label}: {display}")

    pem = credentials.get("private_key_pem")
    ok = "✓" if pem else "✗"
    print(f"  [{ok}] RSA 私钥: {'已获取' if pem else '未获取'}")

    if pem:
        lines = pem.strip().splitlines()
        print(f"\n      RSA 私钥预览 ({len(lines)} 行):")
        print(f"        {lines[0]}")
        if len(lines) > 2:
            print(f"        {lines[1][:60]}...")
            print(f"        ...")
        print(f"        {lines[-1]}")

    print()


def save_config(credentials):
    """将捕获的凭据写入 config.py 和 private_key.py"""
    config_path = os.path.join(PROJECT_ROOT, "config.py")
    pk_path = os.path.join(PROJECT_ROOT, "private_key.py")
    saved = []

    # ---- 更新 config.py ----
    has_config = any(credentials.get(k) for k in ("person_uid", "device_id", "jwt_token"))
    if has_config:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            replacements = {
                "device_id": credentials.get("device_id"),
                "person_uid": credentials.get("person_uid"),
                "jwt_token": credentials.get("jwt_token"),
            }
            for key, value in replacements.items():
                if value:
                    content = re.sub(
                        rf'("{key}"\s*:\s*)"[^"]*"',
                        rf'\1"{value}"',
                        content,
                    )

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(content)
            saved.append("config.py")
        else:
            print("  [!] config.py 不存在，请先从 config.example.py 复制")

    # ---- 更新 private_key.py ----
    pem = credentials.get("private_key_pem")
    if pem:
        pk_content = (
            '"""RSA 私钥（由 credential_tool.py 自动生成）"""\n'
            "\n"
            "from cryptography.hazmat.primitives import serialization\n"
            "from cryptography.hazmat.backends import default_backend\n"
            "\n"
            f'PRIVATE_KEY_PEM = b"""{pem}"""\n'
            "\n"
            "\n"
            "def get_private_key():\n"
            '    """加载并返回 RSA 私钥对象"""\n'
            "    return serialization.load_pem_private_key(\n"
            "        PRIVATE_KEY_PEM,\n"
            "        password=None,\n"
            "        backend=default_backend(),\n"
            "    )\n"
        )
        with open(pk_path, "w", encoding="utf-8") as f:
            f.write(pk_content)
        saved.append("private_key.py")

    # ---- 保存凭据摘要 txt ----
    txt_path = os.path.join(PROJECT_ROOT, "data", "credentials.txt")
    os.makedirs(os.path.dirname(txt_path), exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Oopz Bot 凭据\n")
        f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"用户 UID (person_uid):\n{credentials.get('person_uid', '')}\n\n")
        f.write(f"设备 ID (device_id):\n{credentials.get('device_id', '')}\n\n")
        f.write(f"JWT Token (jwt_token):\n{credentials.get('jwt_token', '')}\n\n")
        if pem:
            f.write(f"RSA 私钥 (PEM):\n{pem}\n")
    saved.append("credentials.txt")

    if saved:
        print(f"  [✓] 已保存到: {', '.join(saved)}")
    else:
        print("  [!] 没有可保存的凭据")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    if not ensure_playwright():
        return

    credentials = asyncio.run(capture_credentials())
    display_results(credentials)

    has_any = any(credentials.get(k) for k in ("person_uid", "device_id", "jwt_token", "private_key_pem"))
    if not has_any:
        print("  未能捕获任何凭据，请重试。")
        return

    if "--save" in sys.argv:
        save_config(credentials)
    else:
        print("  是否保存到配置文件？")
        print("  将更新: config.py (UID/设备ID/Token) + private_key.py (RSA 私钥)")
        choice = input("\n  输入 y 确认保存，其他键跳过: ").strip().lower()
        if choice == "y":
            save_config(credentials)
        else:
            print("\n  已跳过保存。你可以手动将上述值填入配置文件。")

    print()
    print("=" * 60)
    print("  完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
