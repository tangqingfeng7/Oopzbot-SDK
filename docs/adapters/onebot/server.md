# OneBot 通信服务

`OneBotServer` 是 v11/v12 共用通信层。v11 和 v12 的 server 类只是兼容导出：

- `OneBotV11Server` 继承 `OneBotServer`，默认 `version="v11"`；
- `OneBotV12Server` 继承 `OneBotServer`，默认 `version="v12"`。

## 配置项

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `host` | `127.0.0.1` | 正向 HTTP / WebSocket 监听地址。 |
| `port` | v11: `6700`；v12: `6727` | 监听端口。 |
| `path_prefix` | `/onebot` | URL 前缀。最终路径为 `/onebot/v11` 或 `/onebot/v12`。 |
| `access_token` | `""` | OneBot 鉴权 token。为空时不启用鉴权。 |
| `enable_http` | `True` | 是否启用 HTTP action。 |
| `enable_ws` | `True` | 是否启用正向 WebSocket。 |
| `webhook_urls` | `[]` | 事件 HTTP POST 推送地址。 |
| `ws_reverse_urls` | `[]` | 反向 WebSocket 地址，SDK 会主动连接。 |
| `ws_reverse_reconnect_interval` | `3.0` | 反向 WebSocket 断线重连间隔。 |
| `send_connect_event` | `True` | WebSocket 连接建立后是否发送生命周期事件。 |

## 正向 HTTP action

支持两种 HTTP 调用方式。

### 路径式 action

```http
POST /onebot/v12/send_message
Content-Type: application/json

{
  "detail_type": "channel",
  "guild_id": "OOPZ_AREA_ID",
  "channel_id": "OOPZ_CHANNEL_ID",
  "message": [
    {"type": "text", "data": {"text": "hello"}}
  ]
}
```

### payload 式 action

```http
POST /onebot/v12
Content-Type: application/json

{
  "action": "send_message",
  "params": {
    "detail_type": "channel",
    "guild_id": "OOPZ_AREA_ID",
    "channel_id": "OOPZ_CHANNEL_ID",
    "message": "hello"
  },
  "echo": "request-1"
}
```

v11 也支持同样形式：

```http
POST /onebot/v11/send_group_msg
Content-Type: application/json

{
  "group_id": 12345678,
  "message": "hello"
}
```

如果 `group_id` 尚未映射，v11 发送群消息时需要额外提供 Oopz 上下文：

```json
{
  "group_id": 12345678,
  "oopz_area_id": "OOPZ_AREA_ID",
  "oopz_channel_id": "OOPZ_CHANNEL_ID",
  "message": "hello"
}
```

## 正向 WebSocket

连接地址：

```text
ws://127.0.0.1:6700/onebot/v11
ws://127.0.0.1:6727/onebot/v12
```

WebSocket 收到 action payload 后会调用 adapter：

```json
{
  "action": "get_supported_actions",
  "params": {},
  "echo": "check-actions"
}
```

返回：

```json
{
  "status": "ok",
  "retcode": 0,
  "data": ["get_supported_actions", "get_status"],
  "echo": "check-actions"
}
```

## 反向 WebSocket

配置 `ws_reverse_urls` 后，SDK 会主动连接这些地址：

```python
from oopz_sdk import OneBotV12Config

onebot_v12 = OneBotV12Config(
    enabled=True,
    ws_reverse_urls=["ws://127.0.0.1:8080/onebot/v12/ws"],
)
```

断线后会按 `ws_reverse_reconnect_interval` 自动重连。

## Access Token

设置 `access_token` 后，HTTP / WebSocket 请求需要携带：

```http
Authorization: Bearer <access_token>
```

也兼容查询参数：

```text
/onebot/v12?access_token=<access_token>
```
