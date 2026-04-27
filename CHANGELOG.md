# Changelog

## Unreleased

### 变更

- `Message.send_message` 的 `auto_recall` 改为三态 `Optional[bool]`，默认 `None`：不传时跟随 `OopzConfig.auto_recall_enabled`；`True` 强制撤回，`False` 强制保留（用于全局开启后想保留公告 / 日报等个别消息的场景）。原先默认 `False` + 内部只检查 `auto_recall and ...` 的写法，导致"全局 `auto_recall_enabled=True` 但 `send_message()` 不传 `auto_recall` 就不会撤回"，与 `OopzConfig.auto_recall_enabled` 字段名直觉相反。
- `ChannelEdit.accessible` 属性内部更名为 `accessible_roles`（Pydantic alias 仍为 `"accessible"`，`to_request_body()` 产出的 JSON 字段不变，对服务端完全兼容）。直接通过属性访问 `.accessible` 的调用方需要改为 `.accessible_roles`。
- `HttpTransport.request_json` 与 `OperationResult.from_api` 对 `status` 字段改为严格布尔：字符串 `"false"` / `"0"` / `"no"` 等会被正确判为失败，不再因为 Python 真值规则被当成"字符串 true"而误判成功。若服务端个别接口用字符串下发 `status`，之前被静默当成功的响应现在会按真实失败处理。

### 新增

- `oopz_sdk.utils.payload.coerce_bool`：严格把 API payload 里的值转成 `bool`——`bool` 原样；`int` / `float` 按 `!= 0`；`str` 大小写不敏感白名单（`true/1/yes/y/on` → True，`false/0/no/n/off/""` → False）；未知字面量走 `default` 兜底。与 `safe_json_loads` 一并从 `oopz_sdk.utils` 导出。
- `ChannelType.AUDIO`：语音频道在协议里可能返回 `AUDIO` 而不是 `VOICE`，枚举补齐，`CreateChannelResult` / `VoiceChannelMemberInfo` 不再因此 `ValidationError`。`Channel._get_voice_channel_ids` 继续兼容两个值。
- `AudioAttachment` / `FileAttachment`：`Attachment.parse` 现在支持 `attachmentType=AUDIO / FILE`，消息里的语音与文件附件不再被当作未知类型丢掉；两者均提供 `from_manually(...)` 构造器，并从 `oopz_sdk.models` 导出。`AudioAttachment.duration` 自动强转 `int`。
- `ChannelDeleteEvent` + 事件名 `channel.delete`：`EVENT_CHANNEL_DELETE` 现在会被 `EventParser` 归类为独立事件（此前走 `UnknownEvent`）。
- `CreateChannelResult.channel_id` 字段：服务端在创建频道响应里可能用 `id` / `channel` / `channelId`，现在都归一到 `channel_id`（模型 alias `"id"`），且支持 `int` / `float` / `str` 三种原始值。
- `examples/voice_join_and_play.py`：语音频道加入 + 推流播放示例。展示 `bot.start()` 放入 `asyncio.create_task`、主协程通过 `@bot.on_ready` + `asyncio.Event` 等 WS 就绪后再做 `voice.join` / `voice.play_file` 的正确异步生命周期，最后在 `finally` 里 `bot.stop()` 并回收后台任务。

### 修复

- `OperationResult.from_api(None)` 现在会返回 `ok=True`。这和 `HttpTransport.request_data()` 对 `{"status": true, "data": null}` 的处理保持一致：外层响应已经确认成功时，空 `data` 代表“没有额外结果”，不再把撤回、禁言、删频道等操作误报为失败。
- 发布包现在包含 `oopz_sdk/assets/voice/agora_player.html`。此前 wheel 里只带了 `py.typed`，安装后的语音浏览器后端会因为找不到页面文件而无法启动。
- `Voice.join` 在调用 `enter_channel` 之前严格校验 `rtc_uid`：`None` 用后端默认 UID；非负整数或"整数字符串"通过；`bool` / `float` / 非数字字符串 / 负数一律提前抛 `TypeError` / `ValueError`。此前非法 UID 要等 `BrowserVoiceTransport.join` 里 `int(uid)` 才崩，届时服务端已经记录加入语音房，留下脏状态。
- `Voice.join` 的 post-`enter_channel` 失败完整回滚：`sign` 为空、`backend.join` 抛错或返回 `False`、`_send_identity_once` 返回 `False` 这三条路径都会调用 `backend.leave()` + 服务端 `leave_voice_channel`（后者 try/except 吞错，防御性），不再出现"Oopz 侧已记录加入、Agora / 浏览器桥实际没进去"的不一致。`_send_identity_once` 返回 `bool`，首次失败触发 `Voice.leave()` 完全清理；心跳循环里的后续失败仍只记 debug 日志、等下次重试。
- `AreaService.cache_max_entries <= 0` 现在真正关闭域成员缓存：新增 `_cache_disabled()`，`get` 直接返回 `None`、`set` 清空已有条目并跳过写入。此前因 `if len(store) >= 0` 恒真、空字典再去 `min()` 会抛 `ValueError`，把缓存开关卡死在"永远写不进来"。驱逐从 `if` 改为 `while`，支持阈值调小时一次性清理多条。
- `PrivateSession.from_api` 不再因为数字型 `sessionId` / `uid` / `lastTime` 抛 `ValidationError`：这些字段统一强转 `str`（`None → ""`、`bool → "true"/"false"`、`float.is_integer() → "1"`、其它 `float → str(value)`），`mute` 走 `coerce_bool`。
- `Channel.create_channel(channel_type=ChannelType.TEXT)` 不再 `Object of type ChannelType is not JSON serializable`：枚举入参会统一取 `.value` 字符串；非 `str` / 非 `ChannelType` 类型抛 `TypeError`，不再把错误留给 `aiohttp` 的 JSON 序列化。
- `ChannelSetting` / `ChannelCreateEvent` 合并 `accessibleRoles` 与 `accessible` 两种 key：只给短 key 的响应不再被读成空列表，避免"改频道名不改权限"的编辑请求把 `accessible: []` 回写到服务端清掉可见角色。优先级：非空 `accessibleRoles` > 非空 `accessible` > 空列表兜底。
- `ChannelCreateEvent` 支持协议里 `type` 或 `channelType` 任一写法：之前只读 `channelType`，对端只下发 `type` 时 `channel_type` 会读成空串。
- `MessageDeleteEvent.isMentionAll` 从 `bool(v or "")` 的诡异写法改为 `coerce_bool(v, default=False)`；原写法字符串 `"false"` 会被当成 mention 全员。
- 各模型 / 事件的布尔字段整体切到 `coerce_bool`，修掉 "`bool("false") == True`" 这类 Python 真值陷阱。覆盖：`UserInfo.online`、`Profile` 9 个字段、`UserLevelInfo.hasNotReceivePrize`、`ChannelSetting` 6 个字段、`VoiceChannelMemberInfo.isBot`、`CreateChannelResult.secret`、`ChannelUpdateEvent` / `ChannelCreateEvent` 布尔字段、`RoleChangedEvent.isDisplay`、`Message.isMentionAll` / `Message.senderIsBot`、`MentionInfo.isBot`、`Attachment.animated`、`RoleInfo.owned`。
- `ChannelGroupInfo.is_enable_temp` 用 `AliasChoices("IsEnableTemp", "isEnableTemp")` 兼容两种 casing；序列化仍走 `"IsEnableTemp"` 不破坏回写。

### 改进

- README 补充语音示例条目、`auto_recall` 三态语义说明，并把"发消息后自动撤回"的配置方式统一说明成"构造 `OopzConfig` 时传 `auto_recall=AutoRecallConfig(enabled=True, delay=...)` 或直接改 `config.auto_recall_enabled` / `config.auto_recall_delay`，开启后 `send_message` 自动按延迟撤回、不必每次传 `auto_recall=True`"。
- `pyproject.toml` 将 `license-files = []` 改回 `["LICENSE"]`，消除 setuptools 关于 `LICENSE` 未声明的告警，与 `MANIFEST.in` 的 include 保持一致（0.6.1 修过一次，0.7.0/0.7.1 又回退成空数组，这里重新落地）。
- `oopz_sdk/models/attachment.py` 删除 `Attachment.parse` 中 `raise` 之后的 unreachable 赋值。

## 0.7.1 - 2026-04-24

### 变更

- 移除 `OopzConfig.default_area` / `default_channel` 两个字段。`OopzBot.send / reply / recall` 的 `area / channel` 固定为必填位置参数（延续 0.7.0 行为），不再从配置回落。0.6.2 曾引入的回落机制本版本确认放弃，调用方需显式传 `area / channel`，或使用 `ctx.reply()` 等从事件上下文推导的便捷入口。

### 修复

- `Channel.leave_voice_channel` 把 `area` 从 `Optional[str] = None` 改为必填 `str`，并补充空串校验。原先 `area=None` 会被原样拼进 `params`，实际只会让服务端返回错误，没有可用场景。
- `Channel.enter_channel` / `get_voice_channel_members` 补上 `area` / `channel` 的类型标注与空串校验，对齐 0.6.0 立的「必填参数缺失一律抛 `ValueError`」约定。
- `AreaInfo.private_channels` 从 `list[dict[str, Any]]` 改为 `list[str]`。服务端实际下发的是私密频道的 id 字符串列表，原先的 `dict` 声明会让 `areas.get_area_info` 在任何含有私密频道的域上直接 pydantic `ValidationError`（联调已复现）。

### 改进

- `services/message.py` 的参数类型标注修齐：`send_message` 的 `attachments / mention_list / style_tags / reference_message_id` 改为 `Optional[...]`、`auto_recall` 补 `bool`；`recall_message.timestamp` 改为 `Optional[str]`。此前同一个文件里 `send_private_message` 已写成 `Optional[...]`，两种风格并存会让类型检查器误报。
- `Channel._get_voice_channel_ids` 的返回类型从 `list[str] | dict[str, str]` 收敛到真实的 `list[str]`，`dict` 分支是历史遗留注解，从未出现过。
- `AutoRecallConfig.delay` 由 `int` 改为 `float`（配套 `OopzConfig.auto_recall_delay` / `Message._do_auto_recall.delay`），允许设置亚秒级延迟，和 `asyncio.sleep` 的实际类型对齐。
- 删除 `oopz_sdk/transport/__init__.py` 的 `try / except ModuleNotFoundError: WebSocketTransport = None` 兜底：`transport/ws.py` 只依赖 `aiohttp` 和 stdlib，而 `aiohttp` 已经是硬依赖，真正缺失时 `transport/http.py` 的 `import aiohttp` 就已经先炸；和 0.7.0 已清理的两段 `OopzBot / OopzWSClient` 占位块是同类死代码。
- `transport/proxy.py::build_requests_proxies` 注释说明它是遗留 API、仅为兼容保留，新代码应使用 `build_aiohttp_proxy`。

## 0.7.0 - 2026-04-24

### 变更

- `AreaService.enter_area` 失败行为从返回 `{"error": ...}` dict 改为抛 `OopzApiError`，与其它 service 统一。调用方需从判断返回值改为 `try/except OopzApiError`。
- 依赖集合调整：从 `dependencies` 移除 `requests` 与 `websocket-client`（SDK 运行时早已不再使用，保留反而会强迫使用方额外安装）。如果上层项目间接依赖这两个包，请自行在自家 `requirements` 声明。

### 新增

- 事件解析器支持三种此前会被静默丢弃的事件类型:`EVENT_MESSAGE_EDIT` → `message.edit`、`EVENT_PRIVATE_MESSAGE_EDIT` → `message.private.edit`、`EVENT_PRIVATE_MESSAGE_DELETE` → `recall.private`。
- `OopzBot` 新增 `on_message_edit` / `on_private_message_edit` / `on_private_recall` 三个 decorator,对应上述事件。
- `pyproject.toml` 补上 `Programming Language :: Python :: 3.13` classifier。
- `VoiceChanelMemberInfo`(历史拼写错误)现在同时以正确拼写 `VoiceChannelMemberInfo` 暴露,老名字保留作为 alias 不破坏既有代码。

### 修复

- `HttpTransport.request_data` 把合法的 `{"status": true, "data": null}` 响应错误地当成失败抛 `OopzApiError`,改为只在真正没有 `"data"` 键时才抛,行为与 `request_data_with_retry` 对齐。
- `CreateChannelResult.from_api` / `UserInfo.from_api` 的返回类型注解写成了别的模型名,导致静态类型检查报错,修正为各自模型本身。
- `Channel.get_voice_channel_for_user` 此前遍历 `.roles()`(语音成员结构上并没有这个方法),改为 `.items()` 真正可用;同时补上 `area: str` 类型标注与说明。
- `Message.get_channel_messages` 补上 `area / channel / size` 的必填与范围校验,避免把空串 / 非法 size 直接发给服务端。

### 改进

- `Media.upload_file` 的本地文件读取改走 `asyncio.to_thread`,不再在事件循环里做同步 I/O。
- 删除 `oopz_sdk/__init__.py` 与 `oopz_sdk/client/__init__.py` 中两份"缺 `aiohttp` 时给 `OopzBot`/`OopzWSClient` 塞占位类"的 try/except 块：真实导入链路在更早的 `from .client.rest import ...` 就会因为缺 `aiohttp` 失败,这两段兜底永远走不到,是纯死代码。
- 删除 `BaseService` 中未被任何 service 调用的 HTTP 包装方法(`_get / _post / _put / _patch / _delete / _request`)及配套的 `_raise_api_error / _error_payload / _error_message / _retry_after_seconds` 错误处理助手,以及 `copy` / `safe_json` 两个只服务于这些死代码的 import。
- `Config.DEFAULT_HEADERS` 的 `Accept-Encoding` 不再从 `requests.utils.DEFAULT_ACCEPT_ENCODING` 取值,改为直接写 `"gzip, deflate"`,去掉对 `requests` 的最后一处硬依赖。
- `services/member.py::get_person_info` 的 `uid: str = None` 修正为 `uid: Optional[str] = None`。

### 备注

- `Moderation.mute_mic` 同时传 `params` 与 `body`,和同文件其它 mute/unmute 方法的调用风格不一致,本版本未改动行为,仅在源码里留了 TODO 说明,等确认服务端真实契约后再处理。

## 0.6.2 - 2026-04-23

### 修复

- 事件名对齐：`EventParser` 对 `EVENT_MESSAGE_DELETE` 发出的事件名从 `"message.delete"` 改为 `"recall"`，使 `@bot.on_recall` 真正能收到撤回事件（原先注册和派发名字不一致，回调永远不触发）。
- `Message.get_channel_messages` 响应校验逻辑修正：之前 `not isinstance(data, dict) and data.get("message", ...)` 条件既判断反（`and` 让正常 dict 跳过校验）又字段名写错（单数 `message`）且未处理 `data.get("messages") is None` 的情况；现在改为 `or` + 复数字段名，保证 payload 不合法时立即抛 `OopzApiError`。
- `HttpTransport.request_data_with_retry` 行为与 `request_data` 对齐：缺少 `data` 字段改为抛 `OopzApiError`，不再静默返回 `None`；移除永远不会触发的 `except KeyError` 分支，并修正兜底 `RuntimeError` 错误文本。
- `HttpTransport.request` 非 429 错误现在会读取服务端返回的 `message / error` 字段作为错误消息，与 429 分支保持一致，不再丢服务端的错误原因。
- `Signer._resolve_key` 不再在 `private_key=None` 时静默生成一把随机 RSA 密钥（那会导致签名完全对不上服务端），直接抛 `OopzAuthError`。

### 改进

- `OopzBot.send / reply / recall` 在未显式传 `area / channel` 时会回落到 `OopzConfig.default_area / default_channel`，都没有则抛出明确的 `ValueError`，而不是把 `None` 一路送到 API 里得到一个看不懂的服务端错误。
- 删除 `HttpResponse.raise_for_status`（内部无调用，且抛的是 `RuntimeError` 与 SDK 的 `OopzApiError` 体系不一致）。
- 清理 `BaseService` 中未被调用的 `_model_error` / `_invalid_dict_item_payload` 方法，以及相关 `inspect` 依赖。
- 清理 `oopz_sdk/models/base.py` 与 `oopz_sdk/models/message.py` 中未使用的 `dataclasses` / `Self` 等 import 和双空格。

### 测试

- 新增 `tests/test_event_parser.py`，固定 `EventParser` 对 chat / private / recall / heartbeat 事件的事件名契约，防止以后再次漂移。

## 0.6.1 - 2026-04-23

### 修复

- 打包恢复 `LICENSE` 文件：`pyproject.toml` 将 `license-files` 从空数组改为 `["LICENSE"]`，并在 `MANIFEST.in` 中显式 include，符合 MIT 协议的传递要求。
- 移除随 wheel 一起发布的调试脚本 `oopz_sdk/test-client.py`，同步清理 `.gitignore` 中的相关条目。
- 移除空壳的 `OopzApiMixin`（原实现只靠 `vars(OopzRESTClient)` 复制类属性，无法拿到 `messages` / `media` / `areas` 等实例属性，继承使用必然 `AttributeError`）；同步从 `oopz_sdk.__init__` 的 `__all__` 中移除。

### 改进

- README 补充安装、凭证、发送消息、事件监听等快速上手示例，替换原先"文档暂未完成"的占位内容。
- `BaseService` 的 docstring 同步到 0.6.0 的新错误约定（必填参数缺失一律抛 `ValueError`，不再软失败）。
- CI 在 `push` 到 `main` 时也会触发测试和打包，避免主干回归遗漏。
- 清理 `oopz_sdk.utils.message_builder` 里未使用的 `import os` / `ImageAttachment`，修掉 `oopz_sdk/__init__.py` 的多余空格。
- 新增 `test.env.example`，提供 smoke 测试所需的环境变量模板。

## 0.6.0 - 2026-04-23

### 变更

- 所有 service 构造签名统一为 `(owner, config, transport, signer)`，owner 持有同级其它 service 的引用并通过 `_require_service` 访问；对老签名（`config` 首参）误用直接抛 `TypeError`，不再静默兼容。
- `OopzRESTClient` 构造签名改为 `(config, *, bot=None)`，`bot` 仅接受关键字参数。
- 所有 data model 从原先的 dataclass 风格 `BaseModel` 全面迁移到 `pydantic.BaseModel`，统一接入 `@model_validator(mode="before")` 做入参归一化，非字典 payload 直接抛 `OopzApiError`。
- 统一错误约定：service 方法的必填参数（`area` / `channel` / `channel_id` / `uid` / `target` / `message_id` 等）缺失时一律抛 `ValueError`，不再走 "`OperationResult(ok=False, message="缺少 xxx")`" 软失败。后端业务失败仍用 `OperationResult.ok=False` 或 `OopzApiError` 体系表达，调用方按需 `if not result.ok` 或 try/except。
- 删除旧的 `oopz_sdk/response.py` 和 `oopz_sdk/models/response.py`，响应构造统一收口到各模型自己的 `from_api`。
- `Message.from_api` 遇到未知附件类型从抛错改为跳过并 WARNING，避免一条坏附件拖垮整条消息解析。
- `AreaService` 缓存 TTL 的兜底值对齐 `OopzConfig` 默认值 `15.0` 秒。

### 新增

- 新增 `oopz_sdk/models/moderation.py`，承载禁言 / 禁麦相关枚举（`TextMuteInterval`、`VoiceMuteInterval` 等）与结果模型。
- `channel` / `message` / `area` / `member` service 补齐若干常用方法，并统一走 `_request_data + from_api` 的调用风格。

### 改进

- 精简 `area` / `channel` / `media` / `member` / `message` / `moderation` 等 service 代码，合计约 -4200 / +2800 行，删除大量旧兼容分支和散落在 service 内部的原始响应处理逻辑。
- `transport/http.py` 汇总公共的 `_request_data` / `_request_data_with_retry` / `request_raw` 入口，service 层直接调用，不再各自拼装。
- `member.py` 所有方法统一改为 `_request_data + from_api`，移除手写的响应解析。

### 修复

- 修复 `get_channel_messages` 响应校验字段名和类型判断错误，正确按 `messages` 数组解析。
- 修复 `channel` / `moderation` 成功路径上给 `OperationResult` 等 Result 模型误传 `response=` 参数导致的构造异常。
- WebSocket 重连等待从 `asyncio.sleep` 改为 `asyncio.Event.wait`，收到停止信号可立即退出重连循环。
- 清理 `rest.py` 里残留的 `_config` 引用。

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
