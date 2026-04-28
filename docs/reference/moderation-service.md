# Moderation Service

`Moderation Service` 用于域内管理操作，包括禁言、解除禁言、禁麦、解除禁麦、踢出用户、拉黑用户、查询黑名单和取消拉黑。

---

## `mute_user(area, uid, duration=TextMuteInterval.M5)`

禁言域内用户。

如果不传 `duration`，默认禁言 5 分钟。

```python
from oopz_sdk.models import TextMuteInterval

result = await bot.moderation.mute_user(
    area="域 ID",
    uid="用户 UID",
    duration=TextMuteInterval.M5,
)

print(result.ok)
```

也可以直接传分钟数：

```python
await bot.moderation.mute_user(
    area="域 ID",
    uid="用户 UID",
    duration=60,
)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `uid` | `str` | 是 | - | 目标用户 UID，不能为空。 |
    | `duration` | `TextMuteInterval \| int \| None` | 否 | `TextMuteInterval.M5` | 禁言时长。如果传 `int`，表示分钟数，SDK 会自动选择不小于该分钟数的禁言档位。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

=== "时长档位"

    对应枚举：`oopz_sdk.models.TextMuteInterval`

    | 枚举 | 分钟数 | 说明 |
    | --- | --- | --- |
    | `TextMuteInterval.S60` | `1` | 60 秒。 |
    | `TextMuteInterval.M5` | `5` | 5 分钟。 |
    | `TextMuteInterval.H1` | `60` | 1 小时。 |
    | `TextMuteInterval.D1` | `1440` | 1 天。 |
    | `TextMuteInterval.D3` | `4320` | 3 天。 |
    | `TextMuteInterval.D7` | `10080` | 7 天。 |

=== "说明"

    如果 `duration` 传入整数，SDK 会调用：

    ```python
    TextMuteInterval.pick(int(duration))
    ```

    选择第一个分钟数大于等于传入值的档位。

    例如：

    | 传入 | 实际档位 |
    | --- | --- |
    | `1` | `TextMuteInterval.S60` |
    | `3` | `TextMuteInterval.M5` |
    | `30` | `TextMuteInterval.H1` |
    | `2000` | `TextMuteInterval.D3` |
    | `999999` | `TextMuteInterval.D7` |

---

## `unmute_user(area, uid)`

解除用户在域内的禁言状态。

```python
result = await bot.moderation.unmute_user(
    area="域 ID",
    uid="用户 UID",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `uid` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## `mute_mic(uid, area, duration=VoiceMuteInterval.M5)`

禁麦域内用户。

```python
from oopz_sdk.models import VoiceMuteInterval

result = await bot.moderation.mute_mic(
    area="域 ID",
    uid="用户 UID",
    duration=VoiceMuteInterval.M5,
)

print(result.ok)
```

也可以直接传分钟数：

```python
await bot.moderation.mute_mic(
    area="域 ID",
    uid="用户 UID",
    duration=60,
)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `uid` | `str` | 是 | - | 目标用户 UID，不能为空。 |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `duration` | `VoiceMuteInterval \| int \| None` | 否 | `VoiceMuteInterval.M5` | 禁麦时长。如果传 `int`，表示分钟数，SDK 会自动选择不小于该分钟数的禁麦档位。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

=== "时长档位"

    对应枚举：`oopz_sdk.models.VoiceMuteInterval`

    | 枚举 | 分钟数 | 说明 |
    | --- | --- | --- |
    | `VoiceMuteInterval.S60` | `1` | 60 秒。 |
    | `VoiceMuteInterval.M5` | `5` | 5 分钟。 |
    | `VoiceMuteInterval.H1` | `60` | 1 小时。 |
    | `VoiceMuteInterval.D1` | `1440` | 1 天。 |
    | `VoiceMuteInterval.D3` | `4320` | 3 天。 |
    | `VoiceMuteInterval.D7` | `10080` | 7 天。 |

=== "说明"

    如果 `duration` 传入整数，SDK 会调用：

    ```python
    VoiceMuteInterval.pick(int(duration))
    ```

    选择第一个分钟数大于等于传入值的档位。

---

## `unmute_mic(area, uid)`

解除用户在域内的禁麦状态。

```python
result = await bot.moderation.unmute_mic(
    area="域 ID",
    uid="用户 UID",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `uid` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## `remove_from_area(area, uid)`

将用户移出指定域。

```python
result = await bot.moderation.remove_from_area(
    area="域 ID",
    uid="用户 UID",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `uid` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

=== "权限说明"

    该接口通常需要当前机器人账号在目标域内具备移出成员的权限。

---

## `block_user_in_area(area, uid)`

将用户加入指定域的黑名单。

```python
result = await bot.moderation.block_user_in_area(
    area="域 ID",
    uid="用户 UID",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `uid` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

=== "权限说明"

    该接口通常需要当前机器人账号在目标域内具备拉黑成员的权限。

---

## `get_area_blocks(area, name="")`

获取指定域的黑名单列表。

可以通过 `name` 参数按名称过滤。

```python
users = await bot.moderation.get_area_blocks(
    area="域 ID",
    name="",
)

for user in users:
    print(user.uid, user.name)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `area` | `str` | 是 | - | 域 ID，不能为空。 |
    | `name` | `str` | 否 | `""` |  |

=== "返回值"

    返回：`list[UserInfo]`。

    对应模型：`oopz_sdk.models.UserInfo`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `avatar` | `str` | `""` | 用户头像 URL。 |
    | `avatar_frame` | `str` | `""` | 头像框。 |
    | `avatar_frame_animation` | `str` | `""` | 动态头像框。 |
    | `avatar_frame_expire_time` | `int` | `0` | 头像框过期时间。 |
    | `badges` | `Any` | `None` | 用户徽章数据。 |
    | `introduction` | `str` | `""` | 用户简介。 |
    | `mark` | `str` | `""` | 用户标记。 |
    | `mark_expire_time` | `int` | `0` | 标记过期时间。 |
    | `mark_name` | `str` | `""` | 标记名称。 |
    | `name` | `str` | `""` | 用户昵称。 |
    | `online` | `bool` | `False` | 是否在线。 |
    | `memberLevel` | `int` | `0` | 用户等级 |
    | `person_role` | `str` | `""` | 用户角色。 `NORMAL`, `VIP`  |
    | `person_type` | `str` | `""` | 用户类型。 |
    | `pid` | `str` | `""` | 用户 PID。 |
    | `status` | `str` | `""` | 用户状态。 |
    | `uid` | `str` | `""` | 用户 UID。 |
    | `user_common_id` | `str` | `""` | 用户 common ID。 |

---

## `unblock_user_in_area(area, uid)`

将用户从指定域的黑名单中移除。

```python
result = await bot.moderation.unblock_user_in_area(
    area="域 ID",
    uid="用户 UID",
)

print(result.ok)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `area` | `str` | 是 | 域 ID，不能为空。 |
    | `uid` | `str` | 是 | 目标用户 UID，不能为空。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## 常见任务：禁言与解禁

禁言 5 分钟：

```python
from oopz_sdk.models import TextMuteInterval

await bot.moderation.mute_user(
    area="域 ID",
    uid="用户 UID",
    duration=TextMuteInterval.M5,
)
```

解除禁言：

```python
await bot.moderation.unmute_user(
    area="域 ID",
    uid="用户 UID",
)
```

---

## 常见任务：禁麦与解除禁麦

禁麦 5 分钟：

```python
from oopz_sdk.models import VoiceMuteInterval

await bot.moderation.mute_mic(
    area="域 ID",
    uid="用户 UID",
    duration=VoiceMuteInterval.M5,
)
```

解除禁麦：

```python
await bot.moderation.unmute_mic(
    area="域 ID",
    uid="用户 UID",
)
```

---

## 常见任务：踢出与拉黑

踢出用户：

```python
await bot.moderation.remove_from_area(
    area="域 ID",
    uid="用户 UID",
)
```

拉黑用户：

```python
await bot.moderation.block_user_in_area(
    area="域 ID",
    uid="用户 UID",
)
```

取消拉黑：

```python
await bot.moderation.unblock_user_in_area(
    area="域 ID",
    uid="用户 UID",
)
```

---

## 权限说明

管理类接口通常需要机器人账号在目标域内具备相应权限。

如果接口返回失败，可以优先检查：

1. 机器人是否在目标域内。
2. 机器人是否拥有管理目标用户的权限。
3. 目标用户是否拥有更高身份组。
4. `area` 和 `uid` 是否正确。