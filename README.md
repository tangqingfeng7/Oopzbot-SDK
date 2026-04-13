# Oopz SDK

Oopz 平台 Python SDK。

 提供 HTTP API、文件上传、私信、频道管理与 WebSocket 实时事件能力 

 目标是给开发者一个足够直接、足够轻量、能快速接入 Oopz 的 Python 开发框架 

安装 · 示例 · 测试

## 准备工作

在使用 SDK 之前，你需要准备以下信息：

- `device_id`
- `person_uid`
- `jwt_token`
- `private_key`

其中 `private_key` 支持 PEM 字符串、字节，或者已经加载好的 `cryptography` 私钥对象。

## 安装

### 从源码安装

在 `sdk/` 目录下执行：

```bash
pip install -e .
```

如果需要开发依赖：

```bash
pip install -e .[dev]
```

### 直接安装运行依赖

```bash
pip install requests[socks] cryptography websocket-client pillow
```

### 兼容版本

当前 SDK 兼容 `Python 3.10+`。

## 使用

需要使用的地方：

```python
import oopz
```

或者按公开接口导入：

```python
from oopz import OopzClient, OopzConfig, OopzSender
```

## 使用方式

### 快速入门

#### 步骤1

创建 `OopzConfig`，填入认证和默认上下文信息：

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

#### 步骤2

如果你只需要调用 HTTP API，创建 `OopzSender`：

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    sender.send_message("Hello Oopz!")
```

#### 步骤3

如果你需要监听实时事件，创建 `OopzClient` 并实现回调：

```python
from oopz import OopzClient, OopzSender

sender = OopzSender(config)


def on_message(message: dict) -> None:
    content = str(message.get("content") or "")
    if content.strip().lower() == "ping":
        sender.send_message(
            "pong",
            area=message.get("area"),
            channel=message.get("channel"),
        )


client = OopzClient(config, on_chat_message=on_message)
client.start()
```

### 备注

如果你只发消息，不接收实时事件，只使用 `OopzSender` 即可。

如果你既要接收消息又要调用 API，常见做法是 `OopzClient + OopzSender` 组合使用。

## 使用 API

如果你要直接使用平台 API，可以通过 `OopzSender` 调用，例如：

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    sender.send_message("一条普通消息")
    sender.send_private_message("目标UID", "一条私信")
    sender.get_area_members(area="域ID")
    sender.get_area_channels(area="域ID")
```

### 文件上传

SDK 内置了图片和音频上传能力：

```python
with OopzSender(config) as sender:
    sender.upload_file("/path/to/image.png")
    sender.upload_file_from_url("https://example.com/image.png")
    sender.upload_audio_from_url("https://example.com/demo.mp3")
    sender.upload_and_send_image("/path/to/image.png", text="附带说明")
```

### 常用能力

`OopzSender` 当前已经集成了以下常用能力：

- 发送频道消息
- 发送私信
- 上传图片 / 音频
- 获取域成员
- 获取频道列表
- 创建 / 修改频道
- 禁言 / 禁麦 / 撤回消息
- 查询语音频道成员

## 异常处理

SDK 公开异常层级如下：

```text
OopzError
├─ OopzAuthError
├─ OopzConnectionError
└─ OopzApiError
   └─ OopzRateLimitError
```

发送消息主链路已经接入 SDK 异常：

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

`examples` 目录下存放了最小可运行示例：

```text
examples/
├── reply_bot.py      # 接收消息并自动回复示例
└── send_message.py   # 最小发送消息示例
```

可以直接参考下面两个文件：

- [examples/send_message.py](examples/send_message.py)
- [examples/reply_bot.py](examples/reply_bot.py)

## 目录结构

SDK 目录结构如下：

```text
sdk/
├── examples/
├── oopz/
├── tests/
├── MANIFEST.in
├── pyproject.toml
└── README.md
```

其中：

- `oopz/` 是 SDK 源码
- `examples/` 是示例代码
- `tests/` 是公开接口的基础测试

## 参与开发

### 环境配置

在 `sdk/` 目录下执行：

```bash
pip install -e .[dev]
```

### 单元测试

项目当前提供公开接口的基础测试，位于 `tests` 目录中。

执行方式：

```bash
python -m pytest tests -q
```

### 构建

如果你要本地构建 wheel：

```bash
python -m pip wheel . --no-deps -w dist-check
```

如果你已经安装了 `build`，也可以执行：

```bash
python -m build
```

## 当前状态说明

这个 SDK 目前已经具备独立打包、安装、测试和基础示例能力，但整体仍处于持续完善阶段。

后续更适合继续补强的方向包括：

- 更完整的异常契约
- 更稳定的返回值模型
- 更细的类型标注
- 更完整的示例和 CI
