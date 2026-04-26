# Area Service

入口：`client.areas` 或 `bot.areas`。

## 方法列表

| 方法 | 说明 | 返回 |
| --- | --- | --- |
| `get_area_members(area, offset_start=0, offset_end=49)` | 获取域成员分页，带短期缓存。 | `AreaMembersPage` |
| `get_joined_areas()` | 获取当前用户已加入的域列表。 | `list[JoinedAreaInfo]` |
| `get_area_info(area)` | 获取域详细信息。 | `AreaInfo` |
| `edit_area_name(area, name)` | 修改域名称。 | `OperationResult` |
| `enter_area(area, recover=False)` | 进入指定域。 | `dict` |
| `get_area_channels(area)` | 获取域内频道分组与频道列表。 | `list[ChannelGroupInfo]` |
| `get_area_user_detail(area, target)` | 获取用户在域内的角色和禁言/禁麦状态。 | `AreaUserDetail` |
| `get_area_can_give_list(area, target)` | 获取当前用户可以分配给目标用户的身份组。 | `list[RoleInfo]` |
| `edit_user_role(target_uid, role_id, area, add=True)` | 添加或移除目标用户身份组。 | `OperationResult` |
| `get_user_area_nicknames(area, uids)` | 批量获取用户在域内的昵称。 | `dict[str, str]` |
| `populate_names(set_area=None, set_channel=None)` | 预填充或解析名称缓存。 | `dict` |

## 获取域成员

```python
page = await client.areas.get_area_members("域 ID", offset_start=0, offset_end=49)
print(page.total_count, page.members)
```

缓存相关配置：

- `config.area_members_cache_ttl`：缓存有效期，默认 15 秒。
- `config.cache_max_entries`：最大缓存条目，小于等于 0 表示关闭缓存。

## 获取域频道

```python
groups = await client.areas.get_area_channels(area)
for group in groups:
    print(group.group_id, group.name)
    for channel in group.channels:
        print(channel.channel_id, channel.name, channel.channel_type)
```

## 修改用户身份组

```python
await client.areas.edit_user_role(
    target_uid="用户 UID",
    role_id=123,
    area="域 ID",
    add=True,
)
```

`edit_user_role()` 会先读取用户当前角色，再合并目标角色后提交完整角色列表。
