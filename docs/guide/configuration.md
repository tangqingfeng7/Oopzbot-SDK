# 配置方法

SDK 的所有能力都从 `OopzConfig` 开始。

```python
from oopz_sdk import OopzConfig, RetryConfig, HeartbeatConfig, ProxyConfig, AutoRecallConfig

config = OopzConfig(
    device_id="设备 ID",
    person_uid="机器人账号 UID",
    jwt_token="JWT Token",
    private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    retry=RetryConfig(interval=0.35, timeout=(10, 30), max_attempts=3),
    heartbeat=HeartbeatConfig(interval=10.0, reconnect_interval=2.0),
    proxy=ProxyConfig(http="http://127.0.0.1:7890", https="http://127.0.0.1:7890"),
    auto_recall=AutoRecallConfig(enabled=False, delay=30.0),
)
```

## 必填配置

| 字段            | 类型    | 说明                           |
|---------------|-------|------------------------------|
| `device_id`   | `str` | 设备 ID。不能为空。                  |
| `person_uid`  | `str` | 当前登录账号 UID，通常也是机器人 UID。不能为空。 |
| `jwt_token`   | `str` | 登录态 JWT。不能为空。                |
| `private_key` | `str  | bytes                        | key object` | RSA 私钥，用于签名请求。不能为空。 |

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

| 字段                       | 默认值                             | 说明                       |
|--------------------------|---------------------------------|--------------------------|
| `ignore_self_messages`   | `True`                          | 忽略自己发出的消息，避免机器人回复自己导致循环。 |
| `use_announcement_style` | `False`                         | 频道消息默认加 `IMPORTANT` 样式。  |
| `auto_recall`            | `AutoRecallConfig(False, 30.0)` | 发送频道消息后自动撤回。             |


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
