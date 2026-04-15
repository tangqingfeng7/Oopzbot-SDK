# Oopz SDK

Oopz 平台 Python SDK，提供频道消息、私信、文件上传、平台查询、用户侧查询与操作，以及 WebSocket 实时事件能力。


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

## 扩展接口示例

### IM 扩展接口

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    sender.send_message_v2("带 @ 的消息", mentionList=["目标UID"])

    sessions = sender.list_sessions()
    private_messages = sender.get_private_messages("私信频道ID", size=20)
    sender.save_read_status("私信频道ID", message_id="最新消息ID")

    top_messages = sender.get_top_messages()
    system_unread = sender.get_system_message_unread_count()
    system_messages = sender.get_system_message_list()

    print(len(sessions), len(private_messages), len(top_messages), system_unread, len(system_messages))
```

### 用户侧查询接口

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    self_detail = sender.get_self_detail()
    friend_requests = sender.get_friend_requests()
    privacy = sender.get_privacy_settings()
    mixer = sender.get_mixer_settings()

    print(self_detail.uid, len(friend_requests), privacy.get("everyoneAdd"), mixer.get("isFreeSpeech"))
```

### 用户侧操作接口

```python
from oopz import OopzSender

with OopzSender(config) as sender:
    sender.set_user_remark_name("目标UID", "新备注")
    sender.send_friend_request("目标UID")
    sender.respond_friend_request("目标UID", agree=True, friend_request_id="请求ID")
    sender.edit_privacy_settings(
        everyone_add=True,
        with_friend_add=False,
        area_member_add=True,
        not_friend_chat=False,
    )
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

## 已覆盖接口

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

  仍在整理,未稳定。

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
pip install dist/oopz_sdk-0.4.3-py3-none-any.whl
python -c "import oopz; print(oopz.__version__)"
```

可选：先上传到 TestPyPI 做一次发布演练：

```bash
python -m twine upload --repository testpypi dist/*
```

## 版本变更

- `v0.3 -> v0.4` 变化见 [CHANGELOG.md](CHANGELOG.md)
