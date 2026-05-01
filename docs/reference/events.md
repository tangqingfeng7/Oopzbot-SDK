# Event 类型

所有事件都继承自 `Event`。本页只列结构化事件模型；要看 Oopz 原始 event code → SDK event name 的映射，参考 [事件系统](../guide/events.md#oopz-原生-event-code-到-sdk-event-name-映射)。

## 公共字段

所有事件都包含以下基础字段：

| 字段           | 类型               | 说明                            |
|--------------|------------------|-------------------------------|
| `event_name` | `str`            | SDK 内部事件名，例如 `message`、`recall`。 |
| `event_type` | `int`            | Oopz 原始事件编号。                  |
| `raw`        | `dict[str, Any]` | 原始 WebSocket payload（含 `event` / `time` / `body` 等键）。 |

> 历史上 `Event` 上字段叫 `name`，但很多事件 body 里也带 `name`（频道名、身份组名等），冲突，所以 SDK 使用 `event_name`。

## `MessageEvent`

用于：`message`、`message.private`、`message.edit`、`message.private.edit`。

| 字段           | 类型                | 说明                          |
|--------------|-------------------|-----------------------------|
| `message`    | `Message \| None` | 解析后的消息模型。详见 [数据模型 - Message](models.md)。 |
| `is_private` | `bool`            | 是否私信事件（即 `event_type` 为 7 或 56）。 |

消息事件的 handler 拿到的第一个参数就是 `Message`，不是 `MessageEvent`。如果需要 `is_private` 可以从 `ctx.event` 拿。

??? example "示例 payload (event 7 / 私信)"

    ```json
    {
      "event": 7,
      "time": "1776587501102",
      "body": "{\"type\":\"TEXT\",\"data\":\"{\\\"target\\\":\\\"6ad...\\\",\\\"area\\\":\\\"\\\",\\\"channel\\\":\\\"01KP...\\\",\\\"type\\\":\\\"TEXT\\\",\\\"messageId\\\":\\\"142832326542360675\\\",\\\"timestamp\\\":\\\"1776587501099998\\\",\\\"person\\\":\\\"2ce1...\\\",\\\"content\\\":\\\"hi\\\",\\\"text\\\":\\\"hi\\\",\\\"mentionList\\\":[],\\\"isMentionAll\\\":false,\\\"styleTags\\\":[],\\\"referenceMessageId\\\":null,\\\"referenceMessage\\\":null}\"}"
    }
    ```

## `MessageDeleteEvent`

用于：`recall`、`recall.private`。

| 字段                | 类型              | 说明                  |
|-------------------|-----------------|---------------------|
| `area`            | `str`           | 域 ID。私信撤回时通常为空。     |
| `channel`         | `str`           | 频道 ID 或私信会话 ID。     |
| `message_id`      | `str`           | 被撤回消息 ID。           |
| `person`          | `str`           | 触发撤回的用户 UID。        |
| `is_mention_all`  | `bool`          | 被撤回消息是否曾艾特全体。       |
| `mention_list`    | `list[Any]`     | 被撤回消息上的 mention 列表。 |

## `AreaDisableEvent`

用于：`moderation.voice_ban`（11，禁麦）、`moderation.text_ban`（12，禁言）。

| 字段           | 类型    | 说明                                                |
|--------------|-------|---------------------------------------------------|
| `ack_id`     | `str` | ACK ID。                                           |
| `type`       | `str` | 禁用类型。多数情况下为空字符串。                                  |
| `area`       | `str` | 域 ID。                                             |
| `disable_to` | `str` | 禁用截止时间戳（毫秒）；解禁事件时通常下发 `null`，模型里规范化为 `""`。 |

??? example "示例 payload (event 11)"

    ```json
    {
      "event": 11,
      "time": "1776590769525",
      "body": "{\"ackId\":\"0\",\"type\":\"\",\"area\":\"01KP88YR5BYKKGW3QD1G7JMVVA\",\"disableTo\":\"1776590829522\"}"
    }
    ```

## `ChannelUpdateEvent`

用于：`channel.update`（18，频道设置变化）。

| 字段                       | 类型          | 说明                            |
|--------------------------|-------------|-------------------------------|
| `area`                   | `str`       | 域 ID。                         |
| `channel`                | `str`       | 频道 ID。                        |
| `name`                   | `str`       | 频道名称。                         |
| `channel_type`           | `str`       | 频道类型，例如 `TEXT` / `VOICE`。对应 body 里的 `type`。 |
| `secret`                 | `bool`      | 是否私密频道。                       |
| `member_public`          | `bool`      | 成员列表是否公开。                     |
| `text_gap_second`        | `int`       | 发言间隔秒数。                       |
| `voice_control_enabled`  | `bool`      | 是否启用语音权限控制。                   |
| `text_control_enabled`   | `bool`      | 是否启用文字权限控制。                   |
| `voice_roles`            | `list[Any]` | 可语音身份组 ID 列表。                 |
| `text_roles`             | `list[Any]` | 可发言身份组 ID 列表。                 |
| `accessible_roles`       | `list[Any]` | 可访问该频道的身份组 ID 列表。             |
| `accessible`             | `list[Any]` | 可访问该频道的身份组 ID 列表的另一种 payload 键名。当前模型会分别保留 `accessible_roles` 与 `accessible`，不会自动合并；读取时请兼顾两个字段。 |
| `disable_voice`          | `list[Any]` | 禁麦列表。                         |
| `disable_text`           | `list[Any]` | 禁言列表。                         |
| `max_member`             | `int`       | 最大成员数，默认 `30000`。             |
| `access_control_enabled` | `bool`      | 是否启用访问控制。                     |
| `has_password`           | `bool`      | 是否有密码。                        |

## `ChannelCreateEvent`

用于：`channel.create`（25，公开频道创建）。

| 字段                       | 类型           | 说明                              |
|--------------------------|--------------|---------------------------------|
| `area`                   | `str`        | 域 ID。                           |
| `channel`                | `str`        | 新频道 ID。                         |
| `type`                   | `str`        | 频道类型归一值。SDK 会优先使用 body 里的 `channelType`，没有时回退到 `type`。 |
| `channel_type`           | `str`        | 同 `type`，通常为 `TEXT` / `VOICE`。当前模型不会单独保留原始操作类型。 |
| `name`                   | `str`        | 频道名称。                           |
| `member_public`          | `bool`       | 成员列表是否公开。                       |
| `voice_control_enabled`  | `bool`       | 是否启用语音权限控制。                     |
| `text_control_enabled`   | `bool`       | 是否启用文字权限控制。                     |
| `voice_roles`            | `list[Any]`  | 可语音身份组列表，可能为 `null` → 空 list。   |
| `text_roles`             | `list[Any]`  | 可发言身份组列表，可能为 `null` → 空 list。   |
| `text_gap_second`        | `int`        | 发言间隔秒数。                         |
| `password`               | `str`        | 频道密码。                           |
| `voice_quality`          | `str`        | 语音质量，默认 `64k`。                  |
| `voice_delay`            | `str`        | 语音延迟模式，默认 `LOW`。                |
| `max_member`             | `int`        | 最大成员数。                          |
| `group_id`               | `str`        | 所属频道分组 ID。                      |
| `secret`                 | `bool`       | 是否私密频道。                         |
| `accessible_roles`       | `list[Any]`  | 可访问该频道的身份组列表。                   |
| `accessible_members`     | `list[str]` | 可访问该频道的成员 UID 列表。               |
| `has_password`           | `bool`       | 是否设置了密码。                        |
| `access_control_enabled` | `bool`       | 是否启用访问控制。                       |
| `is_temp`                | `bool`       | 是否为临时频道。                        |

## `ChannelDeleteEvent`

用于：`channel.delete`（13，频道删除）。

| 字段        | 类型    | 说明           |
|-----------|-------|--------------|
| `area`    | `str` | 域 ID。        |
| `channel` | `str` | 被删除频道 ID。    |
| `ack_id`  | `str` | ACK ID。      |

## `VoiceChannelPresenceEvent`

用于：`voice.enter`（20，进入语音频道）、`voice.leave`（19，离开语音频道）。

| 字段             | 类型         | 说明                                     |
|----------------|------------|----------------------------------------|
| `area`         | `str`      | 域 ID。                                  |
| `channel`      | `str`      | 语音频道 ID。                               |
| `persons`      | `list[str]` | 当前事件涉及的用户 UID 列表。                      |
| `active_num`   | `int`      | 频道当前活跃人数。                              |
| `sound`        | `str`      | 声音状态。                                  |
| `from_channel` | `str`      | 来源频道（语音切换 / `voice.enter`）。`voice.leave` 时通常为空。 |
| `from_area`    | `str`      | 来源域（语音切换 / `voice.enter`）。`voice.leave` 时通常为空。 |
| `sort`         | `int`      | 排序值，仅 `voice.enter` 下发；`voice.leave` 时为 `0`。 |

??? example "示例 payload (event 20，进入语音)"

    ```json
    {
      "event": 20,
      "time": "1776588082276",
      "body": "{\"area\":\"01KP...\",\"channel\":\"01KP...\",\"persons\":[\"2ce1...\"],\"sound\":\"\",\"fromChannel\":\"\",\"fromArea\":\"\",\"activeNum\":1,\"sort\":99999}"
    }
    ```

## `UserUpdateEvent`

用于：`user.update`（26，用户资料变化）。

| 字段        | 类型               | 说明                                |
|-----------|------------------|-----------------------------------|
| `person`  | `str`            | 用户 UID。                           |
| `updates` | `dict[str, Any]` | 本次变更的字段，例如 `{"avatar": "https://..."}`。 |

## `UserLoginStateEvent`

用于：`user.login_state`（27，用户登录/登出状态变化）。

| 字段       | 类型    | 说明                                          |
|----------|-------|---------------------------------------------|
| `person` | `str` | 用户 UID。                                     |
| `type`   | `str` | 登录状态变化类型，例如 `PERSON_LOGIN` / `PERSON_LOGOUT`。 |

## `AreaUpdateEvent`

用于：`area.update`（28，域信息变化）。

| 字段       | 类型    | 说明           |
|----------|-------|--------------|
| `area`   | `str` | 域 ID。        |
| `code`   | `str` | 域 code（数字 ID）。 |
| `name`   | `str` | 域名称。         |
| `avatar` | `str` | 头像 URL。      |
| `owner`  | `str` | 域主 UID。      |
| `desc`   | `str` | 域描述。         |

## `RoleChangedEvent`

用于：`role.change`（52，身份组变化）。

| 字段                | 类型          | 说明                          |
|-------------------|-------------|-----------------------------|
| `ack_id`          | `str`       | ACK ID。                     |
| `area`            | `str`       | 域 ID。                       |
| `role_id`         | `int`       | 身份组 ID（对应 body 里的 `roleID`）。 |
| `type`            | `str`       | 变化类型，例如 `CREATE` / `DELETE`。 |
| `name`            | `str`       | 身份组名称。                      |
| `description`    | `str`       | 描述。                         |
| `privilege_keys`  | `list[Any]` | 权限 key 列表。                  |
| `is_display`      | `bool`      | 是否展示。                       |
| `sort`            | `int`       | 排序值。                        |
| `role_type`       | `int`       | 身份组类型。                      |
| `category_keys`   | `list[Any]` | 分类 key 列表。                  |

## `ServerIdEvent`

用于：`server_id`（1，连接握手时下发）。

| 字段          | 类型    | 说明                      |
|-------------|-------|-------------------------|
| `server_id` | `str` | 服务端为本次连接分配的 ID。 |

## `AuthEvent`

用于：`auth`（253，鉴权响应）。

| 字段        | 类型    | 说明              |
|-----------|-------|-----------------|
| `code`    | `int` | 鉴权状态码。          |
| `message` | `str` | 鉴权信息。           |

## `HeartbeatEvent`

用于：`heartbeat`（254）。除公共字段外没有额外字段。心跳由 SDK 内部消费，不建议在业务层注册 handler。

## `UnknownEvent`

用于尚未建模的事件，事件名形如 `event_{code}`（如 `event_15`）。

| 字段        | 类型               | 说明              |
|-----------|------------------|-----------------|
| `payload` | `dict[str, Any]` | 原始事件 body 反序列化后的 dict。 |

建议在 `on_raw_event` 中记录未知事件，后续再补充 `EventSpec` 和模型：

```python
@bot.on_raw_event
async def raw(ctx, event):
    if event.event_name.startswith("event_"):
        # event 是 UnknownEvent 实例时，通过 payload 拿到原始 body
        body = getattr(event, "payload", {})
        print(event.event_type, body)
```
