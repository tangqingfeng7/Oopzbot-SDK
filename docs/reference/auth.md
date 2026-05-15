# 认证与凭据

认证相关公开 API 可以从 `oopz_sdk` 或 `oopz_sdk.auth` 导入。

Oopz SDK 当前支持两类认证方式：

1. 使用已有底层凭据：`device_id`、`person_uid`、`jwt_token`、`private_key` (可选)
2. 使用账号密码登录，并自动提取 SDK 需要的底层凭据

一般推荐应用代码使用 `OopzConfig` 完成认证，然后再创建 `OopzBot` 或其他客户端。

---

## `config.login(...)`

使用手机和密码登录，并把登录结果写入当前 `OopzConfig` 实例。

适合同步脚本或普通入口函数：

```python
from oopz_sdk import OopzBot, OopzConfig

config = OopzConfig()
config.login(
    phone="...",
    password="...",
)

bot = OopzBot(config)
```

如果你已经拥有登录使用的凭据, 也可以直接使用凭据进行登录

- `device_id`
- `person_uid`
- `jwt_token`
- `private_key` (可选)

```python
from oopz_sdk import OopzBot, OopzConfig

config = OopzConfig()
config.login(
    device_id="...",
    person_uid="...",
    jwt_token="...",
    private_key="..."
)

bot = OopzBot(config)
```

---

## `await config.login_async(...)`

异步版本的登录方法，适合在异步函数中使用

```python
import asyncio

from oopz_sdk import OopzBot, OopzConfig


async def main():
    config = OopzConfig()
    await config.login_async(
        phone="...",
        password="...",
    )

    bot = OopzBot(config)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 登录方式 `method`

`config.login(..., method=)` 和 `config.login_async(..., method=)` 都支持 `method` 参数。

| method             | 说明                              |
|--------------------|---------------------------------|
| `auto`             | 默认值。优先使用完整凭据；如果提供了账号密码，则执行密码登录。 |
| `credentials`      | 只使用已有底层凭据，不进行账号密码登录。            |
| `password`         | 使用账号密码登录，由 SDK 自动选择合适的密码登录流程。   |
| `password_api`     | 使用账号密码接口登录。                     |
| `password_browser` | 使用浏览器自动登录流程。                    |

示例：

```python
config = OopzConfig()
config.login(
    phone="...",
    password="...",
    method="password",
)
```

使用已有凭据：

```python
config = OopzConfig()
config.login(
    method="credentials",
    device_id="...",
    person_uid="...",
    jwt_token="...",
    private_key="...",
)
```

---

## `OopzConfig.from_env(...)`

使用环境变量创建bot更加安全, 这样密码就不用明文编码到代码中

`from_env` 默认读取以下环境变量：

| 环境变量               | 说明          |
|--------------------|-------------|
| `OOPZ_DEVICE_ID`   | 当前登录设备 ID。  |
| `OOPZ_PERSON_UID`  | 当前登录账号 UID。 |
| `OOPZ_JWT_TOKEN`   | 登录态 JWT。    |
| `OOPZ_PRIVATE_KEY` | RSA 私钥 PEM。 |
| `OOPZ_LOGIN_PHONE` | 登录的手机号。     |
| `OOPZ_LOGIN_PHONE` | 登录的密码。      |
| `OOPZ_APP_VERSION` | 可选，客户端版本。   |

`from_env`同样可以指定登录方式：

```powershell
$env:OOPZ_LOGIN_METHOD = "auto"
```

支持的值：

```text
auto
credentials
password
password_api
password_browser
```


- 设置登录所需要的手机号和密码
    - PowerShell 示例：
    ```powershell
    $env:OOPZ_LOGIN_PHONE = "你的 OOPZ 登录账号"
    $env:OOPZ_LOGIN_PASSWORD = "你的 OOPZ 登录密码"
    ```
    - Linux / macOS 示例：
    ```bash
    export OOPZ_LOGIN_PHONE="..."
    export OOPZ_LOGIN_PASSWORD="..."
    ```
- 设置登录所需的凭据
    - PowerShell 示例：
    ```powershell
    $env:OOPZ_DEVICE_ID = "..."
    $env:OOPZ_PERSON_UID = "..."
    $env:OOPZ_JWT_TOKEN = "..."
    $env:OOPZ_PRIVATE_KEY = "..."
    ```

    - Linux / macOS 示例：
    ```bash
    export OOPZ_DEVICE_ID="..."
    export OOPZ_PERSON_UID="..."
    export OOPZ_JWT_TOKEN="..."
    export OOPZ_PRIVATE_KEY="..."
    ```

然后：

```python
from oopz_sdk import OopzConfig

config = OopzConfig.from_env()
```

### 通过 override 修改其他配置项

```python
from oopz_sdk import OopzConfig, RetryConfig, HeartbeatConfig, ProxyConfig

config = OopzConfig.from_env(
    retry=RetryConfig(max_attempts=3),
    heartbeat=HeartbeatConfig(interval=10.0, reconnect_interval=2.0),
    proxy=ProxyConfig(http="http://127.0.0.1:7890", https="http://127.0.0.1:7890"),
)
```

## `OopzConfig.from_env_async(...)`

异步版本的使用环境变量的登录方法，适合在异步函数中使用

```python
import asyncio

from oopz_sdk import OopzBot, OopzConfig


async def main():
    config = await OopzConfig.from_env_async()

    bot = OopzBot(config)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
```



---

## `login_with_password(phone, password, ...)`

底层账号密码登录函数。

它会通过 OOPZ 登录流程获取 SDK 需要的：

- `device_id`
- `person_uid`
- `jwt_token`
- `private_key`
- `app_version`

返回值是 `OopzLoginCredentials`，而不是 `OopzConfig`。

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

如果你只是想创建 SDK 配置，通常不需要直接调用它，优先使用`login` 或者 `login_async`：


常用参数：

| 参数                         | 类型                                   | 默认值    | 说明                                |
|----------------------------|--------------------------------------|--------|-----------------------------------|
| `phone`                    | `str`                                | -      | OOPZ 登录账号或手机号。                    |
| `password`                 | `str`                                | -      | OOPZ 登录密码。建议交互输入，不要写入代码。          |
| `timeout`                  | `float`                              | `90`   | 等待登录接口响应的秒数。                      |
| `headless`                 | `bool`                               | `True` | 是否无头运行浏览器。遇到验证码或风控验证时可设为 `False`。 |
| `browser_data_dir`         | `str \| Path \| None`                | `None` | 自定义浏览器 profile 目录。默认使用临时目录。       |
| `chromium_executable_path` | `str \| Path \| None`                | `None` | 自定义 Chromium/Chrome 可执行文件路径。      |
| `proxy`                    | `ProxyConfig \| dict \| str \| None` | `None` | 登录浏览器使用的代理。                       |

---

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

print(credentials.masked())
```

## `OopzLoginCredentials`


| 字段                   | 类型            | 说明                      |
|----------------------|---------------|-------------------------|
| `device_id`          | `str`         | 当前登录设备 ID。              |
| `person_uid`         | `str`         | 当前登录账号 UID。             |
| `jwt_token`          | `str`         | 登录态 JWT。                |
| `private_key_pem`    | `str`         | RSA 私钥 PEM。             |
| `app_version`        | `str`         | 捕获到的 Web 客户端版本。         |
| `expires_at`         | `str`         | JWT 过期时间，无法解析时为空。       |
| `expires_in_seconds` | `int \| None` | JWT 剩余秒数，无法解析时为 `None`。 |

常用方法：

| 方法                         | 说明               |
|----------------------------|------------------|
| `to_config(**overrides)`   | 转为 `OopzConfig`。 |
| `to_env(prefix="OOPZ_")`   | 转为环境变量字典。        |
| `from_env(prefix="OOPZ_")` | 从环境变量创建凭据对象。     |
| `from_mapping(data)`       | 从字典创建凭据对象。       |
| `masked()`                 | 返回脱敏摘要，适合日志展示。   |

示例：

```python
credentials = await login_with_password(
    phone,
    password,
)

config = credentials.to_config(
    auto_subscribe_joined_areas=True,
)
```

---

## `OopzPasswordLoginError`

账号密码登录或凭据提取失败时抛出。

它继承自 `OopzAuthError`，可以从 `oopz_sdk` 或 `oopz_sdk.exceptions` 导入：

```python
from oopz_sdk import OopzConfig, OopzPasswordLoginError

try:
    config = OopzConfig()
    config.login(
        phone="...",
        password="...",
    )
except OopzPasswordLoginError as e:
    print("登录失败:", e)
    if e.code is not None:
        print("错误码:", e.code)
```

异步版本：

```python
from oopz_sdk import OopzConfig, OopzPasswordLoginError

try:
    config = OopzConfig()
    await config.login_async(
        phone="...",
        password="...",
    )
except OopzPasswordLoginError as e:
    print("登录失败:", e)
    if e.code is not None:
        print("错误码:", e.code)
```

| 属性        | 类型                   | 说明                         |
|-----------|----------------------|----------------------------|
| `code`    | `int \| str \| None` | 登录接口返回的业务错误码，无则为 `None`。   |
| `payload` | `object \| None`     | 登录接口返回的原始 payload，便于排查时打印。 |

---

## 已弃用方法

下面的方法仍可用，但已进入弃用流程。

### `OopzConfig.from_password(...)`

旧的异步构造方式。

### `OopzConfig.from_password_env(...)`

旧的异步环境变量登录方式。


### `OopzConfig.from_password_env_sync(...)`

旧的同步环境变量登录方式。

---

## 命令行 `oopz-login`

安装包后可使用 `oopz-login` 命令生成本地环境变量。

PowerShell：

```powershell
$env:OOPZ_LOGIN_PHONE = "你的 OOPZ 登录账号"
oopz-login --phone $env:OOPZ_LOGIN_PHONE --print-env powershell
```

Linux / macOS：

```bash
export OOPZ_LOGIN_PHONE="你的 OOPZ 登录账号"
oopz-login --phone "$OOPZ_LOGIN_PHONE" --print-env bash
```
