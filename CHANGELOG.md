# Changelog

## Unreleased

### 新增

- 补充 IM 扩展接口文档与实现：`send_message_v2`、会话列表、私信历史、已读状态、置顶消息、未读统计、系统消息、消息反应与消息详情。
- 补充用户侧基础查询接口：新手引导、通知设置、备注名、拉黑检查、隐私设置、通知偏好、实名认证状态、好友列表、黑名单、好友请求、钻石余额、混音器设置。
- 补充用户侧操作接口：设置备注名、发送好友申请、处理好友申请、删除好友、编辑隐私设置、编辑通知设置。

### 文档

- README 新增 IM 扩展接口示例、用户侧查询示例、用户侧操作示例和当前已覆盖接口清单。

## 0.4.3 - 2026-04-15

### 修复

- 将许可证声明切回兼容旧版 PyPI 校验链路的写法，避免上传阶段因 `license-expression` 字段被拒绝。

## 0.4.2 - 2026-04-15

### 修复

- 修复 PyPI 上传兼容性问题，移除会触发 `license-file` 校验失败的发布元数据字段。

## 0.4.1 - 2026-04-15

### 改进

- 补齐 PyPI 发布元数据，包括项目链接与许可证声明。
- CI 新增 `sdist` / `wheel` 构建、`twine check` 校验和基于 tag 的 PyPI 发布流程。
- README 补充 PyPI 安装说明、发布版最小示例和本地发布前检查步骤。
- 清理构建产物忽略规则与发布清单告警，减少发布过程中的无效噪音。

## 0.4.0 - 2026-04-15

### 新增

- 新增 `smoke/smoke_test.py` 真实环境联调入口，支持通过环境变量验证频道消息、撤回、上传、发图、私信和 WebSocket 认证。
- 新增高频查询结果模型：
  - `ChannelGroupsResult`
  - `JoinedAreasResult`
  - `SelfDetail`
  - `PersonDetail`
  - `ChannelSetting`
  - `VoiceChannelMembersResult`
  - `DailySpeechResult`
  - `AreaBlocksResult`
  - `ChannelMessage`

### 改进

- 为幂等读接口和上传签名请求统一了限流 / 网络异常重试策略。
- 为 `get_area_members`、`get_area_channels`、`get_joined_areas`、`get_self_detail` 增加了更明确的 `from_cache` 语义。
- `OopzClient` 生命周期事件新增 `auth_ok` / `auth_failed`，将“已发送认证”和“认证成功/失败”区分开。
- 网络异常统一翻译为 `OopzConnectionError`。

## 0.3.0 - 2026-04-14

### 变更

- `send_message`、`send_private_message`、上传相关接口不再返回原始 `requests.Response` 或错误字典，改为稳定结果模型。
- 公开查询接口失败时统一抛出 `OopzError` 体系异常，不再用 `{"error": ...}` 或空列表表示失败。
- `OopzConfig` 现在要求 `private_key` 在初始化时必须提供。
- `OopzClient.on_chat_message` 回调参数从原始 `dict` 改为 `ChatMessageEvent`。

### 新增

- 新增结果模型与类型标注：
  - `MessageSendResult`
  - `UploadResult`
  - `UploadAttachment`
  - `PrivateSessionResult`
  - `OperationResult`
  - `ChatMessageEvent`
  - `LifecycleEvent`
- 新增统一响应处理模块，统一 HTTP/业务错误翻译。
- 新增 `on_lifecycle_event` 回调，用于观测 WebSocket 生命周期。
- 新增私信图片上传示例。
- 新增 CI 工作流。

### 改进

- 收紧配置校验，初始化阶段尽早暴露缺失配置。
- 统一上传、私信、频道管理和常用查询接口的错误行为。
- 为包增加更完整的测试覆盖。
