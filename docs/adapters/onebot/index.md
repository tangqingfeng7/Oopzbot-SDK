# OneBot 适配概览

Oopz SDK 内置 OneBot 适配层，用于把 Oopz 的事件、消息和 API 调用转换为 OneBot v11 或 OneBot v12 生态可以理解的格式。

当前实现由三层组成：

| 层级 | 文件 | 职责 |
| --- | --- | --- |
| 共用通信层 | `oopz_sdk/adapters/onebot/server.py` | HTTP、正向 WebSocket、反向 WebSocket、Webhook、鉴权、事件广播。|
| v11 适配器 | `oopz_sdk/adapters/onebot/v11/` | v11 action、CQ 码/消息段、事件格式、数字 ID 映射。 |
| v12 适配器 | `oopz_sdk/adapters/onebot/v12/` | v12 action、消息段、事件格式、字符串 message_id 映射。 |
