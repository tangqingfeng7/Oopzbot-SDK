# Changelog

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
