# Oopz SDK

`oopz` 是一个面向 Oopz 平台的 Python SDK，提供三类核心能力：

- `OopzSender`：HTTP API 调用、消息发送、私信、文件上传。
- `OopzClient`：WebSocket 实时事件接收与自动重连。
- `Signer`：Oopz 请求签名工具。

这次目录结构按 `botpy` 的常见发布方式收口成了独立 SDK 形态：包源码、示例、测试、打包元数据都放在 `sdk/` 下，便于单独构建和发布。

## 目录结构

```text
sdk/
├─ oopz/
├─ examples/
├─ tests/
├─ MANIFEST.in
├─ pyproject.toml
└─ README.md
```

## 安装

在 `sdk/` 目录下安装：

```bash
pip install -e .
```

如果你只想装运行依赖：

```bash
pip install requests[socks] cryptography websocket-client pillow
```

开发环境：

```bash
pip install -e .[dev]
```

## 快速开始

### 发送消息

```python
from oopz import OopzConfig, OopzSender

config = OopzConfig(
    device_id="你的设备ID",
    person_uid="你的用户UID",
    jwt_token="你的JWT Token",
    private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    default_area="默认域ID",
    default_channel="默认频道ID",
)

with OopzSender(config) as sender:
    sender.send_message("Hello Oopz!")
```

### 接收消息

```python
from oopz import OopzClient, OopzConfig

config = OopzConfig(
    device_id="你的设备ID",
    person_uid="你的用户UID",
    jwt_token="你的JWT Token",
    private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
)

def on_message(message: dict) -> None:
    print(message.get("content"))

client = OopzClient(config, on_chat_message=on_message)
client.start()
```

## 公开接口

### `OopzConfig`

核心字段：

| 字段 | 说明 |
| --- | --- |
| `device_id` | 设备 ID |
| `person_uid` | 用户 UID |
| `jwt_token` | Oopz JWT Token |
| `private_key` | RSA 私钥，支持 PEM 字符串、字节或已加载对象 |
| `default_area` | 默认域 ID |
| `default_channel` | 默认频道 ID |
| `rate_limit_interval` | 最小请求间隔 |
| `request_timeout` | HTTP 请求超时，默认 `(10, 30)` |

### `OopzSender`

常用方法：

- `send_message()`
- `send_private_message()`
- `open_private_session()`
- `upload_file()`
- `upload_and_send_image()`
- `get_area_members()`
- `get_area_channels()`
- `recall_message()`

`OopzSender` 现在支持上下文管理：

```python
with OopzSender(config) as sender:
    sender.send_message("hello")
```

### `OopzClient`

常用方法：

- `start()`
- `start_async()`
- `stop()`

### `Signer`

常用方法：

- `sign()`
- `oopz_headers()`
- `client_message_id()`
- `timestamp_ms()`
- `timestamp_us()`

## 异常

公开异常层级：

```text
OopzError
├─ OopzAuthError
├─ OopzConnectionError
└─ OopzApiError
   └─ OopzRateLimitError
```

目前发送消息这条主链路已经接到 SDK 异常上：

```python
from oopz import OopzApiError, OopzRateLimitError

try:
    with OopzSender(config) as sender:
        sender.send_message("test")
except OopzRateLimitError as exc:
    print(f"被限流，建议 {exc.retry_after}s 后重试")
except OopzApiError as exc:
    print(f"请求失败: {exc} (HTTP {exc.status_code})")
```

## 示例

示例文件放在 [examples/send_message.py](/D:/github/Oopzbot/sdk/examples/send_message.py) 和 [examples/reply_bot.py](/D:/github/Oopzbot/sdk/examples/reply_bot.py)。

## 测试

在 `sdk/` 目录下运行：

```bash
python -m pytest tests -q
```

## 构建

在 `sdk/` 目录下运行：

```bash
python -m build
```

生成物会输出到 `sdk/dist/`。
