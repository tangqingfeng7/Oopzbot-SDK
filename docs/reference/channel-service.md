# Channel Service

入口：`client.channels` 或 `bot.channels`。

## 方法列表

| 方法 | 说明 | 返回 |
| --- | --- | --- |
| `get_channel_setting_info(channel)` | 获取频道设置详情。 | `ChannelSetting` |
| `create_channel(area, name, group_id="", channel_type=ChannelType.TEXT)` | 创建频道。 | `CreateChannelResult` |
| `update_channel(area, channel_id, **kwargs)` | 修改频道设置。 | `OperationResult` |
| `delete_channel(area, channel)` | 删除频道。 | `OperationResult` |
| `enter_channel(channel, area, channel_type="TEXT", from_channel="", from_area="", pid="")` | 进入频道；语音频道会返回 RTC sign 信息。 | `ChannelSign` |
| `leave_voice_channel(channel, area, target=None)` | 退出语音频道；默认 target 为当前机器人 UID。 | `OperationResult` |
| `get_voice_channel_members(area)` | 获取域内各语音频道成员。 | `VoiceChannelMembersResult` |
| `get_voice_channel_for_user(user_uid, area)` | 查询用户所在语音频道 ID。 | `str | None` |

## 创建频道

```python
from oopz_sdk.models.channel import ChannelType

result = await client.channels.create_channel(
    area="域 ID",
    name="测试频道",
    channel_type=ChannelType.TEXT,
)
```

如果不传 `group_id`，SDK 会调用 `areas.get_area_channels(area)` 并使用第一个频道分组。

## 修改频道

```python
await client.channels.update_channel(
    area="域 ID",
    channel_id="频道 ID",
    name="新名称",
    text_gap_second=3,
    secret=True,
    accessible_members=["用户 UID"],
)
```

可修改字段：

| 参数 | 说明 |
| --- | --- |
| `name` | 频道名称。 |
| `text_gap_second` | 发言间隔。 |
| `voice_quality` | 语音质量。 |
| `voice_delay` | 语音延迟模式。 |
| `max_member` | 最大成员数。 |
| `voice_control_enabled` | 是否启用语音权限控制。 |
| `text_control_enabled` | 是否启用文字权限控制。 |
| `access_control_enabled` | 是否启用访问控制。 |
| `secret` | 是否私密频道。 |
| `has_password` / `password` | 密码设置；传 `password` 必须同时 `has_password=True`。 |
| `text_roles` | 可发言身份组 ID 列表。 |
| `voice_roles` | 可进入语音身份组 ID 列表。 |
| `accessible_roles` | 可访问身份组 ID 列表，仅私密频道可设置。 |
| `accessible_members` | 可访问成员 UID 列表，仅私密频道可设置。 |

当 `secret=True` 时，SDK 会自动把机器人自己的 UID 加入 `accessible_members`，避免创建/修改后机器人失去访问权限。

## 进入语音频道

一般业务使用更高层的 `bot.voice.join()`；如果只需要获取频道 sign，可直接：

```python
sign = await client.channels.enter_channel(
    channel="语音频道 ID",
    area="域 ID",
    channel_type="VOICE",
    pid="数字 RTC UID",
)
```

返回的 `ChannelSign` 会包含 RTC token、房间名等字段。
