# 账号密码登录提取凭据

这个 recipe 展示如何用 OOPZ 账号密码登录工具获取 SDK 所需凭据，并把凭据放入环境变量。

## 命令行

首次使用前安装 Chromium：

```bash
python -m playwright install chromium
```

Windows PowerShell：

```powershell
$env:OOPZ_LOGIN_PHONE = "你的 OOPZ 登录账号"
oopz-login --phone $env:OOPZ_LOGIN_PHONE --print-env powershell
```

Linux / macOS：

```bash
export OOPZ_LOGIN_PHONE="你的 OOPZ 登录账号"
oopz-login --phone "$OOPZ_LOGIN_PHONE" --print-env bash
```

登录成功后，命令会输出 `OOPZ_DEVICE_ID`、`OOPZ_PERSON_UID`、`OOPZ_JWT_TOKEN` 和 `OOPZ_PRIVATE_KEY` 的设置命令。把输出复制到本地 shell 执行后，就可以运行 SDK 示例。

如果登录过程需要人工验证，增加 `--headful`：

```powershell
oopz-login --phone $env:OOPZ_LOGIN_PHONE --headful --print-env powershell
```

## 使用提取后的环境变量

复制命令行输出的环境变量后，可以直接从这些底层凭据创建配置：

```python
from oopz_sdk import OopzConfig


config = OopzConfig.from_env()
print(config.person_uid)
```

这段代码默认读取 `OOPZ_DEVICE_ID`、`OOPZ_PERSON_UID`、`OOPZ_JWT_TOKEN` 和 `OOPZ_PRIVATE_KEY`。

## 代码中直接登录

如果不想先运行命令行工具，也可以在代码中直接读取账号密码环境变量并登录：

```python
import asyncio

from oopz_sdk import OopzConfig


async def main() -> None:
    config = await OopzConfig.from_password_env()
    print(config.person_uid)


asyncio.run(main())
```

这段代码默认读取 `OOPZ_LOGIN_PHONE` 和 `OOPZ_LOGIN_PASSWORD`。需要人工验证时设置 `OOPZ_LOGIN_HEADFUL=1`（也接受 `true` / `yes` / `on`），也可以在调用时显式传 `headless=False`。

不要把输出的真实 token、私钥或任何保存了这些内容的文件提交到仓库。
