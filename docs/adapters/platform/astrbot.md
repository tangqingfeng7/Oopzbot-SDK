# 接入 AstrBot

Oopz SDK 内置 OneBot 适配能力，可以将 Oopz 的消息、私信、撤回等事件转换为 OneBot 事件，并通过 HTTP / WebSocket / 反向 WebSocket 与 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 连接。

> 推荐优先使用 **OneBot v11 + 反向 WebSocket** 连接 AstrBot。  
> 这是 AstrBot / NapCat / aiocqhttp 生态中最常见、兼容性最好的连接方式。

## 架构说明

接入后整体数据流如下：

```text
Oopz
  ↓ WebSocket 事件
Oopz SDK
  ↓ OneBot v11 事件
AstrBot
  ↓ LLM / 插件 / 指令处理
AstrBot
  ↓ OneBot Action
Oopz SDK
  ↓ Oopz API
Oopz
```

其中：

- **Oopz SDK**：负责连接 Oopz、接收事件、发送消息。
- **OneBot Adapter**：负责 Oopz 事件与 OneBot 事件之间的转换。
- **OneBot Server**：负责 HTTP / WebSocket / 反向 WebSocket 通信。
- **AstrBot**：负责对话、LLM、插件、指令等上层逻辑。


## 在 AstrBot 中配置

进入 AstrBot WebUI 后：

1. 打开左侧 **机器人** / **Platform** 页面。
2. 点击 **创建机器人** / **Add**。
3. 消息平台类型选择：

    ```text
    OneBot v11
    ```

4. 启用该适配器。
5. 连接方式选择 **反向 WebSocket**。
6. 记录 AstrBot 提供的 WebSocket 地址。

通常本机部署时地址类似：

```text
ws://127.0.0.1:6199/ws
```

如果 AstrBot 在 Docker Compose 中，并且 Oopz SDK 和 AstrBot 在同一个 Docker 网络中，地址可能类似：

```text
ws://astrbot:6199/ws
```

如果设置了 token，请记住这个 token，后面需要同步填入 Oopz SDK 的 `access_token`。

## 在 Oopz SDK 中启用 OneBot v11

示例：

```python
import asyncio
import os

from oopz_sdk import OopzBot, OopzConfig, OneBotV11Config


config = OopzConfig(
    device_id=os.environ["OOPZ_DEVICE_ID"],
    person_uid=os.environ["OOPZ_PERSON_UID"],
    jwt_token=os.environ["OOPZ_JWT_TOKEN"],
    private_key=os.environ["OOPZ_PRIVATE_KEY"],

    onebot_v11=OneBotV11Config(
        enabled=True,

        # 推荐使用反向 WebSocket 连接 AstrBot
        ws_reverse_url="ws://127.0.0.1:6199/ws",
        # 如果 AstrBot 侧配置了 token，这里也要填一样的
        access_token="",

        # 只使用反向 WS 时，本地 HTTP / 正向 WS 可以关闭
        enable_http=False,
        enable_ws=False,
    ),
)


bot = OopzBot(config)


@bot.on_ready
async def handle_ready(ctx):
    print("Oopz SDK connected")


asyncio.run(bot.run())
```

启动后，如果连接成功，AstrBot 应该能收到 OneBot v11 的连接事件。

## 使用 Access Token

如果 AstrBot 侧配置了反向 WebSocket Token，例如：

```text
my-secret-token
```

那么 Oopz SDK 也需要配置：

```python
onebot_v11=OneBotV11Config(
    enabled=True,
    ws_reverse_url="ws://127.0.0.1:6199/ws",
    access_token="my-secret-token",
    enable_http=False,
    enable_ws=False,
)
```

当前 SDK 在 OneBot v11 反向 WebSocket 连接时会发送：

```http
Authorization: Bearer <access_token> # access_token 非空时
X-Self-ID: <self_id>
X-Client-Role: Universal
User-Agent: CQHttp/4.15.0
```

如果 AstrBot 一直提示鉴权失败，优先检查：

1. AstrBot 配置的 token。
2. Oopz SDK 的 `access_token`。
3. 是否多了空格。
4. 是否连接到了错误的 AstrBot 实例。


!!! note 
    到这里，你已经应该成功连接了 AstrBot

## 正向 WebSocket 方式

除了反向 WebSocket，Oopz SDK 也可以启动正向 WebSocket Server，让 AstrBot 主动连接 SDK。

示例：

```python
onebot_v11=OneBotV11Config(
    enabled=True,

    host="127.0.0.1",
    port=6700,

    enable_http=True,
    enable_ws=True,

    ws_reverse_urls=[],
)
```

此时 OneBot v11 WebSocket 地址为：

```text
ws://127.0.0.1:6700/
```


## 映射数据库配置

Oopz 是双层结构：

```text
area  ->  channel
```

而 OneBot v11 是单层群结构：

```text
group_id
```

所以当前 OneBot v11 适配器内部会把：

```text
Oopz area + channel
```

映射成一个数字型：

```text
group_id
```

这个映射会存入本地 SQLite 数据库。

默认数据库路径为：

```text
.oopz_sdk/onebot_v11.sqlite3
```

如果你想固定数据库路径，可以配置：

```python
onebot_v11=OneBotV11Config(
    enabled=True,
    db_path="./data/oopz_onebot_v11.sqlite3",
    ws_reverse_url="ws://127.0.0.1:6199/ws",
)
```

建议生产环境固定 `db_path`，否则重启或切换工作目录后，`group_id` / `message_id` 映射可能变化。
