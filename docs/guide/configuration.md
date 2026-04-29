# 配置方法

SDK 的所有能力都从 `OopzConfig` 开始。

```python
import os

from oopz_sdk import OopzConfig, RetryConfig, HeartbeatConfig, ProxyConfig

config = OopzConfig.from_env(
    retry=RetryConfig(interval=0.35, timeout=(10, 30), max_attempts=3),
    heartbeat=HeartbeatConfig(interval=10.0, reconnect_interval=2.0),
    proxy=ProxyConfig(http="http://127.0.0.1:7890", https="http://127.0.0.1:7890"),
)
```

## 必填配置

| 字段            | 类型                       | 说明                           |
|---------------|--------------------------|------------------------------|
| `device_id`   | `str`                    | 设备 ID。不能为空。                  |
| `person_uid`  | `str`                    | 当前登录账号 UID，通常也是机器人 UID。不能为空。 |
| `jwt_token`   | `str`                    | 登录态 JWT。不能为空。                |
| `private_key` | `str \| bytes \| key object` | RSA 私钥，用于签名请求。不能为空。           |

## 通过账号密码自动提取凭证

SDK 内置了一个基于 OOPZ Web 登录页的提取工具，会自动登录并从登录接口、请求头、WebSocket 鉴权消息和 Web Crypto 私钥钩子中提取 `device_id`、`person_uid`、`jwt_token` 和 `private_key`。

首次使用前需要安装 Chromium：

```bash
python -m playwright install chromium
```

命令行方式：

```powershell
$env:OOPZ_LOGIN_PHONE = "你的 OOPZ 登录账号"
python -m oopz_sdk.cli.password_login --phone $env:OOPZ_LOGIN_PHONE --print-env powershell
```

如果登录过程需要人工验证，可以显示浏览器窗口：

```powershell
python -m oopz_sdk.cli.password_login --phone $env:OOPZ_LOGIN_PHONE --headful --print-env powershell
```

命令会安全询问密码，并在成功后输出可设置 `OOPZ_DEVICE_ID`、`OOPZ_PERSON_UID`、`OOPZ_JWT_TOKEN`、`OOPZ_PRIVATE_KEY` 的环境变量命令。把这些命令只复制到本地 shell 执行，不要提交到仓库。

在代码中直接登录并创建配置：

```python
import asyncio
import os

from oopz_sdk import OopzConfig


async def main():
    config = await OopzConfig.from_password_env(
        headless=os.environ.get("OOPZ_LOGIN_HEADFUL") != "1",
    )
    print(config.person_uid)


asyncio.run(main())
```

以下设置一般不需要修改，除非你有特殊需求，例如使用代理或调整重试策略。

## 网关与请求配置


| 字段            | 默认值                       | 说明                   |
|---------------|---------------------------|----------------------|
| `base_url`    | `https://gateway.oopz.cn` | Oopz的HTTP API 地址。    |
| `ws_url`      | `wss://ws.oopz.cn`        | Oopz的WebSocket 网关地址。 |
| `app_version` | `69514`                   | 客户端版本标识。             |
| `channel`     | `Web`                     | 客户端渠道。               |
| `platform`    | `windows`                 | 平台标识。                |
| `web`         | `True`                    | 是否按 Web 客户端行为发送。     |
| `headers`     | `{}`                      | 额外请求头，会覆盖默认头。        |

## 重试配置 `RetryConfig`

| 字段             | 默认值        | 说明                                          |
|----------------|------------|---------------------------------------------|
| `interval`     | `0.35`     | 请求之间的基础间隔，也兼容 `config.rate_limit_interval`。 |
| `timeout`      | `(10, 30)` | 连接超时和读取超时。                                  |
| `max_attempts` | `3`        | 最大尝试次数。                                     |

## 心跳配置 `HeartbeatConfig`

| 字段                       | 默认值     | 说明              |
|--------------------------|---------|-----------------|
| `interval`               | `10.0`  | WebSocket 心跳间隔。 |
| `reconnect_interval`     | `2.0`   | 初始重连间隔。         |
| `max_reconnect_interval` | `120.0` | 最大重连间隔。         |

## 代理配置 `ProxyConfig`

| 字段          | 说明            |
|-------------|---------------|
| `http`      | HTTP 请求代理。    |
| `https`     | HTTPS 请求代理。   |
| `websocket` | WebSocket 代理。 |

示例：

```python
config = OopzConfig(
    ...,
    proxy=ProxyConfig(
        http="http://127.0.0.1:7890",
        https="http://127.0.0.1:7890",
        websocket="http://127.0.0.1:7890",
    ),
)
```

## 消息配置

| 字段                       | 默认值     | 说明                       |
|--------------------------|---------|--------------------------|
| `ignore_self_messages`   | `True`  | 忽略自己发出的消息，避免机器人回复自己导致循环。 |
| `use_announcement_style` | `False` | 频道消息默认加 `IMPORTANT` 样式。  |


## 缓存配置

| 字段                       | 默认值     | 说明                    |
|--------------------------|---------|-----------------------|
| `area_members_cache_ttl` | `15.0`  | 域成员分页缓存有效期。           |
| `area_members_stale_ttl` | `300.0` | 预留的过期缓存时间。            |
| `cache_max_entries`      | `200`   | 缓存最大条目；小于等于 0 表示关闭缓存。 |

## 语音配置

| 字段                              | 默认值                 | 说明                  |
|---------------------------------|---------------------|---------------------|
| `agora_app_id`                  | SDK 内置值             | Agora App ID。       |
| `agora_init_timeout`            | `1800`              | 语音后端初始化超时。          |
| `voice_backend`                 | `browser`           | 当前实现使用浏览器后端。        |
| `voice_browser_headless`        | `True`              | 是否无头运行浏览器。          |
| `voice_browser_executable_path` | `""`                | 自定义 Chromium 路径。    |
| `voice_agora_sdk_url`           | Agora 官方 JS SDK URL | 浏览器后端加载的 Agora SDK。 |

## OneBot v12 配置

详见 [OneBot v12 适配](../adapters/onebot-v12.md)。
