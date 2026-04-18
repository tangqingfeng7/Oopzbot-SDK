# Changelog

## Unreleased

## 0.5.0 - 2026-04-19

### 变更

- 包入口从 `oopz` 迁移为 `oopz_sdk`，旧 `oopz` 包正式移除，对外导出统一收口到 `oopz_sdk.__init__`。
- SDK 目录重组为 `auth`、`client`、`config`、`events`、`exceptions`、`models`、`services`、`transport`、`utils`、`testing`、`adapters` 等模块，原先分散实现改为按职责拆分，并加入包内 `README`、`py.typed`、调试入口和基础脚手架。
- `OopzBot` 改为统一管理 REST、WebSocket 和事件调度的高层入口，旧生命周期写法收敛为函数式事件注册；`on`、`event`、属性式事件入口统一走同一套注册路径，并新增 `on_recall`。
- 消息发送、私信、上传和部分上下文调用统一改为异步流程；HTTP 与 WebSocket 共用同一事件循环，避免连接关闭后出现循环状态异常。
- 事件上下文移除对默认 `area`、`channel` 的直接依赖，最终交给底层 service 解析；上下文同时补齐私聊发送、回复和处理能力。
- 兼容层经历从旧 `oopz` 迁入 `oopz_sdk`、再逐步清理的过程；最终删除 `compat` 目录、旧私聊 service、旧公开接口检查和 `smoke` 联调脚本，保留 `0.5.0` 需要继续维护的公开结构。
- 旧 sender facade 合并进 REST client，`OopzSender` 别名移除；示例、文档和对外入口全部切换到 `oopz_sdk`。

### 新增

- 新增 `OopzRESTClient`、`OopzWSClient`、`OopzBot`、`OopzApiMixin`、`Signer` 等新结构下的公开入口。
- 新增 `EventRegistry`、`EventDispatcher`、`EventParser`、`EventContext`，支持 `on` / `event` 注册，以及 `on_message`、`on_private_message`、`on_recall`、`on_ready`、`on_error`、`on_close`、`on_reconnect`、`on_raw_event` 等入口。
- 新增上下文便捷方法 `ctx.reply()`、`ctx.send()`、`ctx.recall()`，支持频道消息与私信场景共用。
- 新增 `Segment` 消息片段体系、图片片段模型、图片工具和消息构造工具，支持图文混合消息，并让图片片段接管附件发送流程。
- 新增 `oopz_sdk.models` 下的区域、频道、成员、消息、附件、事件、响应、片段等模型拆分文件与对外导出。
- 新增 `oopz_sdk.transport` 下的 HTTP、WebSocket、代理传输层；新增 `oopz_sdk.response` 响应辅助函数与分类异常模块。
- 新增 `oopz_sdk.testing` 测试辅助、`oopz_sdk.utils` 工具函数、`oopz_sdk.adapters.onebot` 适配入口，以及包内 `README` 与 `py.typed`。
- 新增 `Moderation` 管理相关 service 和 `oopz_sdk/test-client.py` 调试入口。
- 补充 IM 扩展接口：`send_message_v2`、会话列表、私信历史、已读状态、置顶消息、未读统计、系统消息、消息反应、消息详情。
- 补充用户侧基础查询接口：新手引导、通知设置、备注名、拉黑检查、隐私设置、通知偏好、实名认证状态、好友列表、黑名单、好友请求、钻石余额、混音器设置。
- 补充用户侧操作接口：设置备注名、发送好友申请、处理好友申请、删除好友、编辑隐私设置、编辑通知设置。
- 为各个 service 注入 bot 引用，便于消息、媒体、区域、频道、成员和管理相关能力互相协作调用。
- 新增私信事件与撤回事件处理。
- 新增可选依赖缺失时的降级提示，缺少图片处理或 WebSocket 相关依赖时会给出更明确的报错信息。

### 改进

- 完善 SDK 模型与 service 接口，补齐区域、频道、成员、消息、媒体、管理相关能力，补充分页结果、响应结构和更多服务层检查。
- 重构 REST 客户端与 HTTP client 结构，统一请求入口、错误处理、返回内容和更多检查逻辑，同时清理无用代码。
- WebSocket 底层改用 `aiohttp`，并改进重连、默认行为和回调衔接方式。
- 媒体上传在 bot 初始化阶段完成 service 准备；service 之间可通过 bot 串联调用。
- 整理 bot 高层方法与 context 高层方法，统一 `send`、`reply`、`recall` 等常用入口。
- 更新 README、包内文档和示例脚本，适配新的异步消息发送、回复、私信图片上传流程和兼容层收缩后的使用方式。
- 更新打包配置与清单，只发布 `oopz_sdk` 包内容，并确保 `py.typed` 一并进入发布产物。
- 同步整理 `.gitignore`、`MANIFEST.in` 和发布相关文件，让当前目录结构和发布产物保持一致。

### 修复

- 修复 `rest.py` 结构问题，改善 HTTP client 分层并清理无用代码。
- 修复 WebSocket 异步调用路径，避免多事件循环和循环提前关闭带来的连接问题。
- 修复上传处理、bot 默认值、媒体初始化时机与消息处理打包问题。
- 修复事件解析中 `message` 内容填充不准确的问题。
- 修复事件上下文兼容性回退，保证旧调用方式在新事件模型下仍能正确取到消息和上下文信息。
- 修复消息片段兼容性回退，补齐 REST、上下文和各 service 对消息片段的处理。
- 修复私聊相关上下文逻辑、事件消息内容解析，以及消息分发过程中的若干问题。
- 修复媒体上传异常处理和外链下载安全问题。
- 修复打包检查在 Python 3.10 环境下缺少 TOML 读取依赖的问题。
- 调整发布元数据写法，避免 PyPI 拒收 `license-file` 和 `license-expression` 字段。

### 测试

- 新增 `tests/test_oopz_sdk_services.py`，覆盖配置、签名、响应辅助、消息与私信、service、bot、事件、媒体、传输和可选依赖行为。
- 新增 `tests/test_examples.py`，确保示例脚本可以被加载而不直接执行主流程。
- 新增 `tests/test_packaging.py`，检查发布配置仅打包 `oopz_sdk`，并验证 `py.typed` 会进入发布产物。

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
