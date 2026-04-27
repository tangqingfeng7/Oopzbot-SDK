# Event 类型

所有事件都继承自 `Event`。

## 公共字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `str` | SDK 内部事件名。 |
| `event_type` | `int` | Oopz 原始事件编号。 |
| `raw` | `dict` | 原始 WebSocket payload。 |

## `MessageEvent`

用于：`message`、`message.private`、`message.edit`、`message.private.edit`。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `message` | `Message | None` | 解析后的消息模型。 |
| `is_private` | `bool` | 是否私信事件。 |

## `MessageDeleteEvent`

用于：`recall`、`recall.private`。

| 字段 | 说明 |
| --- | --- |
| `area` | 域 ID。私信可能为空。 |
| `channel` | 频道 ID 或私信会话 ID。 |
| `message_id` | 被撤回消息 ID。 |
| `person` | 触发撤回的用户。 |
| `isMentionAll` | 是否艾特全体。 |
| `mentionList` | mention 列表。 |

## `AreaDisableEvent`

用于：`moderation.voice_ban`、`moderation.text_ban`。

| 字段 | 说明 |
| --- | --- |
| `ack_id` | ACK ID。 |
| `type` | 禁用类型。 |
| `area` | 域 ID。 |
| `disable_to` | 禁用截止时间或目标信息。 |

## `ChannelUpdateEvent`

用于：`channel.update`。

| 字段 | 说明 |
| --- | --- |
| `area` | 域 ID。 |
| `channel` | 频道 ID。 |
| `name` | 频道名称。 |
| `channel_type` | 频道类型。 |
| `secret` | 是否私密。 |
| `member_public` | 成员是否公开。 |
| `text_gap_second` | 发言间隔。 |
| `voice_control_enabled` | 语音权限控制。 |
| `text_control_enabled` | 文字权限控制。 |
| `voice_roles` | 可语音身份组。 |
| `text_roles` | 可发言身份组。 |
| `accessible_roles` / `accessible` | 可访问身份组。 |
| `disable_voice` | 禁麦列表。 |
| `disable_text` | 禁言列表。 |
| `max_member` | 最大成员数。 |
| `access_control_enabled` | 是否启用访问控制。 |
| `has_password` | 是否有密码。 |

## `ChannelCreateEvent`

用于：`channel.create`。

常用字段包括：

| 字段 | 说明 |
| --- | --- |
| `area` | 域 ID。 |
| `channel` | 新频道 ID。 |
| `name` | 频道名称。 |
| `channel_type` | 频道类型。 |
| `group` / `group_id` | 频道分组。 |
| `secret` | 是否私密。 |
| `max_member` | 最大成员数。 |

## `ChannelDeleteEvent`

用于：`channel.delete`。

| 字段 | 说明 |
| --- | --- |
| `area` | 域 ID。 |
| `channel` | 被删除频道 ID。 |

## `VoiceChannelPresenceEvent`

用于：`voice.enter`、`voice.leave`。

| 字段 | 说明 |
| --- | --- |
| `area` | 域 ID。 |
| `channel` | 语音频道 ID。 |
| `persons` | 当前相关用户列表。 |
| `active_num` | 活跃人数。 |
| `sound` | 声音状态。 |
| `from_channel` | 来源频道。 |
| `from_area` | 来源域。 |

## `UserUpdateEvent`

用于：`user.update`。

| 字段 | 说明 |
| --- | --- |
| `person` | 用户 UID。 |
| `updates` | 更新字段。 |

## `UserLoginStateEvent`

用于：`user.login_state`。

| 字段 | 说明 |
| --- | --- |
| `person` | 用户 UID。 |
| `type` | 登录状态变化类型。 |

## `AreaUpdateEvent`

用于：`area.update`。

| 字段 | 说明 |
| --- | --- |
| `area` | 域 ID。 |
| `code` | 域 code。 |
| `name` | 域名称。 |
| `avatar` | 头像。 |
| `owner` | 所有者 UID。 |
| `desc` | 描述。 |

## `RoleChangedEvent`

用于：`role.change`。

| 字段 | 说明 |
| --- | --- |
| `ack_id` | ACK ID。 |
| `area` | 域 ID。 |
| `role_id` | 身份组 ID。 |
| `type` | 变化类型。 |
| `name` | 身份组名称。 |
| `description` | 描述。 |
| `privilege_keys` | 权限 key 列表。 |
| `is_display` | 是否显示。 |
| `sort` | 排序值。 |
| `role_type` | 身份组类型。 |
| `category_keys` | 分类 key 列表。 |

## `UnknownEvent`

用于尚未建模的事件。

| 字段 | 说明 |
| --- | --- |
| `body` | 原始事件 body。 |

建议在 `on_raw_event` 中记录未知事件，后续再补充 `EventSpec` 和模型。
