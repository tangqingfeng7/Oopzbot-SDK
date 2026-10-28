# 配置方法

SDK 的所有能力都从 `OopzConfig` 开始。

```python
from oopz_sdk import OopzConfig, RetryConfig, HeartbeatConfig, ProxyConfig

config = OopzConfig.from_env(
    retry=RetryConfig(max_attempts=3),
    heartbeat=HeartbeatConfig(interval=10.0, reconnect_interval=2.0),
    proxy=ProxyConfig(http="http://127.0.0.1:7890", https="http://127.0.0.1:7890"),
)
```

登录方法详见[认证与凭据](../reference/auth.md)

## 接受来自域的事件推送

默认情况下, SDK是不会收到来自域的事件 (例如域的设置更改, 用户进入退出房间等) 推送的, 需要进行手动注册。

您可以使用 `send_subscribe_area_events` 方法在bot启动后订阅特定域的事件：

```python
area_ids = ["6bv5677gsfdb41e882694531567a0972"]  # 替换为你想订阅的域 ID

await bot.ws.send_subscribe_area_events(area_ids)
```

您也可以使用 `auto_subscribe_joined_areas` 选项在启动时自动订阅所有已加入域的事件：

!!! danger "注意"
    Oopz web端一般只会使用单个`area_ids`进行请求, 但是经过测试, 这个接口是支持批量订阅的, 但是传入多个`area_ids`造成的风险和问题目前还不清楚, 
    请谨慎使用多个域的事件订阅和`auto_subscribe_joined_areas`功能。

```python
from oopz_sdk import OopzBot, OopzConfig

config = OopzConfig(
    auto_subscribe_joined_areas=True,
)

config.login(phone="手机号", password="密码")

bot = OopzBot(config)

@bot.on_ready
async def ready(ctx):
    print("Bot ready, joined area events subscribed")
```

这个功能会在机器人启动后自动查询已加入的域，并订阅这些域的事件推送。这样当有用户进入退出房间、域设置更改等事件时，机器人就能及时收到通知。


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

from oopz_sdk import OopzConfig


async def main():
    config = await OopzConfig.from_env_async()
    print(config.person_uid)


asyncio.run(main())
```

以下设置一般不需要修改，除非你有特殊需求，例如使用代理或调整重试策略。

## 网关与请求配置


| 字段            | 默认值                       | 说明                   |
|---------------|---------------------------|----------------------|
| `base_url`    | `https://gateway.oopz.cn` | Oopz的HTTP API 地址。    |
| `ws_url`      | 空，构造时自动配对             | 按 `base_url` 选择官方 WebSocket 网关；显式地址优先。 |
| `app_version` | `69514`                   | 客户端版本标识。             |
| `channel`     | `Web`                     | 客户端渠道。               |
| `platform`    | `windows`                 | 平台标识。                |
| `web`         | `True`                    | 是否按 Web 客户端行为发送。     |
| `headers`     | `{}`                      | 额外请求头，会覆盖默认头。        |

### 官方备用线路

当主线路出现 HTTP 567 安全拦截时，可以显式选择官方备用 HTTP/WebSocket 配对：

```python
config = OopzConfig.from_env(base_url="https://gateway1.oopz.cn", ws_url="")
assert config.ws_url == "wss://ws1.oopz.cn"
```

也可设置 `OOPZ_BASE_URL=https://gateway1.oopz.cn`；可选的 `OOPZ_WS_URL`
显式指定事件地址。`from_env(prefix="CUSTOM_")` 会读取对应前缀，代码中的
关键字参数优先于环境变量。这些设置选择登录完成后的 API 与事件线路，
不会修改账号密码登录接口。

同步和异步环境变量入口遵循相同规则；直接调用 `OopzConfig(...)` 不读取环境变量。
环境变量为空或仅含空白时视为未设置。参数和环境变量按字段分别覆盖：仅传入
`base_url` 不会清除环境中已设置的 `OOPZ_WS_URL`。如果需要重新自动配对，应显式传入空值：

```python
config = OopzConfig.from_env(
    base_url="https://gateway2.oopz.cn",
    ws_url="",  # 覆盖环境中的 OOPZ_WS_URL，再按 base_url 配对。
)
assert config.ws_url == "wss://ws2.oopz.cn"
```

使用自定义前缀时，`from_env(prefix="CUSTOM_")` 和
`await OopzConfig.from_env_async(prefix="CUSTOM_")` 读取 `CUSTOM_BASE_URL`、
`CUSTOM_WS_URL` 及同前缀的凭据变量。登录方式开关仍为 `OOPZ_LOGIN_METHOD`。

自动配对仅在构造 `OopzConfig` 时执行；运行中切换线路应重新创建配置与客户端。
SDK 不会在请求失败时自动探测或轮换备用网关。`base_url` 会去除首尾空白和末尾斜杠，
显式 `ws_url` 会去除首尾空白。
支持的官方配对如下，默认仍使用主线路：

| HTTP 网关 | WebSocket 网关 |
|-----------|----------------|
| `https://gateway.oopz.cn` | `wss://ws.oopz.cn` |
| `https://gateway1.oopz.cn` | `wss://ws1.oopz.cn` |
| `https://gateway2.oopz.cn` | `wss://ws2.oopz.cn` |
| `https://gateway-web1.oopz.cn` | `wss://ws-web1.oopz.cn` |

自定义 HTTP 网关不会被猜测为新的 WebSocket 域名，未指定 `ws_url` 时使用主线路。
备用线路的可用性取决于实际网络；切换成功不能证明 HTTP 凭据有效。
如果 WebSocket 已连接但 HTTP 返回 401/428，仍需检查凭据或重新登录。

## 重试配置 `RetryConfig`

| 字段             | 默认值        | 说明                                          |
|----------------|------------|---------------------------------------------|
| `max_attempts` | `3`        | 最大尝试次数。                                     |

该值用于 HTTP 传输层的 `request_data_with_retry()`；只有选择重试入口并启用
`retry_on_429=True` 的调用才会自动重试限流响应，并非所有 Service 请求都会重试。
普通业务请求收到 429 时抛出 `OopzRateLimitError`，其 `retry_after` 提供服务端建议的等待秒数。
密码登录的 429 则归为 `OopzConnectionError`，由 `AuthManager` 使用独立的续期退避策略处理，
详见 [认证与凭据](../reference/auth.md)。

## 请求配置 `RequestConfig`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `timeout`      | `(10, 30)` | 连接超时和读取超时。                                  |


## 全局请求频率限制配置 `RateLimitConfig`

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `interval`     | `0.0`     | 全局请求之间的基础间隔，也兼容 `config.rate_limit_interval`。 |


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
| `userinfo_cache_max_entries` | `5000` | 用户基本信息缓存最大条目数。 |
| `userinfo_cache_ttl` | `1800.0` | 用户基本信息缓存有效期（秒）。 |
| `area_channels_cache_max_entries` | `1000` | 域频道缓存最大条目数。 |
| `area_channels_cache_ttl` | `1800.0` | 域频道缓存有效期（秒）。 |
| `person_profiles_cache_max_entries` | `3000` | 用户详细资料缓存最大条目数。 |
| `person_profile_cache_ttl` | `1800.0` | 用户详细资料缓存有效期（秒）。 |
| `area_user_nickname_cache_max_entries` | `20000` | 域内昵称缓存最大条目数。 |
| `area_user_nickname_cache_ttl` | `300.0` | 域内昵称缓存有效期（秒）。 |
| `area_members_page_cache_max_entries` | `200` | 域成员分页缓存最大条目数。 |
| `area_members_page_cache_ttl` | `10.0` | 域成员分页缓存有效期（秒）。 |

## 语音配置

| 字段                              | 默认值                 | 说明                  |
|---------------------------------|---------------------|---------------------|
| `agora_app_id`                  | SDK 内置值             | Agora App ID。       |
| `agora_init_timeout`            | `1800`              | 语音后端初始化超时。          |
| `voice_backend`                 | `browser`           | 当前实现使用浏览器后端。        |
| `voice_browser_headless`        | `True`              | 是否无头运行浏览器。          |
| `voice_browser_executable_path` | `""`                | 自定义 Chromium 路径。    |
| `voice_agora_sdk_url`           | Agora 官方 JS SDK URL | 浏览器后端加载的 Agora SDK。 |

## OneBot 配置

详见 [OneBot 适配](../adapters/index.md)。
