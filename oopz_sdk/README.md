# oopz_sdk

主要的是想定义一下 oopz_sdk 的整体架构和设计思路，来保证项目的可扩展性, 如果确认这个架构可以用, 那就可以继续迁移oopz原本的功能到这里来

---

### 项目结构拆分

- **auth**：签名、请求头、ID 生成
- **transport**：HTTP / WebSocket 传输层
- **services[todo]**：消息、频道、成员、私信、媒体、管理等平台能力 
- **client**：高层 REST client、WS client、Bot 入口
- **events**：事件解析、注册、调度、上下文
- **models[todo]**：统一的数据模型
- **adapters[todo]**：为未来适配 OneBot 等协议预留位置
- **testing[todo]**：测试

---

### 2. 把 REST 能力整理成 service

当前 `OopzRESTClient` 把主要平台能力拆分为独立 service, 但是还来得及完成, 还没有做验证：

- `messages`：频道消息发送、批量发送、撤回、查询消息
- `private`：私信会话、私信发送
- `media`：上传文件、发送图片、上传音频
- `areas`：域信息、域成员、域频道
- `channels`：频道查询、创建、更新、删除、加入/离开语音频道
- `members`：成员资料、等级、角色、搜索
- `moderation`：禁言、封禁、移除等管理能力

models的定义目前我这个版本不完善, 也还没有完全嵌入到service中

---

### 3. 事件系统

当前事件系统由以下模块组成：

- `EventRegistry`：负责 handler 注册
- `EventDispatcher`：负责按事件语义调用 handler
- `EventParser`：负责把原始 WS payload 解析为结构化事件
- `EventContext`：在 handler 中提供 `bot`、`config`、`event`、`message` 等上下文

目前已经有以下事件入口：

- `ready`
- `message`
- `error`
- `close`
- `reconnect`
- `raw_event`
- 其他未知事件会被解析成 `event_{event_type}` 的形式

这说明 SDK 已经从“单纯发请求”进入了“事件驱动框架”的阶段。

---

### 4. 增加了 context

context的目标是件处理时传给 handler 的运行时上下文对象，用来封装当前事件环境并提供与该环境相关的便捷操作

context (event/context.py) 的方法面向当前这次事件的语境，用于在 handler 中做就地响应；bot (client/bot.py) 层的方法面向全局通用能力，用于在任何位置主动调用平台功能。

让事件处理函数里能直接通过context做高层动作, 这样就可以直接在快速在事件的上下文中给事件所在的群聊发送(回复)消息，比如：

- `ctx.reply(...)`
- `ctx.send(...)`
- `ctx.recall_current(...)`
- 通过 `ctx.bot` 访问完整 bot/service
但是这个需要提供的方法还需要定义清楚

---

## 当前还没做完的部分


### 1. service 层还没有完全统一

虽然 `services/` 已经拆出来了，但它们还没有完全迁移完成

---

### 2. event parser 还只覆盖了部分核心事件

`EventParser` 当前重点覆盖的是：

- 聊天消息事件
- heartbeat
- server_id
- 未识别事件的兜底命名

还有很多时间没有覆盖, 需要进行补充

---

### 3. Bot 层便捷 API 还没有完全定义

当前已经提供了一些快捷方法：

- `send(...)`
- `recall(...)`
- `reply_to(...)`

但一般discord 或者 oopz本身的api应该还是可以提供更多的方法的, `EventContext` 同理


### 4. models的定义还没有完成

models定义好了就需要嵌入到service的解析中了

---
