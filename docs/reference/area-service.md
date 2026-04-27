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

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `area_id` | `str` | "" | 域 ID |
    | `code` | `str` | "" |   |
    | `name` | `str` | "" | 域名称 |
    | `avatar` | `str` | "" | 域头像的url |
    | `banner` | `str` | "" | 域横幅的url |
    | `level` | `int` | 0 | 域等级 |
    | `owner` | `str` | "" | 域主 UID |
    | `group_id` | `str` | "" |  |
    | `group_name` | `str` | "" | |
    | `subscript` | `int` | 0 |  |

---

## `get_area_info(area)`

获取指定域的详细信息，包括域基础信息、当前用户在该域内的权限信息、身份组列表、主页频道等。

```python
info = await client.areas.get_area_info("域 ID")

print(info.area_id, info.name)
print(info.home_page_channel_id)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |

=== "返回值"

    返回：`AreaInfo`。

    对应模型：`oopz_sdk.models.AreaInfo`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `avatar` | `str` | `""` | 域头像 URL。 |
    | `banner` | `str` | `""` | 域横幅 URL。 |
    | `code` | `str` | `""` | 域数字id。 |
    | `desc` | `str` | `""` | 域描述。 |
    | `disable_text_to` | `str | None` | `None` | 当前用户禁言到期时间。 |
    | `disable_voice_to` | `str | None` | `None` | 当前用户禁麦到期时间。 |
    | `edit_count` | `int` | `0` | 域信息编辑次数。 |
    | `home_page_channel_id` | `str` | `""` | 域主页频道 ID。 |
    | `area_id` | `str` | `""` | 域 ID。 |
    | `is_public` | `bool` | `False` | 是否为公开域。 |
    | `name` | `str` | `""` | 域名称。 |
    | `now` | `int` | `0` | 服务端时间戳。 |
    | `private_channels` | `list[str]` | `[]` | 私密频道 ID 列表。 |
    | `role_list` | `list[AreaRole]` | `[]` | 域身份组列表。 |
    | `area_role_infos` | `AreaRoleInfo` | `AreaRoleInfo()` | 当前用户在该域内的角色和权限信息。 |
    | `subscribed` | `bool` | `False` | 当前用户是否已订阅 / 加入该域。 |

    `AreaRoleInfo` 字段：

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `category_keys` | `list[str]` | `[]` | 当前用户拥有的分类权限 key。 |
    | `is_owner` | `bool` | `False` | 当前用户是否为域主。 |
    | `max_role` | `int` | `0` | 当前用户最高身份组的id。 |
    | `privilege_keys` | `list[str]` | `[]` | 当前用户拥有的权限 key。 |
    | `roles` | `list[int]` | `[]` | 当前用户拥有的身份组 ID 列表。 |

    `AreaRole` 字段：

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `description` | `str` | `""` | 身份组描述。 |
    | `is_display` | `bool` | `False` | 是否展示该身份组。 |
    | `name` | `str` | `""` | 身份组名称。 |
    | `role_id` | `int` | `0` | 身份组 ID。 |
    | `sort` | `int` | `0` |  |
    | `type` | `int` | `0` | 身份组类型。 |

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
    | `recover` | `bool` | 否 | `False` | |

=== "返回值"

    返回：`dict`。

    当前代码中该方法会直接返回接口原始数据：

    ```python
    return data if isinstance(data, dict) else {}
    ```

    因为这个接口的使用方式还未完全确定

---

## `get_area_channels(area)`

获取域内频道分组与频道列表。

```python
groups = await bot.areas.get_area_channels(area="域 ID")

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

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `is_enable_temp` | `bool` | `False` | 是否启用临时频道。 |
    | `area` | `str` | `""` | 所属域 ID。 |
    | `channels` | `list[ChannelInfo]` | `[]` | 分组下的频道列表。 |
    | `group_id` | `str` | `""` | 频道分组 ID。 |
    | `name` | `str` | `""` | 频道分组名称。 |
    | `sort` | `int` | `0` | 分组排序。 |
    | `system` | `bool` | `False` | 是否为系统分组。 |
    | `temp_channel_default_max_member` | `int` | `0` | 临时频道默认最大人数。 |
    | `temp_channel_max_limit_member` | `int` | `0` | 临时频道最大人数上限。 |
    
    临时频道暂不明确相关字段的含义。

    `ChannelInfo` 字段：

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `area_id` | `str` | `""` | 所属域 ID。 |
    | `group_id` | `str` | `""` | 所属频道分组 ID。 |
    | `channel_id` | `str` | `""` | 频道 ID。 |
    | `is_temp` | `bool` | `False` | 是否为临时频道。 |
    | `name` | `str` | `""` | 频道名称。 |
    | `number` | `int` | `0` |  |
    | `secret` | `bool` | `False` | 是否为私密频道。 |
    | `settings` | `ChannelSettings` | `ChannelSettings()` | 频道设置。 |
    | `system` | `bool` | `False` | 是否为系统频道。 |
    | `tag` | `str` | `""` | 频道标签。 |
    | `channel_type` | `str` | `""` | 频道类型。 |

    `ChannelSettings` 字段：

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `disable_text_levels` | `list[int] | None` | `None` |  |
    | `disable_voice_levels` | `list[int] | None` | `None` |  |
    | `max_member` | `int` | `0` | 最大成员数。 |
    | `member_public` | `bool` | `False` |  |
    | `text_control_enabled` | `bool` | `False` | 是否启用文本权限控制。 |
    | `text_gap_second` | `int` | `0` | 文本消息间隔秒数。 |
    | `text_roles` | `list[int]` | `[]` | 可发送文本的身份组列表。 |
    | `voice_control_enabled` | `bool` | `False` | 是否启用语音权限控制。 |
    | `voice_delay` | `str` | `""` | 语音延迟配置。 |
    | `voice_quality` | `str` | `""` | 语音质量配置。 |
    | `voice_roles` | `list[int]` | `[]` | 可说话的身份组列表。 |

---

## `get_area_user_detail(area, target)`

获取用户在域内的角色、上级用户以及禁言 / 禁麦状态。

```python
detail = await client.areas.get_area_user_detail(
    area="域 ID",
    target="用户 UID",
)

print(detail.higher_uid)
print([role.role_id for role in detail.roles])
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `target` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`AreaUserDetail`。

    对应模型：`oopz_sdk.models.AreaUserDetail`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `disable_text_to` | `Any` | `None` | 禁言到期时间。 |
    | `disable_voice_to` | `Any` | `None` | 禁麦到期时间。 |
    | `higher_uid` | `str` | `""` | 用户 UID。 |
    | `roles` | `list[RoleInfo]` | `[]` | 用户当前拥有的身份组信息列表。 |
    | `now` | `int` | `0` | 服务端时间戳。 |

    `RoleInfo` 字段：

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `description` | `str` | `""` | 身份组描述。 |
    | `name` | `str` | `""` | 身份组名称。 |
    | `role_id` | `int` | `0` | 身份组 ID。 |
    | `sort` | `int` | `0` | 身份组排序。 |

    !!! note
        注意: RoleInfo 中没有 `owned` 字段
---

## `get_area_can_give_list(area, target)`

获取当前用户可以分配给目标用户的身份组。

```python
roles = await bot.areas.get_area_can_give_list(
    area="域 ID",
    target="用户 UID",
)

for role in roles:
    print(role.role_id, role.name, role.owned)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `target` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`list[RoleInfo]`。

    对应模型：`oopz_sdk.models.RoleInfo`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `description` | `str` | `""` | 身份组描述。 |
    | `name` | `str` | `""` | 身份组名称。 |
    | `owned` | `bool` | `False` | 当前用户是否拥有该身份组。 |
    | `role_id` | `int` | `0` | 身份组 ID。 |
    | `sort` | `int` | `0` | 身份组排序。 |

=== "说明"

    当前代码中，接口返回值必须包含 `roles` 字段：

    ```python
    roles = data.get("roles")
    ```

    如果接口响应中没有 `roles`，SDK 会抛出 `ValueError`。

---

## `edit_user_role(target_uid, role_id, area, add=True)`

添加或移除目标用户身份组。


```python
result = await bot.areas.edit_user_role(
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
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `target_uid` | `str` | 是 | - | 目标用户 UID，不能为空。 |
    | `role_id` | `int` | 是 | - | 要添加或移除的身份组 ID。 |
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

    SDK 内部会先调用：

    ```python
    area_info = await self.get_area_user_detail(area, target_uid)
    ```

    然后通过当前角色列表生成 `targetRoleIDs`：

    ```python
    current_ids = [role.role_id for role in area_info.roles]
    ```

    最后提交：

    ```python
    body = {
        "area": area,
        "target": target_uid,
        "targetRoleIDs": current_ids,
    }
    ```

---

## `populate_names(set_area=None, set_channel=None)`


=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `set_area` | `Callable[[str, str], None] \| None` | 否 | `None` | 域名称缓存回调，接收 `(area_id, area_name)`。 |
    | `set_channel` | `Callable[[str, str], None] \| None` | 否 | `None` | 频道名称缓存回调，接收 `(channel_id, channel_name)`。 |

=== "返回值"

    返回：`dict`。

    | 字段 | 类型 | 说明 |
    | --- | --- | --- |
    | `areas_named` | `int` | 成功回调 `set_area` 的域数量。 |
    | `channels_named` | `int` | 成功回调 `set_channel` 的频道数量。 |


## 常见任务：获取域和频道 ID

很多用户第一次使用 SDK 时，不知道 `area` 和 `channel` 应该填什么。可以先调用 `get_joined_areas()` 和 `get_area_channels()` 打印出来，
或者通过事件回调获取消息内部的发送信息。

!!! note
    Oopz内部使用的uid, 域id和频道id都不是暴露给用户(显示在web或者app页面)的数字id

```python
areas = await bot.areas.get_joined_areas()

for area in areas:
    print("Area:", area.area_id, area.name)

    groups = await bot.areas.get_area_channels(area.area_id)

    for group in groups:
        print("  Group:", group.group_id, group.name)

        for channel in group.channels:
            print("    Channel:", channel.channel_id, channel.name, channel.channel_type)
```