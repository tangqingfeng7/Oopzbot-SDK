# 实现说明与限制

这一页记录当前 OneBot 实现的行为、检查结论和已知限制，便于后续维护。

## 当前实现检查结论

### 结构合理点

- `adapters/onebot/server.py` 已经抽出了 v11/v12 共用通信层，职责比较清晰。
- v11 / v12 的 action 都改成了字典注册表，`get_supported_actions` 可以直接返回当前支持能力。
- v11 使用 `IdStore.createId/resolveId` 风格，接近 onebots 的思路，能满足 v11 数字 ID 要求。
- v12 使用 `MessageStore` 保存内部 message_id 到 Oopz 上下文的映射，适合处理撤回和回复。
- `OopzBot` 会在 WS 事件进入后先广播到已启用的 OneBot adapter，再进入 SDK 自身事件分发。

### 需要注意的点

1. **v11 `get_group_member_list` 有方法但未注册 action。**  
   如果需要客户端调用，需要在 `OneBotV11Adapter._build_actions()` 中加入：

   ```python
   "get_group_member_list": self.get_group_member_list,
   ```

2. **v12 `leave_guild` 当前是占位实现。**  
   它已注册到 action 表，但调用会返回 not implemented。

3. **v12 撤回事件当前固定按 `channel` 生成。**  
   `v12/event.py` 的 `_message_delete_event()` 当前使用 `detail_type="channel"`。如果 Oopz 私聊撤回也进入 `MessageDeleteEvent`，建议补充类似 v11 的私聊判断逻辑，避免私聊撤回被上报成频道撤回。

4. **v11 / v12 ID 不互通。**  
   两个 adapter 可同时启用，但它们的 OneBot ID 不能交叉使用。

5. **`get_msg` 依赖本地映射。**  
   v11 `get_msg` 不是从远端拉历史消息，而是从 adapter 保存的事件/发送记录还原。因此 mapping 不存在时无法返回完整消息。

6. **未知消息段会降级处理。**  
   未支持 segment 不会静默丢弃，而是尽量变成文本占位。这对调试友好，但对严格 OneBot 客户端可能需要进一步细化。



## 推荐接入策略

### 接入 NoneBot / AstrBot 等 v11 生态

- 启用 `OneBotV11Config`；
- 使用默认 `port=6700`；
- 确认客户端能处理 v11 数字 ID；
- 频道发送失败时检查是否缺少 `oopz_area_id/oopz_channel_id`。

### 接入 v12 客户端或自定义网关

- 优先启用 `OneBotV12Config`；
- 使用 `detail_type="channel"` 对接 Oopz 频道；
- 保存并复用 adapter 返回的 `message_id`，不要直接改用 Oopz 原始 `messageId`。

## 后续可以补强的方向

- 给 v11 / v12 adapter 增加单元测试，覆盖消息、撤回、图片、mention、reply、ID mapping。
- 为 v12 私聊撤回补充判断逻辑。
- 将 `get_group_member_list` 注册到 v11 action 表。
- 将 action 支持表改为从代码自动生成，减少文档和实现不同步。
- 为 OneBot 生态常见客户端补充示例配置，例如 NoneBot、AstrBot、Koishi。
