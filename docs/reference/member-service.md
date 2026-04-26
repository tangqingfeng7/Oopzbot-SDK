# Member Service

入口：`client.members` 或 `bot.members`。

该 service 负责用户资料、好友、好友请求等能力。

!!! note
    旧文档可能把这个入口称为 `person`。当前 SDK 代码实际挂载名是 `members`。

## 方法列表

| 方法 | 说明 | 返回 |
| --- | --- | --- |
| `get_person_infos_batch(uids)` | 批量获取用户基本信息，内部按 30 个一批请求。 | `list[UserInfo]` |
| `get_person_info(uid=None)` | 获取指定用户基本信息；默认当前登录用户。 | `UserInfo` |
| `get_person_detail_full(uid)` | 获取指定用户完整资料。 | `Profile` |
| `get_self_detail()` | 获取当前登录用户完整资料。 | `Profile` |
| `get_level_info()` | 获取当前用户等级信息。 | `UserLevelInfo` |
| `get_friendship()` | 获取好友列表。 | `list[Friendship]` |
| `get_friendship_requests()` | 获取好友请求列表。 | `list[FriendshipRequest]` |
| `post_friendship_response(target, friend_request_id, agree)` | 同意或拒绝好友请求。 | `OperationResult` |

## 获取当前用户

```python
me = await client.members.get_person_info()
print(me.uid, me.name)
```

## 批量获取用户

```python
users = await client.members.get_person_infos_batch(["uid1", "uid2"])
```

## 处理好友请求

```python
requests = await client.members.get_friendship_requests()
for req in requests:
    await client.members.post_friendship_response(
        target=req.uid,
        friend_request_id=req.friend_request_id,
        agree=True,
    )
```
