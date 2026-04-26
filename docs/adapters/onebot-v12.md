# OneBot v12 适配

SDK 内置 `oopz_sdk.adapters.onebot.v12`，用于把 Oopz 事件与消息能力适配到 OneBot v12 风格，方便接入 NoneBot2 或其他 OneBot 生态组件。

正在进行中...

[//]: # ()
[//]: # (## 配置)

[//]: # ()
[//]: # (OneBot 配置位于 `OopzConfig.onebot_v12`。)

[//]: # ()
[//]: # (```python)

[//]: # (from oopz_sdk import OopzConfig, OneBotV12Config)

[//]: # ()
[//]: # (config = OopzConfig&#40;)

[//]: # (    ...,)

[//]: # (    onebot_v12=OneBotV12Config&#40;)

[//]: # (        enabled=True,)

[//]: # (        auto_start_server=True,)

[//]: # (        host="127.0.0.1",)

[//]: # (        port=6727,)

[//]: # (        access_token="",)

[//]: # (        enable_http=True,)

[//]: # (        enable_ws=True,)

[//]: # (        webhook_urls=[],)

[//]: # (        ws_reverse_urls=[],)

[//]: # (    &#41;,)

[//]: # (&#41;)

[//]: # (```)

[//]: # ()
[//]: # (## 字段说明)

[//]: # ()
[//]: # (| 字段 | 默认值 | 说明 |)

[//]: # (| --- | --- | --- |)

[//]: # (| `enabled` | `False` | 是否启用 OneBot v12 适配器。 |)

[//]: # (| `auto_start_server` | `True` | `OopzBot.start&#40;&#41;` 时是否自动启动 OneBot server。 |)

[//]: # (| `platform` | `oopz` | OneBot 平台名。 |)

[//]: # (| `self_id` | `""` | OneBot 侧 bot self_id；为空时通常使用 Oopz `person_uid`。 |)

[//]: # (| `db_path` | `None` | 消息映射 SQLite 路径。 |)

[//]: # (| `host` | `127.0.0.1` | 正向 HTTP / WebSocket server 监听地址。 |)

[//]: # (| `port` | `6727` | 监听端口。 |)

[//]: # (| `access_token` | `""` | OneBot 连接层 token。 |)

[//]: # (| `enable_http` | `True` | 是否启用 HTTP API。 |)

[//]: # (| `enable_ws` | `True` | 是否启用正向 WebSocket。 |)

[//]: # (| `webhook_urls` | `[]` | 事件 HTTP webhook 推送地址。 |)

[//]: # (| `ws_reverse_urls` | `[]` | 反向 WebSocket 地址，SDK 会主动连接。 |)

[//]: # (| `ws_reverse_reconnect_interval` | `3.0` | 反向 WS 重连间隔。 |)

[//]: # (| `send_connect_event` | `True` | 是否发送连接事件。 |)

[//]: # ()
[//]: # (## 启动方式)

[//]: # ()
[//]: # (```python)

[//]: # (bot = OopzBot&#40;config&#41;)

[//]: # (await bot.run&#40;&#41;)

[//]: # (```)

[//]: # ()
[//]: # (当 `enabled=True` 且 `auto_start_server=True` 时，OneBot server 会随 Bot 启动。)

[//]: # ()
[//]: # (## 与 NoneBot2 连接)

[//]: # ()
[//]: # (典型正向 WebSocket 地址：)

[//]: # ()
[//]: # (```text)

[//]: # (ws://127.0.0.1:6727/onebot/v12/ws)

[//]: # (```)

[//]: # ()
[//]: # (典型 HTTP API 地址：)

[//]: # ()
[//]: # (```text)

[//]: # (http://127.0.0.1:6727/onebot/v12/)

[//]: # (```)

[//]: # ()
[//]: # (具体路径以当前 `server.py` 暴露路由为准。)

[//]: # ()
[//]: # (## 消息 ID 映射策略)

[//]: # ()
[//]: # (Oopz 撤回频道消息需要：)

[//]: # ()
[//]: # (- `area`)

[//]: # (- `channel`)

[//]: # (- `message_id`)

[//]: # ()
[//]: # (而 OneBot 的 `message_id` 通常只是一个单值。为了让 OneBot 侧可以通过单个 `message_id` 调用撤回，适配器会维护内部 SQLite 映射，把 OneBot message_id 映射到 Oopz 所需的完整信息。)

[//]: # ()
[//]: # (默认映射库示例：)

[//]: # ()
[//]: # (```text)

[//]: # (oopz_sdk/.oopz_sdk/onebot_v12_message_map.sqlite3)

[//]: # (```)

[//]: # ()
[//]: # (建议生产部署时显式配置 `db_path`，避免工作目录变化导致映射丢失：)

[//]: # ()
[//]: # (```python)

[//]: # (OneBotV12Config&#40;)

[//]: # (    enabled=True,)

[//]: # (    db_path="./data/onebot_v12_message_map.sqlite3",)

[//]: # (&#41;)

[//]: # (```)

[//]: # ()
[//]: # (## group_id 与 area/channel 的差异)

[//]: # ()
[//]: # (Oopz 有 `area` 和 `channel`：)

[//]: # ()
[//]: # (- `area` 更接近服务器/域。)

[//]: # (- `channel` 更接近频道。)

[//]: # (- Oopz 侧还可能存在频道分组概念。)

[//]: # ()
[//]: # (OneBot 传统 `group_id` 只有一个群组 ID，无法完整表达 Oopz 的域 + 频道 + 分组结构。适配器建议：)

[//]: # ()
[//]: # (- OneBot `guild_id` 或扩展字段承载 `area`。)

[//]: # (- OneBot `channel_id` 承载 Oopz `channel`。)

[//]: # (- 不把 Oopz 频道分组强行塞进 `group_id`，避免和群/频道 ID 混淆。)

[//]: # (- 需要撤回、回复等操作时，通过内部映射恢复 `area` 与 `channel`。)

[//]: # ()
[//]: # (## 事件映射建议)

[//]: # ()
[//]: # (| Oopz SDK 事件 | OneBot 侧建议 |)

[//]: # (| --- | --- |)

[//]: # (| `message` | 频道消息事件。 |)

[//]: # (| `message.private` | 私聊消息事件。 |)

[//]: # (| `message.edit` | 消息更新或扩展事件。 |)

[//]: # (| `recall` | 消息删除/撤回事件。 |)

[//]: # (| `channel.create` | 频道创建事件。 |)

[//]: # (| `channel.delete` | 频道删除事件。 |)

[//]: # (| `channel.update` | 频道更新事件。 |)

[//]: # (| `voice.enter` / `voice.leave` | 语音状态扩展事件。 |)

[//]: # (| `heartbeat` | 通常不应该上报给 OneBot 业务层；作为连接保活即可。 |)

[//]: # ()
[//]: # (## 维护建议)

[//]: # ()
[//]: # (- `adapter.py`：负责协议转换和动作实现。)

[//]: # (- `server.py`：负责 HTTP / WebSocket server 和 webhook / reverse WS。)

[//]: # (- `event.py`：负责 Oopz 事件到 OneBot 事件的转换。)

[//]: # (- `message.py`：负责消息段转换。)

[//]: # (- `types.py`：放 OneBot 类型、响应结构、SQLite 映射存储。)

[//]: # (- `__init__.py`：导出公开入口。)

[//]: # ()
[//]: # (保持这几个文件职责清晰，可以避免 `adapter.py` 和 `bot.py` 逻辑重复。)
