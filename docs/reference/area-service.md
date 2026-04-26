# Area Service

`Area Service` 用于获取域信息、域成员、频道分组、域内用户状态、身份组。

---

## `get_area_members(area, offset_start=0, offset_end=49)`

获取域成员分页，带短期缓存。

```python
page = await bot.areas.get_area_members(
    area="域 ID",
    offset_start=0,
    offset_end=49,
)

print(page.total_count)

for member in page.members:
    print(member.uid, member.name)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `offset_start` | `int` | 否 | `0` | 分页起始位置。 |
    | `offset_end` | `int` | 否 | `49` | 分页结束位置。 |

=== "返回值"

    返回：`AreaMembersPage`。

    对应模型：`oopz_sdk.models.AreaMembersPage`

    | 字段 | 类型 | 说明 |
    | --- | --- | --- |
    | `total_count` | `int` | 域成员总数。 |
    | `members` | `list[AreaMemberInfo]` | 当前分页中的成员列表。 |
    | `roleCount` | `list[AreaRoleCountInfo]` |  |

    `AreaMemberInfo` 常见字段：

    | 字段 | 类型 | 说明 |
    | --- | --- | --- |
    | `uid` | `str` | 用户id |
    | `display_type` | `str` | 显示状态类型, 例如`MUSIC`/`GAME` |
    | `online` | `int` | 用户在线状态 |
    | `playing_state` | `str` | 用户游玩/听歌状态 |
    | `role` | `int` | 域角色id |
    | `role_sort` | `int` |  |
    | `role_status` | `int` |  |


=== "缓存说明"

    `get_area_members()` 带短期缓存。

    相关配置：

    | 配置 | 默认值 | 说明 |
    | --- | --- | --- |
    | `config.area_members_cache_ttl` | `15` | 域成员缓存有效期，单位为秒。 |
    | `config.cache_max_entries` | - | 最大缓存条目数；小于等于 `0` 表示关闭缓存。 |

---

## `get_joined_areas()`

获取当前用户已加入的域列表。

```python
areas = await client.areas.get_joined_areas()

for area in areas:
    print(area.area_id, area.name)
```

=== "参数"

    无参数。

=== "返回值"

    返回：`list[JoinedAreaInfo]`。

    对应模型：`oopz_sdk.models.JoinedAreaInfo`

    | 字段 | 类型 | API 字段 | 说明 |
    | --- | --- | --- | --- |
    | `area_id` | `str` | `id` | 域 ID |
    | `code` | `str` | `code` |   |
    | `name` | `str` | `name` | 域名称 |
    | `avatar` | `str` | `avatar` | 域头像的url |
    | `banner` | `str` | `banner` | 域横幅的url |
    | `level` | `int` | `level` | 域等级 |
    | `owner` | `str` | `owner` | 域主 UID |
    | `group_id` | `str` | `groupID` |  |
    | `group_name` | `str` | `groupName` | |
    | `subscript` | `int` | `subscript` |  |

---

## `get_area_info(area)`

获取指定域的详细信息。

```python
info = await client.areas.get_area_info("域 ID")
print(info.area_id, info.name)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |

=== "返回值"

    返回：`AreaInfo`。

    对应模型：`oopz_sdk.models.AreaInfo`

    | 字段 | 类型 | 说明 |
    | --- | --- | --- |
    | `area_id` | `str` | 域 ID。 |
    | `name` | `str` | 域名称。 |
    | `avatar` | `str` | 域头像。 |
    | `banner` | `str` | 域横幅。 |
    | `owner` | `str` | 域主 UID。 |
    | `raw` | `dict` | 原始响应数据，具体字段以接口返回为准。 |

---

## `edit_area_name(area, name)`

修改域名称。

```python
result = await client.areas.edit_area_name(
    area="域 ID",
    name="新的域名称",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `name` | `str` | 是 | 新的域名称，不能为空。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## `enter_area(area, recover=False)`

进入指定域。

```python
result = await client.areas.enter_area(
    area="域 ID",
    recover=False,
)

print(result)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `recover` | `bool` | 否 | `False` | 是否恢复进入状态。 |

=== "返回值"

    返回：`dict`。

    该方法直接返回接口原始数据。具体字段以当前 Oopz 接口返回为准。

---

## `get_area_channels(area)`

获取域内频道分组与频道列表。

```python
groups = await client.areas.get_area_channels(area="域 ID")

for group in groups:
    print(group.group_id, group.name)

    for channel in group.channels:
        print(channel.channel_id, channel.name, channel.channel_type)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |

=== "返回值"

    返回：`list[ChannelGroupInfo]`。

    对应模型：`oopz_sdk.models.ChannelGroupInfo`

    | 字段 | 类型 | API 字段 | 说明 |
    | --- | --- | --- | --- |
    | `group_id` | `str` | `groupId` / `id` | 频道分组 ID。 |
    | `name` | `str` | `name` | 频道分组名称。 |
    | `channels` | `list[ChannelInfo]` | `channels` | 分组下的频道列表。 |

    `ChannelInfo` 常见字段：

    | 字段 | 类型 | 说明 |
    | --- | --- | --- |
    | `channel_id` | `str` | 频道 ID。 |
    | `name` | `str` | 频道名称。 |
    | `channel_type` | `str` | 频道类型。 |
    | `area` | `str` | 所属域 ID。 |

---

## `get_area_user_detail(area, target)`

获取用户在域内的角色和禁言 / 禁麦状态。

```python
detail = await client.areas.get_area_user_detail(
    area="域 ID",
    target="用户 UID",
)

print(detail.roles)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `target` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`AreaUserDetail`。

    对应模型：`oopz_sdk.models.AreaUserDetail`

    | 字段 | 类型 | 说明 |
    | --- | --- | --- |
    | `roles` | `list[int]` | 用户当前拥有的身份组 ID 列表。 |
    | `disable_text_to` | `str \| None` | 禁言到期时间或状态。 |
    | `disable_voice_to` | `str \| None` | 禁麦到期时间或状态。 |
    | `raw` | `dict` | 原始响应数据，具体字段以接口返回为准。 |

---

## `get_area_can_give_list(area, target)`

获取当前用户可以分配给目标用户的身份组。

```python
roles = await client.areas.get_area_can_give_list(
    area="域 ID",
    target="用户 UID",
)

for role in roles:
    print(role.role_id, role.name)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `target` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`list[RoleInfo]`。

    对应模型：`oopz_sdk.models.RoleInfo`

    | 字段 | 类型 | 说明 |
    | --- | --- | --- |
    | `role_id` | `int` | 身份组 ID。 |
    | `name` | `str` | 身份组名称。 |
    | `color` | `str` | 身份组颜色。 |
    | `raw` | `dict` | 原始响应数据，具体字段以接口返回为准。 |

---

## `edit_user_role(target_uid, role_id, area, add=True)`

添加或移除目标用户身份组。

`edit_user_role()` 会先读取用户当前角色，再合并目标角色后提交完整角色列表。

```python
result = await client.areas.edit_user_role(
    target_uid="用户 UID",
    role_id=123,
    area="域 ID",
    add=True,
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `target_uid` | `str` | 是 | - | 目标用户 UID，不能为空。 |
    | `role_id` | `int` | 是 | - | 要添加或移除的身份组 ID。 |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `add` | `bool` | 否 | `True` | `True` 表示添加身份组，`False` 表示移除身份组。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

=== "说明"

    该方法不是简单地提交单个 `role_id`。

    SDK 内部会先调用 `get_area_user_detail(area, target_uid)` 获取当前角色列表，然后：

    - `add=True`：把 `role_id` 加入当前角色列表。
    - `add=False`：从当前角色列表移除 `role_id`。

    最后再提交合并后的完整角色列表。

---

## `get_user_area_nicknames(area, uids)`

批量获取用户在指定域内的昵称。

```python
nicknames = await client.areas.get_user_area_nicknames(
    area="域 ID",
    uids=["用户 UID 1", "用户 UID 2"],
)

print(nicknames)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `uids` | `list[str]` | 是 | 用户 UID 列表。 |

=== "返回值"

    返回：`dict[str, str]`。

    字典结构：

    | Key | Value |
    | --- | --- |
    | 用户 UID | 用户在该域内的昵称 |

---

## `populate_names(set_area=None, set_channel=None)`

预填充或解析名称缓存。

该方法通常用于让日志、调试输出或事件上下文中可以更容易显示 area/channel 名称。

```python
names = await client.areas.populate_names(
    set_area="域 ID",
    set_channel="频道 ID",
)

print(names)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `set_area` | `str \| None` | 否 | `None` | 指定要解析或缓存的域 ID。 |
    | `set_channel` | `str \| None` | 否 | `None` | 指定要解析或缓存的频道 ID。 |

=== "返回值"

    返回：`dict`。

    常见结构：

    | 字段 | 类型 | 说明 |
    | --- | --- | --- |
    | `area` | `str \| None` | 域 ID。 |
    | `area_name` | `str \| None` | 域名称。 |
    | `channel` | `str \| None` | 频道 ID。 |
    | `channel_name` | `str \| None` | 频道名称。 |

---

## 常见任务：获取域和频道 ID

很多用户第一次使用 SDK 时，不知道 `area` 和 `channel` 应该填什么。可以先调用 `get_joined_areas()` 和 `get_area_channels()`
打印出来。

```python
areas = await client.areas.get_joined_areas()

for area in areas:
    print("Area:", area.area_id, area.name)

    groups = await client.areas.get_area_channels(area.area_id)

    for group in groups:
        print("  Group:", group.group_id, group.name)

        for channel in group.channels:
            print("    Channel:", channel.channel_id, channel.name, channel.channel_type)
```

---

## 常见任务：修改用户身份组

```python
await client.areas.edit_user_role(
    target_uid="用户 UID",
    role_id=123,
    area="域 ID",
    add=True,
)
```

如果要移除身份组：

```python
await client.areas.edit_user_role(
    target_uid="用户 UID",
    role_id=123,
    area="域 ID",
    add=False,
)
```