# Channel Service

`Channel Service` 用于获取频道设置、创建频道、修改频道、删除频道、进入频道、退出语音频道，以及查询语音频道成员。

---

## `get_channel_setting_info(channel)`

获取频道设置详情，包括频道名称、权限控制、语音质量、访问控制、密码状态等。

```python
setting = await client.channels.get_channel_setting_info("频道 ID")

print(setting.name)
print(setting.channel_type)
print(setting.secret)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `channel` | `str` | 是 | 频道 ID，不能为空。 |

=== "返回值"

    返回：`ChannelSetting`。

    对应模型：`oopz_sdk.models.ChannelSetting`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `channel` | `str` | 无 | 频道 ID。 |
    | `area_id` | `str` | `""` | 所属域 ID。 |
    | `group_id` | `str` | `""` | 所属频道分组 ID。 |
    | `name` | `str` | `""` | 频道名称。 |
    | `channel_type` | `str` | `""` | 频道类型，例如 `TEXT`、`VOICE`。 |
    | `text_gap_second` | `int` | `0` | 文本消息发送间隔秒数。 |
    | `voice_quality` | `str` | `"64k"` | 语音质量。 |
    | `voice_delay` | `str` | `"LOW"` | 语音延迟模式。 |
    | `max_member` | `int` | `30000` | 最大成员数。 |
    | `voice_control_enabled` | `bool` | `False` | 是否启用语音权限控制。 |
    | `text_control_enabled` | `bool` | `False` | 是否启用文字权限控制。 |
    | `text_roles` | `list[Any]` | `[]` | 可发送文字消息的身份组列表。 |
    | `voice_roles` | `list[Any]` | `[]` | 可进入语音的身份组列表。 |
    | `access_control_enabled` | `bool` | `False` | 是否启用访问控制。 |
    | `accessible_roles` | `list[int]` | `[]` | 可访问该频道的身份组 ID 列表。 |
    | `accessible_members` | `list[str]` | `[]` | 可访问该频道的成员 UID 列表。 |
    | `member_public` | `bool` | `False` | 成员列表是否公开。 |
    | `secret` | `bool` | `False` | 是否为私密频道。 |
    | `has_password` | `bool` | `False` | 是否设置了频道密码。 |
    | `password` | `str` | `""` | 频道密码。 |

---

## `create_channel(area, name, group_id="", channel_type=ChannelType.TEXT)`

创建频道。

如果不传 `group_id`，SDK 会调用 `areas.get_area_channels(area)`，并使用第一个频道分组作为默认分组。

```python
from oopz_sdk.models.channel import ChannelType

result = await client.channels.create_channel(
    area="域 ID",
    name="测试频道",
    channel_type=ChannelType.TEXT,
)

print(result.name)
print(result.channel_type)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `name` | `str` | 是 | - | 频道名称，不能为空。 |
    | `group_id` | `str` | 否 | `""` | 频道分组 ID；不传时自动使用第一个频道分组。 |
    | `channel_type` | `ChannelType \| str` | 否 | `ChannelType.TEXT` | 频道类型。支持 `TEXT` 和 `VOICE`。 |

=== "返回值"

    返回：`CreateChannelResult`。

    对应模型：`oopz_sdk.models.CreateChannelResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | `""` | 所属域 ID。 |
    | `group_id` | `str` | `""` | 所属频道分组 ID。 |
    | `max_member` | `int` | `100` | 最大成员数。 |
    | `name` | `str` | `""` | 频道名称。 |
    | `secret` | `bool` | `False` | 是否为私密频道。 |
    | `channel_type` | `ChannelType` | `ChannelType.TEXT` | 频道类型。 |

=== "说明"

    `channel_type` 可以传枚举：

    ```python
    ChannelType.TEXT
    ChannelType.VOICE
    ```

    也可以传字符串：

    ```python
    "TEXT"
    "VOICE"
    ```

    如果字符串不属于允许值，SDK 会抛出 `ValueError`。

---

## `update_channel(area, channel_id, **kwargs)`

修改频道设置。

SDK 会先调用 `get_channel_setting_info(channel_id)` 获取当前频道设置，然后只覆盖你传入的字段，最后提交完整编辑数据。

```python
result = await client.channels.update_channel(
    area="域 ID",
    channel_id="频道 ID",
    name="新名称",
    text_gap_second=3,
    secret=True,
    accessible_members=["用户 UID"],
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `channel_id` | `str` | 是 | - | 频道 ID，不能为空。 |
    | `name` | `str | None` | 否 | `None` | 频道名称。 |
    | `text_gap_second` | `int | None` | 否 | `None` | 发言间隔秒数。 |
    | `voice_quality` | `str | None` | 否 | `None` | 语音质量。 |
    | `voice_delay` | `str | None` | 否 | `None` | 语音延迟模式。 |
    | `max_member` | `int | None` | 否 | `None` | 最大成员数。 |
    | `voice_control_enabled` | `bool | None` | 否 | `None` | 是否启用语音权限控制。 |
    | `text_control_enabled` | `bool | None` | 否 | `None` | 是否启用文字权限控制。 |
    | `access_control_enabled` | `bool | None` | 否 | `None` | 是否启用访问控制。 |
    | `secret` | `bool | None` | 否 | `None` | 是否为私密频道。需要同accessible_roles和accessible_members配合使用。 |
    | `has_password` | `bool | None` | 否 | `None` | 是否设置频道密码。 |
    | `password` | `str | None` | 否 | `None` | 频道密码。传 `password` 时必须同时设置 `has_password=True`。 |
    | `text_roles` | `list[int] | None` | 否 | `None` | 可发送文字消息的身份组 ID 列表。 |
    | `voice_roles` | `list[int] | None` | 否 | `None` | 可进入语音的身份组 ID 列表。 |
    | `accessible_roles` | `list[int] | None` | 否 | `None` | 可访问该频道的身份组 ID 列表，仅私密频道可设置。 |
    | `accessible_members` | `list[str] | None` | 否 | `None` | 可访问该频道的成员 UID 列表，仅私密频道可设置。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

=== "说明"

    当 `secret=True` 时，SDK 会自动把当前机器人自己的 UID 加入 `accessible_members`，避免频道改为私密后机器人失去访问权限。

    如果设置 `accessible_roles` 或 `accessible_members`，但最终 `secret=False`，SDK 会抛出 `ValueError`：

    ```python
    await client.channels.update_channel(
        area="域 ID",
        channel_id="频道 ID",
        accessible_members=["用户 UID"],
    )
    ```

    上面这种写法可能会失败，因为访问控制成员只允许在私密频道中设置。你可以这样写：

    ```python
    await client.channels.update_channel(
        area="域 ID",
        channel_id="频道 ID",
        secret=True,
        accessible_members=["用户 UID"],
    )
    ```

    密码设置规则：

    ```python
    # 设置密码
    await client.channels.update_channel(
        area="域 ID",
        channel_id="频道 ID",
        has_password=True,
        password="123456",
    )

    # 清除密码
    await client.channels.update_channel(
        area="域 ID",
        channel_id="频道 ID",
        has_password=False,
    )
    ```

    如果只传 `password`，但没有传 `has_password=True`，SDK 会抛出 `ValueError`。

---

## `delete_channel(area, channel)`

删除频道。

```python
result = await client.channels.delete_channel(
    area="域 ID",
    channel="频道 ID",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `channel` | `str` | 是 | 频道 ID，不能为空。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## `enter_channel(channel, area, channel_type="TEXT", from_channel="", from_area="", pid="")`

进入指定频道。

进入文字频道时通常只需要传 `channel`、`area` 和 `channel_type="TEXT"`。

进入语音频道时，SDK 会额外请求 sign 信息，并返回 `ChannelSign`。

```python
sign = await client.channels.enter_channel(
    channel="语音频道 ID",
    area="域 ID",
    channel_type="VOICE",
    pid="数字 PID", # 这个uid是bot的数字id, 也就是加好友的id
)

print(sign.room_id)
print(sign.rtc_token)

```

!!! note
    用户数字pid (加好友使用): `1234567890`
    字符串uid (内部请求使用): `6adadd1bcaddd1e867842331981a0972`

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `channel` | `str` | 是 | - | 频道 ID，不能为空。 |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `channel_type` | `str` | 否 | `"TEXT"` | 频道类型。进入语音频道时传 `"VOICE"`。 |
    | `from_channel` | `str` | 否 | `""` | 来源频道 ID，语音频道切换时使用。 |
    | `from_area` | `str` | 否 | `""` | 来源域 ID，语音频道切换时可使用。 |
    | `pid` | `str` | 否 | `""` | 用户 ID。进入语音频道时需要传入。 |

=== "返回值"

    返回：`ChannelSign`。

    对应模型：`oopz_sdk.models.ChannelSign`

    | 字段 / 属性 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `agora_sign` | `str` | `""` | Agora sign。 |
    | `agora_sign_pid` | `str` | `""` | Agora sign 对应的 pid。 |
    | `app_id` | `int` | `0` | App ID。 |
    | `disable_text_to` | `Any` | `None` | 禁言到期时间或状态。 |
    | `disable_voice_to` | `Any` | `None` | 禁麦到期时间或状态。 |
    | `expire_seconds` | `int` | `86400` | sign 有效期，单位秒。 |
    | `now` | `int` | `0` | 服务端时间戳。 |
    | `role_sort` | `int` | `0` |  |
    | `room_id` | `str` | `""` | 房间 ID。 |
    | `supplier` | `str` | `""` | 供应商。 |
    | `supplier_sign` | `str` | `""` | 供应商 sign。 |
    | `user_sign` | `str` | `""` | 用户 sign。 |
    | `voice_delay` | `str` | `"LOW"` | 语音延迟。 |
    | `voice_quality` | `str` | `"64k"` | 语音质量。 |

=== "说明"

    一般业务使用更高层的 `bot.voice.join()` 更方便。

    如果你只需要获取语音频道的参数，可以直接使用 `enter_channel()`。

---

## `leave_voice_channel(channel, area, target=None)`

退出语音频道。

如果 `target` 为空，SDK 会使用当前配置里的 `person_uid`，也就是让当前机器人账号退出语音频道。

```python
result = await client.channels.leave_voice_channel(
    channel="语音频道 ID",
    area="域 ID",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `channel` | `str` | 是 | - | 语音频道 ID，不能为空。 |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `target` | `str | None` | 否 | `None` | 要移出语音频道的用户 UID；不传时默认使用当前机器人 UID。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## `get_voice_channel_members(area)`

获取域内各语音频道的在线成员列表。

SDK 会先通过 `areas.get_area_channels(area)` 找出该域下所有语音频道，然后调用接口获取这些语音频道中的成员。

```python
result = await client.channels.get_voice_channel_members(area="域 ID")

for channel_id, members in result.channel_members.items():
    print("channel:", channel_id)

    for member in members:
        print(member.uid, member.is_bot)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |

=== "返回值"

    返回：`VoiceChannelMembersResult`。

    对应模型：`oopz_sdk.models.VoiceChannelMembersResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `channel_members` | `dict[str, list[VoiceChannelMemberInfo]]` | `{}` | 语音频道 ID 到成员列表的映射。 |

    `VoiceChannelMemberInfo` 字段：

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `uid` | `str` | `""` | 用户 UID。 |
    | `bot_type` | `str` | `""` | 机器人类型。官方内部保留字段 |
    | `dimensions` | `str` | `""` |  |
    | `enter_time` | `str` | `""` | 进入语音频道时间。 |
    | `framerate` | `str` | `""` | 帧率信息。 |
    | `is_bot` | `bool` | `False` | 是否为机器人。官方内部保留字段 |
    | `people_limit` | `int` | `0` |  |
    | `screen_sharing_state` | `str` | `""` | 屏幕共享状态。 |
    | `screen_type` | `str` | `""` | 屏幕类型。 |
    | `sort` | `int` | `0` | 排序值。 |

=== "缓存说明"

    SDK 会缓存语音频道 ID 列表 300 秒。

    缓存的只是“哪些频道是语音频道”，不是语音频道里的成员列表。

---

## `get_voice_channel_for_user(user_uid, area)`

查询用户当前所在的语音频道 ID。

如果用户不在任何语音频道中，返回 `None`。

```python
channel_id = await client.channels.get_voice_channel_for_user(
    user_uid="用户 UID",
    area="域 ID",
)

if channel_id is None:
    print("用户当前不在语音频道")
else:
    print("用户所在语音频道:", channel_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `user_uid` | `str` | 是 | 用户 UID。 |
    | `area` | `str` | 是 | 域 ID，不能为空。 |

=== "返回值"

    返回：`str | None`。

    | 返回值 | 说明 |
    | --- | --- |
    | `str` | 用户所在的语音频道 ID。 |
    | `None` | 用户当前不在该域的任何语音频道。 |

=== "说明"

    该方法内部会调用 `get_voice_channel_members(area)`，然后遍历每个语音频道成员：

    ```python
    for ch_id, ch_members in members.channel_members.items():
        for m in ch_members:
            if m.uid == user_uid:
                return ch_id
    return None
    ```

---

## 常见任务：创建文字频道

```python
from oopz_sdk.models.channel import ChannelType

result = await client.channels.create_channel(
    area="域 ID",
    name="公告",
    channel_type=ChannelType.TEXT,
)

print(result.name)
```

---

## 常见任务：创建语音频道

```python
from oopz_sdk.models.channel import ChannelType

result = await client.channels.create_channel(
    area="域 ID",
    name="语音房间",
    channel_type=ChannelType.VOICE,
)

print(result.name)
```

---