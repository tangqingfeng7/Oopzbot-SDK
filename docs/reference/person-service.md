# Person Service

`Person Service` 用于获取用户基本信息、用户完整资料，以及当前用户等级信息。


---

## `get_person_info(uid=None)`

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

=== "异常"

    | 场景 | 异常 |
    | --- | --- |
    | 没有传 `uid`，并且配置中没有 `person_uid` | `ValueError` |
    | 接口返回不是列表 | `OopzApiError` |
    | 接口返回空列表 | `OopzApiError` |

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



## `get_person_detail_full(uid)`

获取指定用户的完整资料。

相比 `get_person_info()`，该方法返回的信息更完整，例如 IP 属地、VIP 信息、关注数、粉丝数、主页装饰、游戏 / 音乐状态等。

```python
profile = await bot.person.get_person_detail_full("用户 UID")

print(profile.uid)
print(profile.name)
print(profile.ip_address)
```

recommendArea=== "参数"

    | 参数 | 类型 | 必填 | 说明 |
    | --- | --- | --- | --- |
    | `uid` | `str` | 是 | 用户 UID，不能为空。 |

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
    | `display_playing_state` | `Any` | `None` | 暂未使用 |
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

=== "异常"

    | 场景 | 异常 |
    | --- | --- |
    | `uid` 为空 | `ValueError` |
    | 接口返回无法解析为 `Profile` | `OopzApiError` 或 Pydantic 校验异常 |

---

## `get_self_detail()`

获取当前登录用户的完整资料。

该方法使用配置中的 `person_uid` 请求当前用户详情。

```python
profile = await bot.person.get_self_detail()

print(profile.uid)
print(profile.name)
print(profile.user_level)
```

=== "参数"

    无参数。

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
