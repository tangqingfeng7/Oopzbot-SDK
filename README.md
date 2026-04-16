<div align="center">

# Oopz SDK

[![Language](https://img.shields.io/badge/language-python-green.svg?style=plastic)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg?style=plastic)](./LICENSE)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![PyPI](https://img.shields.io/pypi/v/oopz-sdk)

  基于 Oopz 平台接口实现的 Python SDK


[仓库](https://github.com/tangqingfeng7/Oopzbot-SDK)
·
[变更记录](./CHANGELOG.md)
·
[PyPI](https://pypi.org/project/oopz-sdk/)

</div>

## 准备工作

### 安装

```bash
pip install oopz-sdk
```

如果需要升级到最新版本：

```bash
pip install --upgrade oopz-sdk
```

兼容版本：`Python 3.10+`

### 从源码安装

```bash
pip install -e .
```

### 安装开发依赖

```bash
pip install -e .[dev]
```

### 使用

需要使用的地方：

```python
from oopz import OopzClient, OopzConfig, OopzSender
```

### 凭证准备

创建 `OopzConfig` 时，以下字段为必填：

- `device_id`
- `person_uid`
- `jwt_token`
- `private_key`

如果你要直接使用默认上下文发频道消息，还需要：

- `default_area`
- `default_channel`

补充说明：

- `private_key` 支持 PEM 字符串、`bytes`，或已加载好的私钥对象
- `default_area`、`default_channel` 不是全局必填，只在依赖默认频道发送时需要
- `request_timeout`、`rate_limit_interval`、缓存相关配置都可以按需覆盖

### 兼容提示

> 当前 SDK 更适合围绕 Oopz Web 侧高频能力做集成。  
> 已覆盖的接口较多，但不同接口组的稳定程度并不完全一致，接入前建议先跑一次真实联调。

## 使用方式

### 快速入门

#### 步骤 1

先创建配置对象：

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

#### 步骤 2

创建 `OopzSender`，发送一条最小测试消息：

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    result = sender.send_message("Hello from oopz-sdk")
    print(result.message_id)
```

如果这里能正常拿到 `message_id`，说明最基础的鉴权和消息发送链路已经跑通。

#### 步骤 3

如果你需要收消息和做实时处理，再启动 `OopzClient`：

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

### 常见用法

#### 发送私信

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    result = sender.send_private_message("目标UID", "你好")
    print(result.channel, result.message_id)
```

#### 上传图片并发送

```python
from oopz import OopzSender, UploadResult

with OopzSender(config) as sender:
    upload: UploadResult = sender.upload_file("demo.png", file_type="IMAGE", ext=".png")
    print(upload.attachment.url)

    sender.upload_and_send_image("demo.png", text="图片说明")
```

#### 获取频道最近消息

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    messages = sender.get_channel_messages(size=20)
    for message in messages:
        print(message.person, message.content)
```

### 备注

也可以不设置默认域和默认频道，而是在调用时显式传入：

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    sender.send_message("显式指定发送位置", area="域ID", channel="频道ID")
```

## 使用 API

当前 SDK 已覆盖这几组高频能力：

- 频道消息：`send_message`、`send_message_v2`、`recall_message`、`get_channel_messages`
- 私信与会话：`open_private_session`、`send_private_message`、`list_sessions`、`get_private_messages`、`save_read_status`
- IM 辅助查询：`get_top_messages`、`get_areas_unread`、`get_areas_mention_unread`、`get_gim_reactions`、`get_gim_message_details`
- 系统消息：`get_system_message_unread_count`、`get_system_message_list`
- 用户资料与账号查询：`get_self_detail`、`get_person_detail`、`get_person_detail_full`、`get_person_infos_batch`、`get_level_info`
- 用户侧查询：`get_novice_guide`、`get_notice_setting`、`get_user_remark_names`、`check_block_status`、`get_privacy_settings`、`get_notification_settings`、`get_real_name_auth_status`、`get_friend_list`、`get_blocked_list`、`get_friend_requests`、`get_diamond_remain`、`get_mixer_settings`
- 用户侧操作：`set_user_remark_name`、`send_friend_request`、`respond_friend_request`、`remove_friend`、`edit_privacy_settings`、`edit_notification_settings`
- 域与频道管理：已加入域、域详情、频道列表、频道创建/删除/复制、频道设置查询/编辑、私密频道成员搜索
- 域成员管理：成员搜索、成员列表、身份组编辑、移出域、域封禁/解封、禁言/禁麦、语音频道成员查询
- 文件上传：通用上传、上传后发图、上传后私信图片

## 公开类型与返回值

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

聊天事件回调接收：

- `ChatMessageEvent`
- `LifecycleEvent`

其中带缓存回退能力的读接口会通过 `from_cache` 明确标识缓存命中，例如：

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

示例：

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

## 示例目录

[`examples`](./examples/) 目录下存放示例脚本，目前主要包括：

- `send_message.py`：最小发送消息
- `reply_bot.py`：接收消息并自动回复
- `upload_private_image.py`：上传图片并通过私信发送

## 真实联调

项目提供了真实联调脚本 [`smoke/smoke_test.py`](./smoke/smoke_test.py)，不会进入默认 CI。

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

## 参与开发

### 环境配置

```bash
pip install -e .[dev]
```

### 单元测试

项目当前提供公开 API、错误翻译、模型返回和 WebSocket 生命周期相关测试，位于 [`tests`](./tests/) 目录。

执行方法：

```bash
python -m pytest tests -q
```

### 打包检查

```bash
python -m build
python -m twine check dist/*
```
