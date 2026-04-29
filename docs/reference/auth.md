# 认证与凭据

认证相关公开 API 从 `oopz_sdk` 或 `oopz_sdk.auth` 导出。

## `OopzConfig.from_password_env(...)`

从环境变量读取 OOPZ 账号密码，自动登录并返回 `OopzConfig`。这是 quickstart 推荐的开发期登录方式。

```python
import os

from oopz_sdk import OopzConfig

config = await OopzConfig.from_password_env(
    headless=os.environ.get("OOPZ_LOGIN_HEADFUL") != "1",
)
```

默认读取：

| 环境变量 | 说明 |
| --- | --- |
| `OOPZ_LOGIN_PHONE` | OOPZ 登录账号或手机号。 |
| `OOPZ_LOGIN_PASSWORD` | OOPZ 登录密码。 |

可以通过 `phone_env` / `password_env` 改用其他环境变量名。其他参数会传给 `login_with_password()`；如果需要覆盖最终配置，传入 `config_overrides={...}`。

## `OopzConfig.from_env(...)`

如果你已经有底层凭据，可以直接从环境变量创建配置：

```python
from oopz_sdk import OopzConfig

config = OopzConfig.from_env()
```

默认读取 `OOPZ_DEVICE_ID`、`OOPZ_PERSON_UID`、`OOPZ_JWT_TOKEN`、`OOPZ_PRIVATE_KEY`，并可选读取 `OOPZ_APP_VERSION`。

## `login_with_password(phone, password, ...)`

通过 OOPZ Web 登录页自动登录，并提取 SDK 需要的 `device_id`、`person_uid`、`jwt_token` 和 RSA 私钥。

```python
import getpass
import os

from oopz_sdk import login_with_password

credentials = await login_with_password(
    os.environ["OOPZ_LOGIN_PHONE"],
    getpass.getpass("OOPZ 密码: "),
    headless=True,
)
print(credentials.masked())
```

常用参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `phone` | `str` | - | OOPZ 登录账号或手机号。 |
| `password` | `str` | - | OOPZ 登录密码。建议交互输入，不要写入代码。 |
| `timeout` | `float` | `90` | 等待登录接口响应的秒数。 |
| `headless` | `bool` | `True` | 是否无头运行浏览器。遇到验证码或风控验证时可设为 `False`。 |
| `browser_data_dir` | `str \| Path \| None` | `None` | 自定义浏览器 profile 目录。默认使用临时目录。 |
| `chromium_executable_path` | `str \| Path \| None` | `None` | 自定义 Chromium/Chrome 可执行文件路径。 |
| `proxy` | `ProxyConfig \| dict \| str \| None` | `None` | 登录浏览器使用的代理。 |

## `login_with_password_sync(phone, password, ...)`

同步包装，适合一次性脚本：

```python
import getpass
import os

from oopz_sdk import login_with_password_sync

credentials = login_with_password_sync(
    os.environ["OOPZ_LOGIN_PHONE"],
    getpass.getpass("OOPZ 密码: "),
)
```

## `OopzLoginCredentials`

账号密码登录返回的 dataclass，不是 Pydantic 响应模型。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `device_id` | `str` | 当前登录设备 ID。 |
| `person_uid` | `str` | 当前登录账号 UID。 |
| `jwt_token` | `str` | 登录态 JWT。 |
| `private_key_pem` | `str` | RSA 私钥 PEM。 |
| `app_version` | `str` | 捕获到的 Web 客户端版本。 |
| `expires_at` | `str` | JWT 过期时间，无法解析时为空。 |
| `expires_in_seconds` | `int \| None` | JWT 剩余秒数，无法解析时为 `None`。 |

常用方法：

| 方法 | 说明 |
| --- | --- |
| `to_config(**overrides)` | 转为 `OopzConfig`。 |
| `to_env(prefix="OOPZ_")` | 转为环境变量字典。 |
| `from_env(prefix="OOPZ_")` | 从环境变量创建凭据对象。 |
| `from_mapping(data)` | 从字典创建凭据对象。 |
| `masked()` | 返回脱敏摘要，适合日志展示。 |

## 命令行

安装包后可使用 `oopz-login`：

```powershell
$env:OOPZ_LOGIN_PHONE = "你的 OOPZ 登录账号"
oopz-login --phone $env:OOPZ_LOGIN_PHONE --print-env powershell
```

Linux / macOS：

```bash
export OOPZ_LOGIN_PHONE="你的 OOPZ 登录账号"
oopz-login --phone "$OOPZ_LOGIN_PHONE" --print-env bash
```

命令会交互式询问密码。输出的环境变量命令包含真实登录态和私钥，只能在本地 shell 中使用，不要提交到仓库。

如果确实需要保存为本地 JSON，可使用 `save_credentials_json(credentials, path)` / `load_credentials_json(path)`；该文件包含真实 token 和私钥，必须加入忽略列表。
