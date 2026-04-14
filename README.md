# Oopz SDK

Oopz 平台 Python SDK，提供消息发送、私信、文件上传、频道管理和 WebSocket 实时事件能力。

SDK 的公开契约已经统一到两条主线：

- 失败统一抛出 `OopzError` 体系异常
- 成功优先返回稳定结果模型，而不是原始 `requests.Response`

## 安装

### 从源码安装

```bash
pip install -e .
```

开发依赖：

```bash
pip install -e .[dev]
```

### 运行环境

- Python `3.10+`
- `requests[socks]`
- `cryptography`
- `websocket-client`
- `pillow`

## 配置

创建 `OopzConfig` 时，以下字段为必填：

- `device_id`
- `person_uid`
- `jwt_token`
- `private_key`

其中 `private_key` 支持：

- PEM 字符串
- PEM 字节串
- 已加载好的 `cryptography` 私钥对象

如果你要依赖默认上下文发送频道消息，还需要配置：

- `default_area`
- `default_channel`

```python
from oopz import OopzConfig

config = OopzConfig(
    device_id="你的设备ID",
    person_uid="你的用户UID",
    jwt_token="你的JWT Token",
    private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    default_area="默认域ID",
    default_channel="默认频道ID",
)
```

## 快速开始

### 发送消息

```python
from oopz import MessageSendResult, OopzConfig, OopzSender

config = OopzConfig(
    device_id="你的设备ID",
    person_uid="你的用户UID",
    jwt_token="你的JWT Token",
    private_key="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
    default_area="默认域ID",
    default_channel="默认频道ID",
)

with OopzSender(config) as sender:
    result: MessageSendResult = sender.send_message("Hello Oopz!")
    print(result.message_id)
```

### 发送私信

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    result = sender.send_private_message("目标UID", "你好")
    print(result.channel, result.message_id)
```

### 上传并发图

```python
from oopz import OopzSender, UploadResult

with OopzSender(config) as sender:
    upload: UploadResult = sender.upload_file("demo.png", file_type="IMAGE", ext=".png")
    print(upload.attachment.url)

    sender.upload_and_send_image("demo.png", text="图片说明")
```

## WebSocket 实时事件

聊天消息回调接收 `ChatMessageEvent`，生命周期事件可通过 `on_lifecycle_event` 订阅。

```python
from oopz import ChatMessageEvent, LifecycleEvent, OopzClient, OopzSender

sender = OopzSender(config)


def on_message(event: ChatMessageEvent) -> None:
    if event.content.strip().lower() == "ping":
        sender.send_message("pong", area=event.area, channel=event.channel)


def on_lifecycle(event: LifecycleEvent) -> None:
    print(event.state, event.reason, event.error)


client = OopzClient(
    config,
    on_chat_message=on_message,
    on_lifecycle_event=on_lifecycle,
)
client.start()
```

## 公开返回值

当前常用公开返回值模型包括：

- `MessageSendResult`
- `UploadResult`
- `UploadAttachment`
- `PrivateSessionResult`
- `OperationResult`
- `ChatMessageEvent`
- `LifecycleEvent`

常用查询接口返回稳定的 `dict` / `list` 结构，并附带类型标注：

- `get_area_members`
- `get_area_channels`
- `get_joined_areas`
- `get_channel_messages`

## 异常处理

异常层级：

```text
OopzError
├─ OopzAuthError
├─ OopzConnectionError
└─ OopzApiError
   └─ OopzRateLimitError
```

```python
from oopz import OopzApiError, OopzRateLimitError, OopzSender

try:
    with OopzSender(config) as sender:
        sender.send_message("test")
except OopzRateLimitError as exc:
    print(f"被限流，建议 {exc.retry_after}s 后重试")
except OopzApiError as exc:
    print(f"请求失败: {exc} (HTTP {exc.status_code})")
```

## 示例

`examples/` 目录包含：

- `send_message.py`：最小发送消息
- `reply_bot.py`：接收消息并自动回复
- `upload_private_image.py`：上传图片并通过私信发送

## 测试与构建

运行测试：

```bash
python -m pytest tests -q
```

构建 wheel：

```bash
python -m pip wheel . --no-deps -w dist-check
```

如果本地已安装 `build`：

```bash
python -m build
```

## v0.3 变更

`v0.2 -> v0.3` 的主要变化见 [CHANGELOG.md](CHANGELOG.md)。
