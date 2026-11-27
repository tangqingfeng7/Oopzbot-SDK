# Person Service

`Person` 提供用户资料、当前动态、等级和好友关系接口。


---

## `get_person_info(uid=None, force=False)`

获取指定用户的基本信息。

如果不传 `uid`，默认使用当前配置里的 `person_uid`，也就是当前bot的登录用户。

```python
me = await bot.person.get_person_info()

print(me.uid)
print(me.name)
```

获取指定用户：

```python
user = await bot.person.get_person_info("用户 UID")

print(user.uid, user.name)
```

=== "参数"

    | 参数 | 类型 | 必填 | 默认值 | 说明 |
    | --- | --- | --- | --- | --- |
    | `uid` | `str | None` | 否 | `None` | 用户 UID。不传时使用当前配置中的 `person_uid`。 |
    | `force` | `bool` | 否 | 是否强制重新获取并更新缓存 |    

=== "返回值"

    返回：`UserInfo`。

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

=== "缓存说明"

    `get_person_info()` 带短期缓存。

    相关配置：

    | 配置 | 默认值 | 说明 |
    | --- | --- | --- |
    | `config.userinfo_cache_ttl` | `1800.0` | 域成员缓存有效期，单位为秒。 |
    | `config.userinfo_cache_max_entries` | `5000` | 最大缓存条目数；小于等于 `0` 表示关闭缓存。 |


---

## `get_person_infos_batch(uids)`

批量获取用户基本信息。

该方法内部会按每 30 个 UID 分批请求，然后把结果合并为一个 `list[UserInfo]` 返回。


```python
users = await bot.person.get_person_infos_batch([
    "uid1",
    "uid2",
])

for user in users:
    print(user.uid, user.name, user.online)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `uids` | `list[str]` | 是 | 用户 UID 列表。如果传入空列表，直接返回 `[]`。 |

=== "返回值"

    返回：`list[UserInfo]`。

    对应模型：`oopz_sdk.models.UserInfo`

    可参考 `get_person_info()` 的返回值字段说明。

---


## `get_person_detail_full(uid, force=False)`

获取指定用户的完整资料, 会使用缓存。

相比 `get_person_info()`，该方法返回的信息更完整，例如 IP 属地、VIP 信息、关注数、粉丝数、主页装饰、游戏 / 音乐状态等。

```python
profile = await bot.person.get_person_detail_full("用户 UID")

print(profile.uid)
print(profile.name)
print(profile.ip_address)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `uid` | `str` | 是 | 用户 UID，不能为空。 |
    | `force` | `bool` | 否 | 是否强制重新获取并更新缓存 |

=== "返回值"

    返回：`Profile`。

    对应模型：`oopz_sdk.models.Profile`
    
    !!! warning
        下面的字段说明可能不完全正确, 仅供参考. 请以实际接口返回的字段为准. 
    
    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `area_avatar` | `str` | `""` | 暂未使用 |
    | `area_max_num` | `int` | `0` | 暂未使用 |
    | `area_name` | `str` | `""` | 暂未使用 |
    | `avatar` | `str` | `""` | 用户头像 URL |
    | `avatar_frame` | `str` | `""` | 头像框 |
    | `avatar_frame_animation` | `str` | `""` | 动态头像框 |
    | `avatar_frame_expire_time` | `int` | `0` | 头像框过期时间 |
    | `badges` | `list[Any]` | `[]` | 用户徽章列表 |
    | `banner` | `str` | `""` | 用户主页横幅 |
    | `card_decoration` | `str` | `""` | 资料卡装饰 |
    | `card_decoration_expire_time` | `int` | `0` | 资料卡装饰过期时间 |
    | `community_personal_rec` | `bool` | `False` | |
    | `default_avatar` | `bool` | `False` | 是否使用默认头像 |
    | `default_name` | `bool` | `False` | 是否使用默认名称 |
    | `disabled_end_time` | `int` | `0` | 禁用结束时间 |
    | `disabled_start_time` | `int` | `0` | 禁用开始时间 |
    | `display_playing_state` | `Any` | `None` | 动态展示开关，公开资料可能为空。 |
    | `display_type` | `str` | `""` | 展示状态类型`GAME`, `MUSIC` |
    | `fans_count` | `int` | `0` | 粉丝数 |
    | `fixed_private_message` | `bool` | `False` |  |
    | `follow_count` | `int` | `0` | 关注数 |
    | `follow_private` | `bool` | `False` |  |
    | `greeting` | `str` | `""` |  |
    | `introduction` | `str` | `""` | 用户简介 |
    | `ip_address` | `str` | `""` | IP 属地 |
    | `is_abroad` | `bool` | `False` |  |
    | `like_count` | `int` | `0` | 获赞数 |
    | `mark` | `str` | `""` | 用户标记 |
    | `mark_expire_time` | `int` | `0` | 标记过期时间 |
    | `mark_name` | `str` | `""` | 标记名称 |
    | `mobile_banner` | `str` | `""` | 移动端主页横幅 |
    | `music_state` | `str` | `""` | 音乐状态 |
    | `mute` | `Any` | `None` | 静音状态 |
    | `mutual_follow_count` | `int` | `0` | 互相关注数量 |
    | `name` | `str` | `""` | 用户昵称 |
    | `online` | `bool` | `False` | 是否在线 |
    | `person_role` | `str` | `""` | 用户角色 `NORMAL`, `VIP`  |
    | `person_type` | `str` | `""` | 用户类型 |
    | `person_vip_end_time` | `int` | `0` | VIP 结束时间 |
    | `person_vip_start_time` | `int` | `0` | VIP 开始时间 |
    | `phone` | `str` | `""` | 手机号 |
    | `pid` | `str` | `""` | 用户 PID |
    | `pid_level_name` | `str` | `""` | PID 等级名称 |
    | `pid_tag_black` | `str` | `""` |  |
    | `pid_tag_white` | `str` | `""` |  |
    | `playing_game_image` | `str` | `""` | 正在游玩游戏的图片 |
    | `playing_state` | `str` | `""` | 正在游玩状态 |
    | `playing_time` | `int` | `0` | 游玩时长或状态时间 |
    | `pwd_set_time` | `int` | `0` |  |
    | `recommend_area` | `str` | `""` |  |
    | `song_state` | `str` | `""` | 歌曲状态 |
    | `status` | `str` | `""` | 用户状态 |
    | `stealth` | `bool` | `False` | 是否隐身 |
    | `uid` | `str` | `""` | 用户 UID |
    | `use_booster` | `bool` | `False` | 是否使用加速器或增强权益 |
    | `user_common_id` | `str` | `""` | 用户 common ID |
    | `user_level` | `int` | `0` | 用户等级 |
    | `vip_id` | `str` | `""` | VIP ID |
    | `voice_disable` | `int` | `0` | 语音禁用状态 |
    | `wx_nickname` | `str` | `""` | 微信昵称 |
    | `wx_union_id` | `str` | `""` | 微信 UnionID |

=== "缓存说明"

    `get_person_detail_full()` 带短期缓存。

    相关配置：

    | 配置 | 默认值 | 说明 |
    | --- | --- | --- |
    | `config.person_profile_cache_ttl` | `1800.0` | 域成员缓存有效期，单位为秒。 |
    | `config.person_profiles_cache_max_entries` | `3000` | 最大缓存条目数；小于等于 `0` 表示关闭缓存。 |


---

## `get_self_detail()`

获取当前登录用户的完整资料, 默认从缓存中获取

该方法使用配置中的 `person_uid` 请求当前用户详情。

```python
profile = await bot.person.get_self_detail()

print(profile.uid)
print(profile.name)
print(profile.user_level)
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `force` | `bool` | 否 | 是否强制重新获取并更新缓存 |

=== "返回值"

    返回：`Profile`。

    对应模型：`oopz_sdk.models.Profile`

    可参考 `get_person_detail_full()` 的返回值字段说明。

=== "异常"

    | 场景 | 异常 |
    | --- | --- |
    | 配置中没有 `person_uid` | `ValueError` |
    | 接口返回无法解析为 `Profile` | `OopzApiError` 或 Pydantic 校验异常 |

---


## 当前动态

通过 `client.person` 或 `bot.person` 调用。写入方法只修改当前登录账号的动态，返回 `OperationResult`。

| 方法 | 用途 |
| --- | --- |
| `get_playing_state(uid=None)` | 从 Oopz 读取最新动态，返回 `PlayingState`。省略 UID 或传入自己的 UID 时读取本人资料，其他 UID 读取公开资料。 |
| `set_game_state(name, *, game_id=0)` | 展示「正在玩」和自定义文案。传入正整数可以指定官方游戏图标，传 `0` 或省略时由 Oopz 选择图标。 |
| `set_music_state(app, song="")` | 展示「正在听」的音乐软件和歌名。省略歌名时只展示软件。 |
| `clear_playing_state()` | 清空正在展示的游戏或音乐动态。 |

```python
await bot.person.set_game_state("组队中", game_id=116)
await bot.person.set_music_state("QQ音乐", "七里香")
state = await bot.person.get_playing_state()
print(state.display_type, state.music_state, state.song_state)
await bot.person.clear_playing_state()
```

`state.display_type` 为 `"GAME"` 时，游戏文案和图标地址在 `playing_state` 和 `playing_game_image` 中。为 `"MUSIC"` 时，音乐软件和歌名在 `music_state` 和 `song_state` 中。空字符串表示没有动态。`display_playing_state` 表示是否对外展示，服务端未公开该开关时为 `None`。

写入返回 `ok=False` 表示操作失败，`message` 包含服务端提供的说明。响应的 `status` 为假或缺少 `data` 字段时，SDK 抛出 `OopzApiError`。

---

## `update_self_introduction(introduction)`

更新bot自己的个人介绍

```python

await bot.person.update_self_introduction("新的个人介绍")

```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `introduction` | `str` | 否 | 修改的个人介绍, 为空为清除个人介绍 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

    
---

## `get_level_info()`

获取当前用户等级和积分信息。

```python
level = await bot.person.get_level_info()

print(level.current_level)
print(level.next_level)
print(level.next_level_distance)
```

=== "参数"

    无参数。

=== "返回值"

    返回：`UserLevelInfo`。

    对应模型：`oopz_sdk.models.UserLevelInfo`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `auth_desc` | `str` | `""` | 认证说明 |
    | `auth_state` | `int` | `0` | 认证状态 |
    | `current_level` | `int` | `0` | 当前等级 |
    | `current_level_full_points` | `int` | `0` | 当前等级满级所需积分 |
    | `has_not_receive_prize` | `bool` | `False` | 是否有未领取奖励 |
    | `next_level` | `int` | `0` | 下一等级 |
    | `next_level_distance` | `int` | `0` | 距离下一等级还需要的积分 |
    | `pay_points` | `int` | `0` | 付费积分 |
    | `sign_in_points` | `int` | `0` | 签到积分 |

---

## `get_friendship()`

获取当前用户的好友列表。

```python
friends = await bot.person.get_friendship()

for friend in friends:
    print(friend.uid, friend.name, friend.online)
```

=== "参数"

    无参数。

=== "返回值"

    返回：`list[Friendship]`。

    对应模型：`oopz_sdk.models.Friendship`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `uid` | `str` | `""` | 好友 UID。 |
    | `name` | `str` | `""` | 好友昵称。 |
    | `online` | `bool` | `False` | 是否在线。 |

=== "异常"

    | 场景 | 异常 |
    | --- | --- |
    | 接口返回不是列表 | `OopzApiError` |

---

## `get_friendship_requests()`

获取当前用户的好友请求列表（别人加你为好友的请求）。

```python
requests = await bot.person.get_friendship_requests()

for req in requests:
    print(req.friend_request_id, req.uid, req.create_time)
```

=== "参数"

    无参数。

=== "返回值"

    返回：`list[FriendshipRequest]`。

    对应模型：`oopz_sdk.models.FriendshipRequest`

    | 字段 | 类型 | 默认值 | API 字段 | 说明 |
    | --- | --- | --- | --- | --- |
    | `friend_request_id` | `int` | `0` | `friendRequestId` | 好友请求 ID。 |
    | `uid` | `str` | `""` | `uid` | 发起请求方 UID。 |
    | `create_time` | `str` | `""` | `createTime` | 请求创建时间。 |

=== "异常"

    | 场景 | 异常 |
    | --- | --- |
    | 接口返回格式错误 | `OopzApiError` |

---

## `post_friendship_response(target, friend_request_id, agree)`

接受或拒绝某个好友请求。

```python
requests = await bot.person.get_friendship_requests()

for req in requests:
    await bot.person.post_friendship_response(
        target=req.uid,
        friend_request_id=req.friend_request_id,
        agree=True,
    )
```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `target` | `str` | 是 | 发起好友请求的用户 UID。 |
    | `friend_request_id` | `int` | 是 | 好友请求 ID（来自 `get_friendship_requests()`）。 |
    | `agree` | `bool` | 是 | `True` 表示同意，`False` 表示拒绝。 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

---

## `get_person_remark_name(uid)`

获取bot自己给别人的备注名。

```python

response = await bot.person.get_person_remark_name(uid)
for user_remark_name in response:
    print(user_remark_name.uid, user_remark_name.remark_name)

```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `uid` | `str` | 是 | 用户 UID，不能为空。 |

=== "返回值"

    返回：`UserRemarkNamesResponse`。

    对应模型：`oopz_sdk.models.UserRemarkNamesResponse`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `user_remark_names` | `list[UserRemarkName] ` | 用户设置的备注名列表 |
    
    `UserRemarkName` 字段：
    
    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `uid` | `str` | `""` | 用户 UID。 |
    | `remark_name` | `str` | `""` | 备注名。 |
---


## `set_user_remark_name(uid, remark_name="")`

获取bot自己给别人的备注名。

```python

await bot.person.set_user_remark_name(uid, "新的备注名")

```

=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `uid` | `str` | 是 | 用户 UID，不能为空。 |
    | `remark_name` | `str` | 否 | 修改的备注名, 为空为清除备注名 |

=== "返回值"

    返回：`OperationResult`。

    对应模型：`oopz_sdk.models.OperationResult`

    | 字段 | 类型 | 默认值 | 说明 |
    | --- | --- | --- | --- |
    | `ok` | `bool` | `True` | 操作是否成功。 |
    | `message` | `str` | `""` | 操作消息或错误信息。 |

    
---

## 常见任务：获取当前用户

```python
me = await bot.person.get_person_info()

print(me.uid)
print(me.name)
```

---

## 常见任务：批量获取用户信息

```python
users = await bot.person.get_person_infos_batch([
    "uid1",
    "uid2",
    "uid3",
])

for user in users:
    print(user.uid, user.name)
```

---

## 常见任务：获取当前用户完整资料

```python
profile = await bot.person.get_self_detail()

print(profile.uid)
print(profile.name)
print(profile.user_level)
```
