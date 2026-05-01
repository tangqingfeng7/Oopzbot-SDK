# 消息与 ID 映射

Oopz 和 OneBot 的 ID 模型不同，不能简单把所有 ID 原样透传。

## 为什么需要映射

Oopz 的频道消息通常需要这些上下文：

```text
area + channel + message_id
```

私聊消息可能需要：

```text
target/channel + message_id
```

但 OneBot 撤回、回复、查询消息时通常只传：

```text
message_id
```

并且两者使用的id的格式也有所不同所以。adapter 需要维护一张表，把 OneBot 的 `message_id` 还原成 Oopz 所需上下文。

## v11：数字 ID 映射

v11 使用 `IdStore` 维护数字 ID。

```text
Oopz string source -> OneBot int64-like number
```

默认数据库：

```text
.oopz_sdk/onebot_v11.sqlite3
```

### 生成逻辑

如果传入的是数字，直接使用：

```python
ids.createId(123456).number  # 123456
```

如果传入的是来自oopz的字符串 source：

1. 先查 SQLite 是否已有映射；
2. 如果已有，返回旧数字；
3. 如果没有，随机生成一个 JS 安全范围内的数字并保存。

### 常见 source

| source 类型 | 构造函数                                                     | 用途                  |
|-----------|----------------------------------------------------------|---------------------|
| self      | `make_self_source(uid)`                                  | 当前 bot 的 `self_id`。 |
| user      | `make_user_source(uid)`                                  | v11 `user_id`。      |
| group     | `make_group_source(area, channel)`                       | v11 `group_id`。     |
| message   | `make_message_source(area, channel, target, message_id)` | v11 `message_id`。   |

## Oopz 与 OneBot 模型差异

### v11 group 与 Oopz channel

OneBot v11 是单层 `group_id`，Oopz 是 `area/channel` 双层结构。当前实现把 Oopz 频道消息映射为 v11 group 消息，并且生成映射进行存储：

```text
Oopz area + channel -> OneBot v11 group_id
```

因此 v11 的 `group_id` 更接近“area 下的某个 Oopz 频道”，而不是单纯的 Oopz area。

### v12 guild/channel 与 Oopz area/channel

OneBot v12 的模型更接近 Oopz：

```text
Oopz area    -> guild_id
Oopz channel -> channel_id
```


### 发送群消息时的上下文

如果某个 `group_id` 是 adapter 从事件中生成的，那么它可以反查到 Oopz `area/channel`。

如果外部客户端自己传了一个全新的 `group_id`，adapter 不知道它对应哪个 Oopz 频道，此时需要额外传：

```json
{
  "group_id": 12345678,
  "oopz_area_id": "OOPZ_AREA_ID",
  "oopz_channel_id": "OOPZ_CHANNEL_ID"
}
```

## v12：字符串 message_id 映射

v12 使用 `MessageStore` 保存消息映射。

内部 `message_id` 形态：

```text
oopz:<sha1 digest 前 24 位>
```

生成 source 包含：

```text
detail_type | oopz_message_id | area | channel | target | user_id
```

这样做可以避免不同频道或私聊中出现相同 Oopz messageId 时发生冲突。

默认数据库：

```text
.oopz_sdk/onebot_v12_message_map.sqlite3
```

## 映射生命周期

消息映射会在这些场景保存：

- adapter 收到 Oopz 消息事件；
- adapter 收到 Oopz 撤回事件；
- adapter 通过 OneBot action 发送消息成功。

可以调用维护 action 清理旧映射：

=== "v11"

    ```json
    {
      "action": "cleanup_message_mapping",
      "params": {
        "older_than_seconds": 604800
      }
    }
    ```

=== "v12"

    ```json
    {
      "action": "cleanup_message_mapping",
      "params": {
        "older_than_seconds": 604800
      }
    }
    ```

## 不要混用 v11 / v12 ID

v11 和 v12 可以同时启用，但它们不是同一套协议 ID。

| 来源                      | 可用于                                      |
|-------------------------|------------------------------------------|
| v11 事件的数字 `message_id`  | v11 `delete_msg`、v11 `get_msg`。          |
| v12 事件的字符串 `message_id` | v12 `delete_message`、v12 `reply`。        |
| Oopz 原始 `messageId`     | Oopz SDK 原生 API；OneBot fallback 需要补充上下文。 |

!!! danger "不要把 v12 message_id 传给 v11"
v12 返回的 `oopz:...` 是字符串，v11 期望数字。直接混用会导致参数校验失败或找不到映射。
