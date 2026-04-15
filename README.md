# Oopz SDK

Oopz 平台 Python SDK，提供频道消息、私信、文件上传、平台查询与 WebSocket 实时事件能力。

`v0.4` 在 `v0.3` 的统一异常和结果模型基础上，继续补了三件事：

- 真实联调入口 `smoke/smoke_test.py`
- 更统一的读接口重试与缓存回退语义
- 高频查询结果模型与更明确的 WebSocket 认证生命周期

## 安装

### 从 PyPI 安装

```bash
pip install oopz-sdk
```

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
- `requests`
- `cryptography`
- `websocket-client`
- `pillow`

## 配置

创建 `OopzConfig` 时，以下字段为必填：

- `device_id`
- `person_uid`
- `jwt_token`
- `private_key`

如果你要依赖默认上下文发送频道消息，还需要配置：

- `default_area`
- `default_channel`

当前稳定配置面还包括：

- `request_timeout`
- `rate_limit_interval`
- `area_members_cache_ttl`
- `area_members_stale_ttl`
- `query_cache_ttl`
- `query_cache_stale_ttl`

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

### 发布版最小示例

下面的示例只依赖公开导出接口，适合通过 `pip install oopz-sdk` 安装后的最小验证：

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
    result = sender.send_message("Hello from PyPI")
    print(result.message_id)
```

## WebSocket 实时事件

聊天消息回调接收 `ChatMessageEvent`，生命周期回调接收 `LifecycleEvent`。

`v0.4` 的生命周期状态包括：

- `connecting`
- `connected`
- `auth_sent`
- `auth_ok`
- `auth_failed`
- `reconnecting`
- `closed`
- `error`

其中 `auth_sent` 表示已发起认证，`auth_ok` / `auth_failed` 才表示协议级认证结果。

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

发送、上传和管理类接口返回：

- `MessageSendResult`
- `UploadResult`
- `UploadAttachment`
- `PrivateSessionResult`
- `OperationResult`

高频查询接口返回：

- `ChannelGroupsResult`
- `JoinedAreasResult`
- `SelfDetail`
- `PersonDetail`
- `ChannelSetting`
- `VoiceChannelMembersResult`
- `DailySpeechResult`
- `AreaBlocksResult`
- `list[ChannelMessage]`

其中带缓存回退能力的读接口会通过 `from_cache` 明确标识缓存命中，而不是让调用方猜测：

- `get_area_members`
- `get_area_channels`
- `get_joined_areas`
- `get_self_detail`

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
from oopz import OopzApiError, OopzConnectionError, OopzRateLimitError, OopzSender

try:
    with OopzSender(config) as sender:
        sender.send_message("test")
except OopzRateLimitError as exc:
    print(f"被限流，建议 {exc.retry_after}s 后重试")
except OopzConnectionError as exc:
    print(f"网络失败: {exc}")
except OopzApiError as exc:
    print(f"请求失败: {exc} (HTTP {exc.status_code})")
```

## 示例

`examples/` 目录包含：

- `send_message.py`：最小发送消息
- `reply_bot.py`：接收消息并自动回复
- `upload_private_image.py`：上传图片并通过私信发送

## 真实联调

`smoke/smoke_test.py` 用于跑真实账号联调，不会进入默认 CI。

### 联调前准备

- 准备测试域和测试频道
- 准备可用的 `device_id / person_uid / jwt_token / private_key`
- 如需私信联调，准备 `OOPZ_TARGET_UID`
- 如需严格验证 WebSocket 收消息，准备第二个账号在等待窗口内发消息

### 环境变量

- `OOPZ_DEVICE_ID`
- `OOPZ_PERSON_UID`
- `OOPZ_JWT_TOKEN`
- `OOPZ_PRIVATE_KEY` 或 `OOPZ_PRIVATE_KEY_FILE`
- `OOPZ_AREA_ID`
- `OOPZ_CHANNEL_ID`
- `OOPZ_TARGET_UID` 可选
- `OOPZ_SMOKE_IMAGE` 可选
- `OOPZ_SMOKE_EXPECT_WS_MESSAGE=1` 可选
- `OOPZ_SMOKE_WS_WAIT_SECONDS` 可选，默认 `20`

### 执行方式

```bash
python smoke/smoke_test.py
```

### 通过标准

- 域列表、自身信息、频道列表、域成员查询成功
- 频道发消息和撤回成功
- 文件上传和发图成功
- WebSocket 至少完成 `auth_ok`
- 提供 `OOPZ_TARGET_UID` 时私信成功
- 设置 `OOPZ_SMOKE_EXPECT_WS_MESSAGE=1` 时，等待窗口内收到真实消息事件

### 常见失败原因

- `jwt_token` 过期，导致 HTTP 或 WebSocket 认证失败
- `private_key` 与账号不匹配，导致签名异常
- `default_area/default_channel` 或环境变量填写错误
- 给自己发私信，触发平台已知异常
- 仅用单账号联调时，WebSocket 默认无法验证“收到他人消息”这条链路

## 本地发布前检查

运行单元测试：

```bash
python -m pytest tests -q
```

构建源码包和 wheel：

```bash
python -m build
```

校验发布产物元数据和 README 渲染：

```bash
python -m twine check dist/*
```

可选：在干净虚拟环境验证 wheel 安装和导入：

```bash
pip install dist/oopz_sdk-0.4.0-py3-none-any.whl
python -c "import oopz; print(oopz.__version__)"
```

可选：先上传到 TestPyPI 做一次发布演练：

```bash
python -m twine upload --repository testpypi dist/*
```

## 版本变更

- `v0.3 -> v0.4` 变化见 [CHANGELOG.md](CHANGELOG.md)
